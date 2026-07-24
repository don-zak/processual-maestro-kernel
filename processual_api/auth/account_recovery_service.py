from __future__ import annotations

import hmac
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from processual_api.auth.account_recovery_external_revocation import (
    AccountRecoveryExternalAuthorityRevoker,
)
from processual_api.auth.delivery_crypto import (
    DeliveryPayloadCipher,
)
from processual_api.auth.passwords import PasswordService
from processual_api.auth.token_material import TokenDigester

ACCOUNT_RECOVERY_VERIFICATION_TTL = timedelta(minutes=30)
ACCOUNT_RECOVERY_COMPLETION_TTL = timedelta(minutes=15)
ACCOUNT_RECOVERY_MAX_ATTEMPTS = 5
ACCOUNT_RECOVERY_PURPOSE = "platform_account_recovery"
ACCOUNT_RECOVERY_VERIFICATION_TOKEN_PURPOSE = "account_recovery_verification"
ACCOUNT_RECOVERY_COMPLETION_TOKEN_PURPOSE = "account_recovery_completion"


class AccountRecoveryDeniedError(RuntimeError):
    """Raised for all externally indistinguishable recovery denials."""


class AccountRecoveryRepository(Protocol):
    async def eligible_principal_by_login(
        self,
        *,
        login_normalized: str,
    ): ...

    async def invalidate_active_requests(
        self,
        *,
        user_id: uuid.UUID,
        invalidated_at: datetime,
    ) -> int: ...

    def add_request_with_delivery(
        self,
        **values,
    ): ...

    async def request_for_update(
        self,
        *,
        request_id: uuid.UUID,
    ): ...

    async def user_for_update(
        self,
        *,
        user_id: uuid.UUID,
    ): ...

    async def revoke_refresh_tokens(
        self,
        *,
        user_id: uuid.UUID,
        revoked_at: datetime,
    ) -> int: ...

    async def revoke_sessions(
        self,
        *,
        user_id: uuid.UUID,
        revoked_at: datetime,
        reason: str,
    ) -> int: ...

    async def invalidate_action_tokens(
        self,
        *,
        user_id: uuid.UUID,
        invalidated_at: datetime,
    ) -> int: ...

    async def disable_mfa_factors(
        self,
        *,
        user_id: uuid.UUID,
        disabled_at: datetime,
    ) -> int: ...

    async def delete_mfa_recovery_codes(
        self,
        *,
        user_id: uuid.UUID,
    ) -> int: ...


class AccountRecoveryUnitOfWork(Protocol):
    repository: AccountRecoveryRepository

    async def __aenter__(self): ...

    async def __aexit__(
        self,
        exc_type,
        exc,
        traceback,
    ): ...

    async def commit(self) -> None: ...


@dataclass(frozen=True, slots=True)
class AccountRecoveryStartReceipt:
    accepted: bool
    externally_indistinguishable: bool
    session_created: bool
    access_token_issued: bool
    refresh_token_issued: bool


@dataclass(frozen=True, slots=True)
class AccountRecoveryVerificationReceipt:
    request_id: uuid.UUID
    completion_token: str
    completion_expires_at: datetime
    session_created: bool
    access_token_issued: bool
    refresh_token_issued: bool
    password_change_required: bool
    mfa_reenrollment_required: bool


@dataclass(frozen=True, slots=True)
class AccountRecoveryCompletionReceipt:
    request_id: uuid.UUID
    completed_at: datetime
    password_changed: bool
    mfa_reenrollment_required: bool
    sessions_revoked: int
    refresh_tokens_revoked: int
    action_tokens_revoked: int
    supervisor_session_keys_revoked: int
    api_keys_revoked: int
    session_created: bool
    access_token_issued: bool
    refresh_token_issued: bool
    api_key_issued: bool
    authority_granted: bool


class AccountRecoveryService:
    def __init__(
        self,
        *,
        unit_of_work_factory: Callable[
            [],
            AccountRecoveryUnitOfWork,
        ],
        token_digester: TokenDigester,
        delivery_cipher: DeliveryPayloadCipher,
        password_service: PasswordService | None = None,
        external_authority_revoker: (AccountRecoveryExternalAuthorityRevoker | None) = None,
        clock: Callable[[], datetime] | None = None,
        verification_ttl: timedelta = (ACCOUNT_RECOVERY_VERIFICATION_TTL),
        completion_ttl: timedelta = (ACCOUNT_RECOVERY_COMPLETION_TTL),
        max_attempts: int = ACCOUNT_RECOVERY_MAX_ATTEMPTS,
    ) -> None:
        if verification_ttl <= timedelta(0):
            raise ValueError("Account recovery verification TTL must be positive.")

        if completion_ttl <= timedelta(0):
            raise ValueError("Account recovery completion TTL must be positive.")

        if max_attempts <= 0:
            raise ValueError("Account recovery max attempts must be positive.")

        self._unit_of_work_factory = unit_of_work_factory
        self._token_digester = token_digester
        self._delivery_cipher = delivery_cipher
        self._password_service = password_service or PasswordService()
        self._external_authority_revoker = external_authority_revoker
        self._clock = clock or (lambda: datetime.now(UTC))
        self._verification_ttl = verification_ttl
        self._completion_ttl = completion_ttl
        self._max_attempts = max_attempts

    def _now(self) -> datetime:
        now = self._clock()

        if now.tzinfo is None:
            raise ValueError("Account recovery clock must be timezone-aware.")

        return now

    @staticmethod
    def _normalize_login(login: str) -> str:
        normalized = login.strip().casefold()

        if not normalized:
            raise ValueError("Account recovery login identifier is required.")

        if len(normalized) > 320:
            raise ValueError("Account recovery login identifier is too long.")

        return normalized

    @staticmethod
    def _generic_start_receipt() -> AccountRecoveryStartReceipt:
        return AccountRecoveryStartReceipt(
            accepted=True,
            externally_indistinguishable=True,
            session_created=False,
            access_token_issued=False,
            refresh_token_issued=False,
        )

    async def start(
        self,
        *,
        login: str,
    ) -> AccountRecoveryStartReceipt:
        login_normalized = self._normalize_login(login)
        now = self._now()

        async with self._unit_of_work_factory() as unit:
            repository = unit.repository

            principal = await repository.eligible_principal_by_login(login_normalized=login_normalized)

            if principal is None:
                return self._generic_start_receipt()

            user, recovery_email = principal

            if (
                getattr(user, "status", None) != "active"
                or getattr(
                    recovery_email,
                    "purpose",
                    None,
                )
                != "recovery"
                or getattr(
                    recovery_email,
                    "status",
                    None,
                )
                != "verified"
                or getattr(
                    recovery_email,
                    "verified_at",
                    None,
                )
                is None
                or getattr(
                    recovery_email,
                    "revoked_at",
                    None,
                )
                is not None
            ):
                return self._generic_start_receipt()

            request_id = uuid.uuid4()
            outbox_id = uuid.uuid4()
            verification_expires_at = now + self._verification_ttl

            verification = self._token_digester.generate_token(purpose=(ACCOUNT_RECOVERY_VERIFICATION_TOKEN_PURPOSE))

            await repository.invalidate_active_requests(
                user_id=user.id,
                invalidated_at=now,
            )

            encrypted = self._delivery_cipher.encrypt(
                verification.raw,
                outbox_id=str(outbox_id),
                user_id=str(user.id),
                account_recovery_request_id=str(request_id),
                purpose=(ACCOUNT_RECOVERY_VERIFICATION_TOKEN_PURPOSE),
            )

            repository.add_request_with_delivery(
                request_id=request_id,
                outbox_id=outbox_id,
                user_id=user.id,
                recovery_email_id=recovery_email.id,
                purpose=ACCOUNT_RECOVERY_PURPOSE,
                state="pending",
                verification_token_hash=verification.digest,
                completion_token_hash=None,
                attempt_count=0,
                expires_at=verification_expires_at,
                verified_at=None,
                completed_at=None,
                revoked_at=None,
                created_at=now,
                updated_at=now,
                payload_ciphertext=encrypted.ciphertext,
                payload_key_version=encrypted.key_version,
                available_at=now,
            )

            await unit.commit()

        return self._generic_start_receipt()

    async def verify(
        self,
        *,
        request_id: uuid.UUID,
        raw_token: str,
    ) -> AccountRecoveryVerificationReceipt:
        now = self._now()

        try:
            provided_hash = self._token_digester.digest(
                raw_token,
                purpose=(ACCOUNT_RECOVERY_VERIFICATION_TOKEN_PURPOSE),
            )
        except ValueError as exc:
            raise AccountRecoveryDeniedError("Account recovery verification is unavailable.") from exc

        async with self._unit_of_work_factory() as unit:
            request = await unit.repository.request_for_update(request_id=request_id)

            if request is None:
                raise AccountRecoveryDeniedError("Account recovery verification is unavailable.")

            if (
                request.purpose != ACCOUNT_RECOVERY_PURPOSE
                or request.state != "pending"
                or request.verified_at is not None
                or request.completed_at is not None
                or request.revoked_at is not None
            ):
                raise AccountRecoveryDeniedError("Account recovery verification is unavailable.")

            if request.expires_at <= now:
                request.state = "expired"
                request.updated_at = now

                await unit.commit()

                raise AccountRecoveryDeniedError("Account recovery verification is unavailable.")

            matches = hmac.compare_digest(
                request.verification_token_hash,
                provided_hash,
            )

            if not matches:
                request.attempt_count += 1
                request.updated_at = now

                if request.attempt_count >= self._max_attempts:
                    request.state = "revoked"
                    request.revoked_at = now

                await unit.commit()

                raise AccountRecoveryDeniedError("Account recovery verification is unavailable.")

            completion = self._token_digester.generate_token(purpose=(ACCOUNT_RECOVERY_COMPLETION_TOKEN_PURPOSE))
            completion_expires_at = now + self._completion_ttl

            request.state = "verified"
            request.verified_at = now
            request.completion_token_hash = completion.digest
            request.expires_at = completion_expires_at
            request.updated_at = now

            await unit.commit()

            return AccountRecoveryVerificationReceipt(
                request_id=request.id,
                completion_token=completion.raw,
                completion_expires_at=(completion_expires_at),
                session_created=False,
                access_token_issued=False,
                refresh_token_issued=False,
                password_change_required=True,
                mfa_reenrollment_required=True,
            )

    async def complete(
        self,
        *,
        request_id: uuid.UUID,
        raw_completion_token: str,
        new_password: str,
    ) -> AccountRecoveryCompletionReceipt:
        now = self._now()

        try:
            provided_hash = self._token_digester.digest(
                raw_completion_token,
                purpose=(ACCOUNT_RECOVERY_COMPLETION_TOKEN_PURPOSE),
            )
            new_password_hash = self._password_service.hash_password(new_password)
        except (
            RuntimeError,
            ValueError,
        ) as exc:
            raise AccountRecoveryDeniedError("Account recovery completion is unavailable.") from exc

        if self._external_authority_revoker is None:
            raise AccountRecoveryDeniedError("Account recovery completion is unavailable.")

        async with self._unit_of_work_factory() as unit:
            repository = unit.repository

            request = await repository.request_for_update(
                request_id=request_id,
            )

            if request is None:
                raise AccountRecoveryDeniedError("Account recovery completion is unavailable.")

            if (
                request.purpose != ACCOUNT_RECOVERY_PURPOSE
                or request.state != "verified"
                or request.verified_at is None
                or request.completed_at is not None
                or request.revoked_at is not None
                or not request.completion_token_hash
            ):
                raise AccountRecoveryDeniedError("Account recovery completion is unavailable.")

            if request.expires_at <= now:
                request.state = "expired"
                request.updated_at = now

                await unit.commit()

                raise AccountRecoveryDeniedError("Account recovery completion is unavailable.")

            if not hmac.compare_digest(
                request.completion_token_hash,
                provided_hash,
            ):
                raise AccountRecoveryDeniedError("Account recovery completion is unavailable.")

            user = await repository.user_for_update(
                user_id=request.user_id,
            )

            if user is None or getattr(user, "status", None) != "active":
                raise AccountRecoveryDeniedError("Account recovery completion is unavailable.")

            try:
                external_receipt = self._external_authority_revoker.revoke(
                    user_id=str(user.id),
                    identity_aliases=(str(user.email_normalized),),
                )
            except (
                RuntimeError,
                ValueError,
            ) as exc:
                raise AccountRecoveryDeniedError("Account recovery completion is unavailable.") from exc

            refresh_tokens_revoked = await repository.revoke_refresh_tokens(
                user_id=user.id,
                revoked_at=now,
            )

            sessions_revoked = await repository.revoke_sessions(
                user_id=user.id,
                revoked_at=now,
                reason=("account_recovery_completed"),
            )

            action_tokens_revoked = await repository.invalidate_action_tokens(
                user_id=user.id,
                invalidated_at=now,
            )

            await repository.disable_mfa_factors(
                user_id=user.id,
                disabled_at=now,
            )

            await repository.delete_mfa_recovery_codes(
                user_id=user.id,
            )

            user.password_hash = new_password_hash
            user.password_changed_at = now
            user.failed_login_count = 0
            user.locked_until = None
            user.updated_at = now

            request.state = "completed"
            request.completed_at = now
            request.completion_token_hash = None
            request.updated_at = now

            await unit.commit()

            return AccountRecoveryCompletionReceipt(
                request_id=request.id,
                completed_at=now,
                password_changed=True,
                mfa_reenrollment_required=True,
                sessions_revoked=sessions_revoked,
                refresh_tokens_revoked=(refresh_tokens_revoked),
                action_tokens_revoked=(action_tokens_revoked),
                supervisor_session_keys_revoked=(external_receipt.supervisor_session_keys_revoked),
                api_keys_revoked=(external_receipt.api_keys_revoked),
                session_created=False,
                access_token_issued=False,
                refresh_token_issued=False,
                api_key_issued=False,
                authority_granted=False,
            )


__all__ = [
    "ACCOUNT_RECOVERY_COMPLETION_TOKEN_PURPOSE",
    "ACCOUNT_RECOVERY_COMPLETION_TTL",
    "ACCOUNT_RECOVERY_MAX_ATTEMPTS",
    "ACCOUNT_RECOVERY_PURPOSE",
    "ACCOUNT_RECOVERY_VERIFICATION_TOKEN_PURPOSE",
    "ACCOUNT_RECOVERY_VERIFICATION_TTL",
    "AccountRecoveryCompletionReceipt",
    "AccountRecoveryDeniedError",
    "AccountRecoveryService",
    "AccountRecoveryStartReceipt",
    "AccountRecoveryVerificationReceipt",
]
