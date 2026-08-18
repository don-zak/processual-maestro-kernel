from __future__ import annotations

import hashlib
import hmac
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol


class AdministratorOnboardingMfaRepository(Protocol):
    async def invitation_by_id(self, *, invitation_id: uuid.UUID): ...


class AdministratorOnboardingMfaDeniedError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AdministratorOnboardingMfaGrant:
    invitation_id: uuid.UUID
    user_id: uuid.UUID
    email_normalized: str
    supervision_level: str


class AdministratorOnboardingMfaAuthority:
    def __init__(
        self,
        *,
        repository: AdministratorOnboardingMfaRepository,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._clock = clock or (lambda: datetime.now(UTC))

    @staticmethod
    def _deny() -> AdministratorOnboardingMfaDeniedError:
        return AdministratorOnboardingMfaDeniedError(
            "Administrator onboarding MFA proof is invalid."
        )

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("Administrator onboarding MFA clock must be timezone-aware.")
        return now

    async def authorize(
        self,
        *,
        invitation_id: uuid.UUID,
        user_id: uuid.UUID,
        mfa_proof: str,
    ) -> AdministratorOnboardingMfaGrant:
        if not isinstance(mfa_proof, str) or not mfa_proof:
            raise self._deny()
        invitation = await self._repository.invitation_by_id(invitation_id=invitation_id)
        if invitation is None or invitation.accepted_by_user_id != user_id:
            raise self._deny()
        proof_hash = invitation.onboarding_mfa_proof_hash
        proof_expires_at = invitation.onboarding_mfa_proof_expires_at
        if not proof_hash or proof_expires_at is None or proof_expires_at.tzinfo is None:
            raise self._deny()
        candidate = hashlib.sha256(mfa_proof.encode("utf-8")).hexdigest()
        if not hmac.compare_digest(candidate, str(proof_hash)):
            raise self._deny()
        if invitation.status != "pending" or proof_expires_at <= self._now():
            raise self._deny()
        return AdministratorOnboardingMfaGrant(
            invitation_id=invitation.id,
            user_id=user_id,
            email_normalized=invitation.email_normalized,
            supervision_level=invitation.supervision_level,
        )


__all__ = [
    "AdministratorOnboardingMfaAuthority",
    "AdministratorOnboardingMfaDeniedError",
    "AdministratorOnboardingMfaGrant",
]
