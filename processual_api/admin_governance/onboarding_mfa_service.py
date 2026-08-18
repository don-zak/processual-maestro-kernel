from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from processual_api.admin_governance.onboarding_mfa_authority import (
    AdministratorOnboardingMfaAuthority,
)
from processual_api.auth.mfa_crypto import EncryptedMfaSecret, MfaSecretCipher
from processual_api.auth.token_material import TokenDigester
from processual_api.auth.totp import (
    build_totp_provisioning_uri,
    encode_totp_secret,
    generate_totp_secret,
    verify_totp,
)


class AdministratorOnboardingMfaRepository(Protocol):
    async def invitation_for_update(self, *, invitation_id: uuid.UUID): ...
    async def onboarding_user_for_update(self, *, user_id: uuid.UUID): ...
    async def active_mfa_factor_for_update(self, *, user_id: uuid.UUID): ...
    async def pending_mfa_factor_for_update(self, *, user_id: uuid.UUID): ...
    async def disable_pending_mfa_factors(
        self,
        *,
        user_id: uuid.UUID,
        disabled_at: datetime,
    ) -> None: ...
    def add_pending_mfa_factor(
        self,
        *,
        factor_id: uuid.UUID,
        user_id: uuid.UUID,
        label: str,
        ciphertext: bytes,
        key_version: str,
    ) -> None: ...
    async def replace_mfa_recovery_codes(
        self,
        *,
        factor_id: uuid.UUID,
        code_hashes: tuple[str, ...],
    ) -> None: ...
    def complete_mfa_onboarding(self, invitation, *, completed_at: datetime) -> None: ...


class AdministratorOnboardingMfaUnitOfWork(Protocol):
    repository: AdministratorOnboardingMfaRepository
    async def __aenter__(self): ...
    async def __aexit__(self, exc_type, exc, traceback): ...
    async def commit(self) -> None: ...


class AdministratorOnboardingMfaError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AdministratorOnboardingMfaEnrollment:
    secret: str
    provisioning_uri: str
    next_action: str = "confirm_mfa"


@dataclass(frozen=True, slots=True)
class AdministratorOnboardingMfaCompletion:
    invitation_id: uuid.UUID
    user_id: uuid.UUID
    supervision_level: str
    status: str = "mfa_complete_pending_activation"
    next_action: str = "activate_permissions"


class AdministratorOnboardingMfaService:
    def __init__(
        self,
        *,
        unit_of_work_factory: Callable[[], AdministratorOnboardingMfaUnitOfWork],
        cipher: MfaSecretCipher,
        token_digester: TokenDigester,
        issuer: str = "Processual Maestro",
        recovery_code_count: int = 10,
        clock: Callable[[], datetime] | None = None,
        factor_id_factory: Callable[[], uuid.UUID] | None = None,
    ) -> None:
        if not issuer.strip() or recovery_code_count < 6 or recovery_code_count > 20:
            raise ValueError("Invalid administrator onboarding MFA policy.")
        self._unit_of_work_factory = unit_of_work_factory
        self._cipher = cipher
        self._token_digester = token_digester
        self._issuer = issuer
        self._recovery_code_count = recovery_code_count
        self._clock = clock or (lambda: datetime.now(UTC))
        self._factor_id_factory = factor_id_factory or uuid.uuid4

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("Administrator onboarding MFA clock must be timezone-aware.")
        return now

    def _authority(self, repository: Any) -> AdministratorOnboardingMfaAuthority:
        return AdministratorOnboardingMfaAuthority(repository=repository, clock=self._clock)

    def _generate_recovery_codes(self) -> tuple[tuple[str, ...], tuple[str, ...]]:
        generated = tuple(
            self._token_digester.generate_recovery_code()
            for _ in range(self._recovery_code_count)
        )
        return (
            tuple(material.raw for material in generated),
            tuple(material.digest for material in generated),
        )

    async def enroll(
        self,
        *,
        invitation_id: uuid.UUID,
        user_id: uuid.UUID,
        mfa_proof: str,
        label: str,
    ) -> AdministratorOnboardingMfaEnrollment:
        now = self._now()
        normalized_label = " ".join(label.split())
        if not normalized_label or len(normalized_label) > 120:
            raise ValueError("Administrator onboarding MFA label is invalid.")

        async with self._unit_of_work_factory() as unit:
            repository = unit.repository
            await self._authority(repository).authorize(
                invitation_id=invitation_id,
                user_id=user_id,
                mfa_proof=mfa_proof,
            )
            user = await repository.onboarding_user_for_update(user_id=user_id)
            if (
                user is None
                or user.status != "pending_verification"
                or user.email_verified_at is None
            ):
                raise AdministratorOnboardingMfaError(
                    "Administrator onboarding identity is not eligible for MFA enrollment."
                )
            if await repository.active_mfa_factor_for_update(user_id=user_id) is not None:
                raise AdministratorOnboardingMfaError(
                    "Administrator onboarding identity already has active MFA."
                )

            await repository.disable_pending_mfa_factors(
                user_id=user_id,
                disabled_at=now,
            )
            factor_id = self._factor_id_factory()
            secret = generate_totp_secret()
            encrypted = self._cipher.encrypt(
                secret,
                factor_id=str(factor_id),
                user_id=str(user_id),
            )
            repository.add_pending_mfa_factor(
                factor_id=factor_id,
                user_id=user_id,
                label=normalized_label,
                ciphertext=encrypted.ciphertext,
                key_version=encrypted.key_version,
            )
            await unit.commit()

        return AdministratorOnboardingMfaEnrollment(
            secret=encode_totp_secret(secret),
            provisioning_uri=build_totp_provisioning_uri(
                secret=secret,
                account_name=user.email_normalized,
                issuer=self._issuer,
            ),
        )

    async def confirm(
        self,
        *,
        invitation_id: uuid.UUID,
        user_id: uuid.UUID,
        mfa_proof: str,
        code: str,
    ) -> tuple[AdministratorOnboardingMfaCompletion, tuple[str, ...]]:
        now = self._now()
        raw_codes, code_hashes = self._generate_recovery_codes()

        async with self._unit_of_work_factory() as unit:
            repository = unit.repository
            grant = await self._authority(repository).authorize(
                invitation_id=invitation_id,
                user_id=user_id,
                mfa_proof=mfa_proof,
            )
            invitation = await repository.invitation_for_update(invitation_id=invitation_id)
            user = await repository.onboarding_user_for_update(user_id=user_id)
            if invitation is None or user is None:
                raise AdministratorOnboardingMfaError(
                    "Administrator onboarding state is unavailable."
                )
            if user.status != "pending_verification" or user.email_verified_at is None:
                raise AdministratorOnboardingMfaError(
                    "Administrator onboarding identity is not eligible for MFA confirmation."
                )
            if await repository.active_mfa_factor_for_update(user_id=user_id) is not None:
                raise AdministratorOnboardingMfaError(
                    "Administrator onboarding identity already has active MFA."
                )
            factor = await repository.pending_mfa_factor_for_update(user_id=user_id)
            if factor is None:
                raise AdministratorOnboardingMfaError(
                    "Administrator onboarding MFA enrollment is unavailable."
                )

            encrypted = EncryptedMfaSecret(
                ciphertext=factor.secret_ciphertext,
                key_version=factor.secret_key_version,
            )
            try:
                secret = self._cipher.decrypt(
                    encrypted,
                    factor_id=str(factor.id),
                    user_id=str(user_id),
                )
            except ValueError as exc:
                raise AdministratorOnboardingMfaError(
                    "Administrator onboarding MFA authority is unavailable."
                ) from exc
            match = verify_totp(
                secret,
                code,
                at_time=now.timestamp(),
                last_used_step=factor.last_used_step,
            )
            if not match.accepted or match.matched_step is None:
                raise AdministratorOnboardingMfaError(
                    "Administrator onboarding MFA credential is invalid."
                )

            factor.last_used_step = match.matched_step
            factor.status = "active"
            factor.verified_at = now
            await repository.replace_mfa_recovery_codes(
                factor_id=factor.id,
                code_hashes=code_hashes,
            )
            repository.complete_mfa_onboarding(invitation, completed_at=now)
            await unit.commit()

        return (
            AdministratorOnboardingMfaCompletion(
                invitation_id=grant.invitation_id,
                user_id=grant.user_id,
                supervision_level=grant.supervision_level,
            ),
            raw_codes,
        )


__all__ = [
    "AdministratorOnboardingMfaCompletion",
    "AdministratorOnboardingMfaEnrollment",
    "AdministratorOnboardingMfaError",
    "AdministratorOnboardingMfaService",
]
