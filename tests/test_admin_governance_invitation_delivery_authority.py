from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from processual_api.admin_governance.invitation_delivery_authority import (
    AdministratorInvitationDeliveryAuthority,
    AdministratorInvitationDeliveryDeniedError,
)


@dataclass
class FakeInvitation:
    id: uuid.UUID
    email_normalized: str
    supervision_level: str
    token_hash: str
    status: str
    expires_at: datetime
    accepted_by_user_id: uuid.UUID | None = None


class FakeRepository:
    def __init__(self, invitation: FakeInvitation | None) -> None:
        self.invitation = invitation
        self.requested_id: uuid.UUID | None = None

    async def invitation_by_id(self, *, invitation_id: uuid.UUID):
        self.requested_id = invitation_id
        if self.invitation is None or self.invitation.id != invitation_id:
            return None
        return self.invitation


def _invitation(*, token: str = "invite-secret", status: str = "pending") -> FakeInvitation:
    return FakeInvitation(
        id=uuid.UUID("00000000-0000-0000-0000-000000000049"),
        email_normalized="admin@example.com",
        supervision_level="operations_supervisor",
        token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
        status=status,
        expires_at=datetime(2026, 8, 18, 12, 0, tzinfo=UTC),
    )


def _authority(repository: FakeRepository) -> AdministratorInvitationDeliveryAuthority:
    return AdministratorInvitationDeliveryAuthority(
        repository=repository,
        clock=lambda: datetime(2026, 8, 18, 10, 0, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_authorize_returns_email_bound_pending_invitation() -> None:
    invitation = _invitation()
    repository = FakeRepository(invitation)

    grant = await _authority(repository).authorize(
        invitation_id=invitation.id,
        invitation_token="invite-secret",
    )

    assert repository.requested_id == invitation.id
    assert grant.invitation_id == invitation.id
    assert grant.email_normalized == "admin@example.com"
    assert grant.supervision_level == "operations_supervisor"
    assert grant.expires_at == invitation.expires_at


@pytest.mark.asyncio
@pytest.mark.parametrize("token", ["", "wrong-secret"])
async def test_authorize_rejects_missing_or_wrong_token_without_state_disclosure(token: str) -> None:
    invitation = _invitation()

    with pytest.raises(
        AdministratorInvitationDeliveryDeniedError,
        match="delivery authority is invalid",
    ):
        await _authority(FakeRepository(invitation)).authorize(
            invitation_id=invitation.id,
            invitation_token=token,
        )


@pytest.mark.asyncio
async def test_authorize_rejects_unknown_invitation_with_generic_error() -> None:
    with pytest.raises(
        AdministratorInvitationDeliveryDeniedError,
        match="delivery authority is invalid",
    ):
        await _authority(FakeRepository(None)).authorize(
            invitation_id=uuid.uuid4(),
            invitation_token="invite-secret",
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["accepted", "expired", "cancelled"])
async def test_authorize_rejects_non_pending_invitation(status: str) -> None:
    invitation = _invitation(status=status)

    with pytest.raises(AdministratorInvitationDeliveryDeniedError):
        await _authority(FakeRepository(invitation)).authorize(
            invitation_id=invitation.id,
            invitation_token="invite-secret",
        )


@pytest.mark.asyncio
async def test_authorize_rejects_invitation_already_bound_to_onboarding_identity() -> None:
    invitation = _invitation()
    invitation.accepted_by_user_id = uuid.uuid4()

    with pytest.raises(AdministratorInvitationDeliveryDeniedError):
        await _authority(FakeRepository(invitation)).authorize(
            invitation_id=invitation.id,
            invitation_token="invite-secret",
        )


@pytest.mark.asyncio
async def test_authorize_rejects_expired_invitation() -> None:
    invitation = _invitation()
    invitation.expires_at = datetime(2026, 8, 18, 9, 59, tzinfo=UTC)

    with pytest.raises(AdministratorInvitationDeliveryDeniedError):
        await _authority(FakeRepository(invitation)).authorize(
            invitation_id=invitation.id,
            invitation_token="invite-secret",
        )


@pytest.mark.asyncio
async def test_authorize_rejects_naive_invitation_expiry() -> None:
    invitation = _invitation()
    invitation.expires_at = datetime(2026, 8, 18, 12, 0)

    with pytest.raises(AdministratorInvitationDeliveryDeniedError):
        await _authority(FakeRepository(invitation)).authorize(
            invitation_id=invitation.id,
            invitation_token="invite-secret",
        )


def test_authority_requires_timezone_aware_clock() -> None:
    invitation = _invitation()
    authority = AdministratorInvitationDeliveryAuthority(
        repository=FakeRepository(invitation),
        clock=lambda: datetime(2026, 8, 18, 10, 0),
    )

    with pytest.raises(ValueError, match="timezone-aware"):
        authority._now()
