from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from processual_api.auth.normalization import normalize_display_name
from processual_api.auth.passwords import PasswordService

ONBOARDING_MFA_PROOF_TTL = timedelta(minutes=15)


class AdministratorInvitationOnboardingRepository(Protocol):
    async def invitation_for_update(self, *, invitation_id: uuid.UUID): ...

    async def identity_exists(self, *, email_normalized: str) -> bool: ...

    def add_onboarding_identity(self, **values): ...

    def bind_invitation_to_onboarding_identity(self, invitation, **values) -> None: ...


class AdministratorInvitationOnboardingUnitOfWork(Protocol):
    repository: AdministratorInvitationOnboardingRepository

    async def __aenter__(self): ...

    async def __aexit__(self, exc_type, exc, traceback) -> None: ...

    async def commit(self) -> None: ...


class AdministratorInvitationOnboardingDeniedError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AdministratorInvitationOnboardingReceipt:
    user_id: uuid.UUID
    email_normalized: str
    supervision_level: str
    mfa_proof: str
    mfa_proof_expires_at: datetime
    next_action: str = "enroll_mfa"


class AdministratorInvitationOnboardingService:
    def __init__(
        self,
        *,
        unit_of_work_factory: Callable[[], AdministratorInvitationOnboardingUnitOfWork],
        password_service: PasswordService,
        clock: Callable[[], datetime] | None = None,
        user_id_factory: Callable[[], uuid.UUID] | None = None,
        proof_factory: Callable[[], str] | None = None,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._password_service = password_service
        self._clock = clock or (lambda: datetime.now(UTC))
        self._user_id_factory = user_id_factory or uuid.uuid4
        self._proof_factory = proof_factory or (lambda: secrets.token_urlsafe(32))

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("Administrator onboarding clock must be timezone-aware.")
        return now

    @staticmethod
    def _deny() -> AdministratorInvitationOnboardingDeniedError:
        return AdministratorInvitationOnboardingDeniedError(
            "Administrator invitation onboarding is invalid."
        )

    async def start(
        self,
        *,
        invitation_id: uuid.UUID,
        invitation_token: str,
        display_name: str,
        password: str,
    ) -> AdministratorInvitationOnboardingReceipt:
        if not isinstance(invitation_token, str) or not invitation_token:
            raise self._deny()

        normalized_name = normalize_display_name(display_name)
        password_hash = self._password_service.hash_password(password)
        now = self._now()
        mfa_proof = self._proof_factory()
        if not isinstance(mfa_proof, str) or len(mfa_proof) < 32:
            raise RuntimeError("Administrator onboarding MFA proof generation failed.")
        mfa_proof_hash = hashlib.sha256(mfa_proof.encode("utf-8")).hexdigest()
        mfa_proof_expires_at = now + ONBOARDING_MFA_PROOF_TTL

        async with self._unit_of_work_factory() as unit_of_work:
            repository = unit_of_work.repository
            invitation = await repository.invitation_for_update(
                invitation_id=invitation_id
            )
            if invitation is None:
                raise self._deny()

            presented_hash = hashlib.sha256(
                invitation_token.encode("utf-8")
            ).hexdigest()
            if not hmac.compare_digest(presented_hash, str(invitation.token_hash)):
                raise self._deny()

            expires_at = invitation.expires_at
            if (
                expires_at.tzinfo is None
                or invitation.status != "pending"
                or invitation.accepted_by_user_id is not None
                or expires_at <= now
            ):
                raise self._deny()

            if await repository.identity_exists(
                email_normalized=invitation.email_normalized
            ):
                raise self._deny()

            user_id = self._user_id_factory()
            repository.add_onboarding_identity(
                user_id=user_id,
                email_normalized=invitation.email_normalized,
                display_name=normalized_name,
                password_hash=password_hash,
                verified_at=now,
            )
            repository.bind_invitation_to_onboarding_identity(
                invitation,
                user_id=user_id,
                bound_at=now,
                mfa_proof_hash=mfa_proof_hash,
                mfa_proof_expires_at=mfa_proof_expires_at,
            )
            await unit_of_work.commit()

        return AdministratorInvitationOnboardingReceipt(
            user_id=user_id,
            email_normalized=invitation.email_normalized,
            supervision_level=invitation.supervision_level,
            mfa_proof=mfa_proof,
            mfa_proof_expires_at=mfa_proof_expires_at,
        )


__all__ = [
    "AdministratorInvitationOnboardingDeniedError",
    "AdministratorInvitationOnboardingReceipt",
    "AdministratorInvitationOnboardingService",
    "ONBOARDING_MFA_PROOF_TTL",
]
