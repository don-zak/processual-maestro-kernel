from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Protocol

from processual_api.auth.delivery_crypto import DeliveryPayloadCipher
from processual_api.auth.normalization import normalize_email
from processual_api.auth.token_material import TokenDigester

if TYPE_CHECKING:
    from processual_api.auth.models import AuthActionToken, IdentityUser

EMAIL_VERIFICATION_TTL = timedelta(hours=24)
RESEND_COOLDOWN = timedelta(seconds=60)


class EmailVerificationRepository(Protocol):
    async def verification_principals_for_update(
        self,
        token_hash: str,
    ) -> tuple[AuthActionToken, IdentityUser] | None: ...

    async def pending_user_for_update(self, email_normalized: str) -> IdentityUser | None: ...

    async def latest_active_verification_token(
        self,
        user_id: uuid.UUID,
    ) -> AuthActionToken | None: ...

    async def invalidate_active_verification_tokens(
        self,
        user_id: uuid.UUID,
        *,
        invalidated_at: datetime,
    ) -> None: ...

    def add_verification_delivery(self, **values) -> None: ...


class EmailVerificationUnitOfWork(Protocol):
    repository: EmailVerificationRepository

    async def __aenter__(self) -> EmailVerificationUnitOfWork: ...

    async def __aexit__(self, exc_type, exc, traceback) -> None: ...

    async def commit(self) -> None: ...


@dataclass(frozen=True, slots=True)
class VerificationOutcome:
    processed: bool = True


@dataclass(frozen=True, slots=True)
class ResendOutcome:
    accepted: bool = True


class EmailVerificationService:
    def __init__(
        self,
        *,
        unit_of_work_factory: Callable[[], EmailVerificationUnitOfWork],
        token_digester: TokenDigester,
        delivery_cipher: DeliveryPayloadCipher,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._token_digester = token_digester
        self._delivery_cipher = delivery_cipher
        self._clock = clock or (lambda: datetime.now(UTC))

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("Email verification clock must be timezone-aware.")
        return now

    async def verify(self, raw_token: str) -> VerificationOutcome:
        token_hash = self._token_digester.digest(raw_token, purpose="verify_email")
        now = self._now()
        async with self._unit_of_work_factory() as unit_of_work:
            principals = await unit_of_work.repository.verification_principals_for_update(
                token_hash
            )
            if principals is None:
                return VerificationOutcome()
            action_token, user = principals
            if (
                action_token.consumed_at is not None
                or action_token.invalidated_at is not None
                or action_token.expires_at <= now
                or user.status not in {"pending_verification", "active"}
            ):
                return VerificationOutcome()
            action_token.consumed_at = now
            if user.status == "pending_verification":
                user.status = "active"
                user.email_verified_at = now
            await unit_of_work.commit()
        return VerificationOutcome()

    async def resend(self, email: str) -> ResendOutcome:
        email_normalized = normalize_email(email)
        now = self._now()
        verification = self._token_digester.generate_token(purpose="verify_email")
        action_token_id = uuid.uuid4()
        outbox_id = uuid.uuid4()

        async with self._unit_of_work_factory() as unit_of_work:
            user = await unit_of_work.repository.pending_user_for_update(email_normalized)
            if user is None:
                return ResendOutcome()
            latest = await unit_of_work.repository.latest_active_verification_token(user.id)
            if latest is not None and latest.created_at + RESEND_COOLDOWN > now:
                return ResendOutcome()
            encrypted_delivery = self._delivery_cipher.encrypt(
                verification.raw,
                outbox_id=str(outbox_id),
                user_id=str(user.id),
                action_token_id=str(action_token_id),
                purpose="verify_email",
            )
            await unit_of_work.repository.invalidate_active_verification_tokens(
                user.id,
                invalidated_at=now,
            )
            unit_of_work.repository.add_verification_delivery(
                user=user,
                action_token_id=action_token_id,
                action_token_hash=verification.digest,
                action_token_expires_at=now + EMAIL_VERIFICATION_TTL,
                outbox_id=outbox_id,
                payload_ciphertext=encrypted_delivery.ciphertext,
                payload_key_version=encrypted_delivery.key_version,
                available_at=now,
            )
            await unit_of_work.commit()
        return ResendOutcome()


__all__ = [
    "EMAIL_VERIFICATION_TTL",
    "RESEND_COOLDOWN",
    "EmailVerificationService",
    "ResendOutcome",
    "VerificationOutcome",
]
