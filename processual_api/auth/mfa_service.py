from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from processual_api.auth.mfa_contracts import MfaEnrollment, MfaStatus
from processual_api.auth.mfa_crypto import EncryptedMfaSecret, MfaSecretCipher
from processual_api.auth.token_material import TokenDigester
from processual_api.auth.totp import (
    build_totp_provisioning_uri,
    encode_totp_secret,
    generate_totp_secret,
    verify_totp,
)


class InvalidMfaCredentialError(RuntimeError):
    """The supplied MFA credential is absent, invalid, or was already used."""


class MfaConflictError(RuntimeError):
    """The requested MFA lifecycle transition is not allowed."""


class MfaStepUpRequiredError(RuntimeError):
    """The current session does not contain a sufficiently recent MFA proof."""


class MfaAuthorityUnavailableError(RuntimeError):
    """The authoritative MFA store or crypto authority is unavailable."""


class MfaService:
    def __init__(
        self,
        *,
        unit_of_work_factory: Callable[[], Any],
        cipher: MfaSecretCipher,
        token_digester: TokenDigester,
        issuer: str = "Processual Maestro",
        recovery_code_count: int = 10,
        step_up_ttl: timedelta = timedelta(minutes=5),
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not issuer.strip() or recovery_code_count < 6 or recovery_code_count > 20:
            raise ValueError("Invalid MFA enrollment policy.")
        if step_up_ttl < timedelta(minutes=1) or step_up_ttl > timedelta(minutes=30):
            raise ValueError("Invalid MFA step-up lifetime.")
        self._unit_of_work_factory = unit_of_work_factory
        self._cipher = cipher
        self._token_digester = token_digester
        self._issuer = issuer
        self._recovery_code_count = recovery_code_count
        self._step_up_ttl = step_up_ttl
        self._clock = clock or (lambda: datetime.now(UTC))

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("MFA clock must be timezone-aware.")
        return now

    @staticmethod
    def _encrypted_factor(factor) -> EncryptedMfaSecret:
        return EncryptedMfaSecret(
            ciphertext=factor.secret_ciphertext,
            key_version=factor.secret_key_version,
        )

    def _decrypt_factor(self, factor) -> bytes:
        try:
            return self._cipher.decrypt(
                self._encrypted_factor(factor),
                factor_id=str(factor.id),
                user_id=str(factor.user_id),
            )
        except ValueError as exc:
            raise MfaAuthorityUnavailableError("MFA authority is unavailable.") from exc

    @staticmethod
    def _normalize_recovery_code(raw_code: str) -> str:
        return raw_code.strip().upper()

    def _generate_recovery_codes(self) -> tuple[tuple[str, ...], tuple[str, ...]]:
        generated = tuple(
            self._token_digester.generate_recovery_code()
            for _ in range(self._recovery_code_count)
        )
        return (
            tuple(material.raw for material in generated),
            tuple(material.digest for material in generated),
        )

    async def enroll(self, *, user_id: uuid.UUID, label: str) -> MfaEnrollment:
        now = self._now()
        uow = self._unit_of_work_factory()
        async with uow:
            repository = uow.repository
            if repository is None:
                raise MfaAuthorityUnavailableError("MFA repository is unavailable.")
            if await repository.active_factor_for_update(user_id) is not None:
                raise MfaConflictError("An active MFA factor already exists.")
            account_name = await repository.user_email(user_id)
            if not account_name:
                raise MfaAuthorityUnavailableError("MFA identity authority is unavailable.")
            await repository.disable_pending_factors(user_id, disabled_at=now)
            factor_id = uuid.uuid4()
            secret = generate_totp_secret()
            encrypted = self._cipher.encrypt(
                secret,
                factor_id=str(factor_id),
                user_id=str(user_id),
            )
            repository.add_pending_factor(
                factor_id=factor_id,
                user_id=user_id,
                label=label,
                ciphertext=encrypted.ciphertext,
                key_version=encrypted.key_version,
            )
            await uow.commit()
        return MfaEnrollment(
            secret=encode_totp_secret(secret),
            provisioning_uri=build_totp_provisioning_uri(
                secret=secret,
                account_name=account_name,
                issuer=self._issuer,
            ),
        )

    def _verify_totp_factor(self, factor, code: str, *, now: datetime) -> None:
        secret = self._decrypt_factor(factor)
        match = verify_totp(
            secret,
            code,
            at_time=now.timestamp(),
            last_used_step=factor.last_used_step,
        )
        if not match.accepted or match.matched_step is None:
            raise InvalidMfaCredentialError("MFA credential is invalid.")
        factor.last_used_step = match.matched_step

    @staticmethod
    async def _mark_session_satisfied(repository, *, user_id, session_id, now) -> None:
        auth_session = await repository.session_for_update(
            user_id=user_id,
            session_id=session_id,
        )
        if auth_session is None or auth_session.revoked_at is not None or auth_session.expires_at <= now:
            raise InvalidMfaCredentialError("MFA credential is invalid.")
        auth_session.mfa_satisfied_at = now

    def _assert_recent_step_up(self, auth_session, *, now: datetime) -> None:
        if (
            auth_session is None
            or auth_session.revoked_at is not None
            or auth_session.expires_at <= now
            or auth_session.mfa_satisfied_at is None
            or auth_session.mfa_satisfied_at < now - self._step_up_ttl
        ):
            raise MfaStepUpRequiredError("Recent MFA verification is required.")

    async def confirm_enrollment(
        self,
        *,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        code: str,
    ) -> tuple[str, ...]:
        now = self._now()
        raw_codes, code_hashes = self._generate_recovery_codes()
        uow = self._unit_of_work_factory()
        async with uow:
            repository = uow.repository
            if repository is None:
                raise MfaAuthorityUnavailableError("MFA repository is unavailable.")
            factor = await repository.pending_factor_for_update(user_id)
            if factor is None:
                raise MfaConflictError("No pending MFA enrollment exists.")
            self._verify_totp_factor(factor, code, now=now)
            factor.status = "active"
            factor.verified_at = now
            await repository.replace_recovery_codes(factor.id, code_hashes=code_hashes)
            await self._mark_session_satisfied(
                repository,
                user_id=user_id,
                session_id=session_id,
                now=now,
            )
            await uow.commit()
        return raw_codes

    async def verify(
        self,
        *,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        code: str | None,
        recovery_code: str | None,
    ) -> None:
        now = self._now()
        uow = self._unit_of_work_factory()
        async with uow:
            repository = uow.repository
            if repository is None:
                raise MfaAuthorityUnavailableError("MFA repository is unavailable.")
            factor = await repository.active_factor_for_update(user_id)
            if factor is None:
                raise InvalidMfaCredentialError("MFA credential is invalid.")
            if code is not None:
                self._verify_totp_factor(factor, code, now=now)
            elif recovery_code is not None:
                normalized = self._normalize_recovery_code(recovery_code)
                digest = self._token_digester.digest(normalized, purpose="mfa_recovery_code")
                stored = await repository.unused_recovery_code_for_update(factor.id, digest)
                if stored is None:
                    raise InvalidMfaCredentialError("MFA credential is invalid.")
                stored.used_at = now
            else:
                raise InvalidMfaCredentialError("MFA credential is invalid.")
            await self._mark_session_satisfied(
                repository,
                user_id=user_id,
                session_id=session_id,
                now=now,
            )
            await uow.commit()

    async def require_recent_step_up(self, *, user_id: uuid.UUID, session_id: uuid.UUID) -> None:
        now = self._now()
        uow = self._unit_of_work_factory()
        async with uow:
            repository = uow.repository
            if repository is None:
                raise MfaAuthorityUnavailableError("MFA repository is unavailable.")
            auth_session = await repository.session_for_update(user_id=user_id, session_id=session_id)
            self._assert_recent_step_up(auth_session, now=now)

    async def regenerate_recovery_codes(
        self,
        *,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> tuple[str, ...]:
        now = self._now()
        raw_codes, code_hashes = self._generate_recovery_codes()
        uow = self._unit_of_work_factory()
        async with uow:
            repository = uow.repository
            if repository is None:
                raise MfaAuthorityUnavailableError("MFA repository is unavailable.")
            auth_session = await repository.session_for_update(user_id=user_id, session_id=session_id)
            self._assert_recent_step_up(auth_session, now=now)
            factor = await repository.active_factor_for_update(user_id)
            if factor is None:
                raise MfaConflictError("No active MFA factor exists.")
            await repository.replace_recovery_codes(factor.id, code_hashes=code_hashes)
            await uow.commit()
        return raw_codes

    async def disable(self, *, user_id: uuid.UUID, session_id: uuid.UUID) -> None:
        now = self._now()
        uow = self._unit_of_work_factory()
        async with uow:
            repository = uow.repository
            if repository is None:
                raise MfaAuthorityUnavailableError("MFA repository is unavailable.")
            auth_session = await repository.session_for_update(user_id=user_id, session_id=session_id)
            self._assert_recent_step_up(auth_session, now=now)
            if await repository.is_required_by_role(user_id):
                raise MfaConflictError("MFA is required for this identity role.")
            factor = await repository.active_factor_for_update(user_id)
            if factor is None:
                raise MfaConflictError("No active MFA factor exists.")
            factor.status = "disabled"
            factor.disabled_at = now
            await repository.replace_recovery_codes(factor.id, code_hashes=())
            await repository.revoke_other_sessions(
                user_id=user_id,
                current_session_id=session_id,
                revoked_at=now,
                reason="mfa_disabled",
            )
            await uow.commit()

    async def status(self, *, user_id: uuid.UUID, session_id: uuid.UUID) -> MfaStatus:
        now = self._now()
        uow = self._unit_of_work_factory()
        async with uow:
            repository = uow.repository
            if repository is None:
                raise MfaAuthorityUnavailableError("MFA repository is unavailable.")
            enabled, pending = await repository.factor_statuses(user_id)
            factor = await repository.active_factor_for_update(user_id) if enabled else None
            remaining = await repository.recovery_codes_remaining(factor.id) if factor is not None else 0
            auth_session = await repository.session_for_update(user_id=user_id, session_id=session_id)
            satisfied = bool(
                auth_session is not None
                and auth_session.mfa_satisfied_at is not None
                and auth_session.mfa_satisfied_at >= now - self._step_up_ttl
            )
        return MfaStatus(enabled, pending, remaining, satisfied)


__all__ = [
    "InvalidMfaCredentialError",
    "MfaAuthorityUnavailableError",
    "MfaConflictError",
    "MfaService",
    "MfaStepUpRequiredError",
]
