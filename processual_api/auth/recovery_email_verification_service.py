from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from processual_api.auth.delivery_crypto import (
    DeliveryPayloadCipher,
)
from processual_api.auth.token_material import TokenDigester

RECOVERY_EMAIL_VERIFICATION_TTL = timedelta(hours=1)


class RecoveryEmailVerificationDeniedError(RuntimeError):
    pass


class RecoveryEmailVerificationRepository(Protocol):
    async def platform_admin_user(
        self,
        *,
        user_id: uuid.UUID,
    ): ...

    async def pending_recovery_email_for_update(
        self,
        *,
        user_id: uuid.UUID,
    ): ...

    async def verification_principals_for_update(
        self,
        *,
        token_hash: str,
    ): ...

    async def invalidate_active_tokens(
        self,
        *,
        user_id: uuid.UUID,
        invalidated_at: datetime,
    ) -> int: ...

    def add_verification(
        self,
        **values,
    ): ...


class RecoveryEmailVerificationUnitOfWork(Protocol):
    repository: RecoveryEmailVerificationRepository

    async def __aenter__(self): ...

    async def __aexit__(
        self,
        exc_type,
        exc,
        traceback,
    ): ...

    async def commit(self) -> None: ...


@dataclass(frozen=True, slots=True)
class RecoveryEmailVerificationIssueReceipt:
    user_id: uuid.UUID
    action_token_id: uuid.UUID
    outbox_id: uuid.UUID
    expires_at: datetime
    invalidated_token_count: int


@dataclass(frozen=True, slots=True)
class RecoveryEmailVerificationReceipt:
    user_id: uuid.UUID
    email_normalized: str
    status: str


class RecoveryEmailVerificationService:
    def __init__(
        self,
        *,
        unit_of_work_factory: Callable[
            [],
            RecoveryEmailVerificationUnitOfWork,
        ],
        token_digester: TokenDigester,
        delivery_cipher: DeliveryPayloadCipher,
        clock: Callable[[], datetime] | None = None,
        token_ttl: timedelta = (
            RECOVERY_EMAIL_VERIFICATION_TTL
        ),
    ) -> None:
        if token_ttl <= timedelta(0):
            raise ValueError(
                "Recovery-email verification TTL must be positive."
            )

        self._unit_of_work_factory = unit_of_work_factory
        self._token_digester = token_digester
        self._delivery_cipher = delivery_cipher
        self._clock = clock or (lambda: datetime.now(UTC))
        self._token_ttl = token_ttl

    def _now(self) -> datetime:
        now = self._clock()

        if now.tzinfo is None:
            raise ValueError(
                "Recovery-email verification clock "
                "must be timezone-aware."
            )

        return now

    async def issue(
        self,
        *,
        actor_user_id: uuid.UUID,
        recent_step_up: bool,
    ) -> RecoveryEmailVerificationIssueReceipt:
        if not recent_step_up:
            raise RecoveryEmailVerificationDeniedError(
                "Recent MFA step-up is required."
            )

        now = self._now()
        expires_at = now + self._token_ttl
        action_token_id = uuid.uuid4()
        outbox_id = uuid.uuid4()

        verification = self._token_digester.generate_token(
            purpose="verify_recovery_email"
        )

        async with self._unit_of_work_factory() as unit:
            repository = unit.repository

            actor = await repository.platform_admin_user(
                user_id=actor_user_id
            )

            if actor is None:
                raise RecoveryEmailVerificationDeniedError(
                    "Active platform administrator authority "
                    "is required."
                )

            recovery_email = (
                await repository.pending_recovery_email_for_update(
                    user_id=actor_user_id
                )
            )

            if recovery_email is None:
                raise RecoveryEmailVerificationDeniedError(
                    "Pending recovery email is unavailable."
                )

            invalidated_count = (
                await repository.invalidate_active_tokens(
                    user_id=actor_user_id,
                    invalidated_at=now,
                )
            )

            encrypted = self._delivery_cipher.encrypt(
                verification.raw,
                outbox_id=str(outbox_id),
                user_id=str(actor_user_id),
                action_token_id=str(action_token_id),
                purpose="verify_recovery_email",
            )

            repository.add_verification(
                token_id=action_token_id,
                outbox_id=outbox_id,
                user_id=actor_user_id,
                token_hash=verification.digest,
                expires_at=expires_at,
                payload_ciphertext=encrypted.ciphertext,
                payload_key_version=encrypted.key_version,
                available_at=now,
            )

            await unit.commit()

        return RecoveryEmailVerificationIssueReceipt(
            user_id=actor_user_id,
            action_token_id=action_token_id,
            outbox_id=outbox_id,
            expires_at=expires_at,
            invalidated_token_count=invalidated_count,
        )

    async def verify(
        self,
        *,
        raw_token: str,
    ) -> RecoveryEmailVerificationReceipt:
        now = self._now()

        try:
            token_hash = self._token_digester.digest(
                raw_token,
                purpose="verify_recovery_email",
            )
        except ValueError as exc:
            raise RecoveryEmailVerificationDeniedError(
                "Recovery-email verification is unavailable."
            ) from exc

        async with self._unit_of_work_factory() as unit:
            principals = (
                await unit.repository
                .verification_principals_for_update(
                    token_hash=token_hash
                )
            )

            if principals is None:
                raise RecoveryEmailVerificationDeniedError(
                    "Recovery-email verification is unavailable."
                )

            action_token, recovery_email = principals

            if (
                action_token.consumed_at is not None
                or action_token.expires_at <= now
                or recovery_email.status != "pending"
                or recovery_email.revoked_at is not None
            ):
                raise RecoveryEmailVerificationDeniedError(
                    "Recovery-email verification is unavailable."
                )

            action_token.consumed_at = now
            recovery_email.status = "verified"
            recovery_email.verified_at = now
            recovery_email.revoked_at = None
            recovery_email.updated_at = now

            await unit.commit()

            return RecoveryEmailVerificationReceipt(
                user_id=recovery_email.user_id,
                email_normalized=(
                    recovery_email.email_normalized
                ),
                status="verified",
            )

    async def invalidate_for_user(
        self,
        *,
        actor_user_id: uuid.UUID,
        recent_step_up: bool,
    ) -> int:
        if not recent_step_up:
            raise RecoveryEmailVerificationDeniedError(
                "Recent MFA step-up is required."
            )

        now = self._now()

        async with self._unit_of_work_factory() as unit:
            actor = await unit.repository.platform_admin_user(
                user_id=actor_user_id
            )

            if actor is None:
                raise RecoveryEmailVerificationDeniedError(
                    "Active platform administrator authority "
                    "is required."
                )

            count = await unit.repository.invalidate_active_tokens(
                user_id=actor_user_id,
                invalidated_at=now,
            )

            await unit.commit()
            return count


__all__ = [
    "RECOVERY_EMAIL_VERIFICATION_TTL",
    "RecoveryEmailVerificationDeniedError",
    "RecoveryEmailVerificationIssueReceipt",
    "RecoveryEmailVerificationReceipt",
    "RecoveryEmailVerificationService",
]
