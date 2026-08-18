from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from processual_api.admin_governance.onboarding_mfa_authority import (
    AdministratorOnboardingMfaAuthority,
    AdministratorOnboardingMfaDeniedError,
)


@dataclass
class FakeInvitation:
    id: uuid.UUID
    email_normalized: str
    supervision_level: str
    status: str
    accepted_by_user_id: uuid.UUID | None
    onboarding_mfa_proof_hash: str | None
    onboarding_mfa_proof_expires_at: datetime | None


class FakeRepository:
    def __init__(self, invitation: FakeInvitation | None) -> None:
        self.invitation = invitation

    async def invitation_by_id(self, *, invitation_id: uuid.UUID):
        if self.invitation is None or self.invitation.id != invitation_id:
            return None
        return self.invitation


def _invitation(*, proof: str = "mfa-proof", status: str = "pending") -> FakeInvitation:
    return FakeInvitation(
        id=uuid.UUID("00000000-0000-0000-0000-000000000049"),
        email_normalized="admin@example.com",
        supervision_level="operations_supervisor",
        status=status,
        accepted_by_user_id=uuid.UUID("00000000-0000-0000-0000-000000000050"),
        onboarding_mfa_proof_hash=hashlib.sha256(proof.encode("utf-8")).hexdigest(),
        onboarding_mfa_proof_expires_at=datetime(2026, 8, 18, 10, 15, tzinfo=UTC),
    )


def _authority(invitation: FakeInvitation | None) -> AdministratorOnboardingMfaAuthority:
    return AdministratorOnboardingMfaAuthority(
        repository=FakeRepository(invitation),
        clock=lambda: datetime(2026, 8, 18, 10, 5, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_authorize_accepts_bound_unexpired_proof() -> None:
    invitation = _invitation()
    grant = await _authority(invitation).authorize(
        invitation_id=invitation.id,
        user_id=invitation.accepted_by_user_id,
        mfa_proof="mfa-proof",
    )
    assert grant.user_id == invitation.accepted_by_user_id
    assert grant.email_normalized == "admin@example.com"
    assert grant.supervision_level == "operations_supervisor"


@pytest.mark.asyncio
@pytest.mark.parametrize("proof", ["", "wrong-proof"])
async def test_authorize_rejects_missing_or_wrong_proof(proof: str) -> None:
    invitation = _invitation()
    with pytest.raises(AdministratorOnboardingMfaDeniedError):
        await _authority(invitation).authorize(
            invitation_id=invitation.id,
            user_id=invitation.accepted_by_user_id,
            mfa_proof=proof,
        )


@pytest.mark.asyncio
async def test_authorize_rejects_wrong_user_or_expired_proof() -> None:
    invitation = _invitation()
    with pytest.raises(AdministratorOnboardingMfaDeniedError):
        await _authority(invitation).authorize(
            invitation_id=invitation.id,
            user_id=uuid.uuid4(),
            mfa_proof="mfa-proof",
        )

    invitation.onboarding_mfa_proof_expires_at = datetime(2026, 8, 18, 10, 4, tzinfo=UTC)
    with pytest.raises(AdministratorOnboardingMfaDeniedError):
        await _authority(invitation).authorize(
            invitation_id=invitation.id,
            user_id=invitation.accepted_by_user_id,
            mfa_proof="mfa-proof",
        )


@pytest.mark.asyncio
async def test_authorize_rejects_non_pending_or_missing_proof_state() -> None:
    invitation = _invitation(status="accepted")
    with pytest.raises(AdministratorOnboardingMfaDeniedError):
        await _authority(invitation).authorize(
            invitation_id=invitation.id,
            user_id=invitation.accepted_by_user_id,
            mfa_proof="mfa-proof",
        )

    invitation.status = "pending"
    invitation.onboarding_mfa_proof_hash = None
    with pytest.raises(AdministratorOnboardingMfaDeniedError):
        await _authority(invitation).authorize(
            invitation_id=invitation.id,
            user_id=invitation.accepted_by_user_id,
            mfa_proof="mfa-proof",
        )
