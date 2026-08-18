from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from processual_api.admin_governance.invitation_lifecycle_service import (
    AdministratorInvitationLifecycleConflictError,
    AdministratorInvitationLifecycleDeniedError,
    AdministratorInvitationLifecycleService,
)

NOW = datetime(2026, 8, 18, 15, 30, tzinfo=UTC)
ACTOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000071")
INVITATION_ID = uuid.UUID("00000000-0000-0000-0000-000000000072")
USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000073")


@dataclass
class FakeInvitation:
    id: uuid.UUID = INVITATION_ID
    status: str = "pending"
    accepted_by_user_id: uuid.UUID | None = None
    expires_at: datetime = NOW + timedelta(hours=24)
    cancelled_by_user_id: uuid.UUID | None = None
    cancelled_at: datetime | None = None
    updated_at: datetime | None = None


class FakeRepository:
    def __init__(self) -> None:
        self.actor = object()
        self.invitation: FakeInvitation | None = FakeInvitation()

    async def active_platform_admin(self, *, user_id: uuid.UUID):
        return self.actor if user_id == ACTOR_ID else None

    async def invitation_for_update(self, *, invitation_id: uuid.UUID):
        if invitation_id != INVITATION_ID:
            return None
        return self.invitation


class FakeUnitOfWork:
    def __init__(self, repository: FakeRepository) -> None:
        self.repository = repository
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True


def _service(repository: FakeRepository):
    unit = FakeUnitOfWork(repository)
    return (
        AdministratorInvitationLifecycleService(
            unit_of_work_factory=lambda: unit,
            clock=lambda: NOW,
        ),
        unit,
    )


@pytest.mark.asyncio
async def test_cancel_pending_invitation_is_atomic() -> None:
    repository = FakeRepository()
    service, unit = _service(repository)

    receipt = await service.cancel(
        invitation_id=INVITATION_ID,
        actor_user_id=ACTOR_ID,
        reason="Security review no longer requires this administrator",
        recent_step_up=True,
    )

    assert unit.committed is True
    assert receipt.status == "cancelled"
    assert receipt.cancelled_by_user_id == ACTOR_ID
    assert repository.invitation is not None
    assert repository.invitation.status == "cancelled"
    assert repository.invitation.cancelled_by_user_id == ACTOR_ID
    assert repository.invitation.cancelled_at == NOW
    assert repository.invitation.updated_at == NOW


@pytest.mark.asyncio
async def test_cancel_requires_recent_step_up() -> None:
    repository = FakeRepository()
    service, unit = _service(repository)

    with pytest.raises(
        AdministratorInvitationLifecycleDeniedError,
        match="Recent platform-administrator MFA step-up",
    ):
        await service.cancel(
            invitation_id=INVITATION_ID,
            actor_user_id=ACTOR_ID,
            reason="Security review no longer requires this administrator",
            recent_step_up=False,
        )

    assert unit.committed is False
    assert repository.invitation is not None
    assert repository.invitation.status == "pending"


@pytest.mark.asyncio
async def test_cancel_requires_active_platform_admin() -> None:
    repository = FakeRepository()
    repository.actor = None
    service, unit = _service(repository)

    with pytest.raises(
        AdministratorInvitationLifecycleDeniedError,
        match="Active platform administrator authority",
    ):
        await service.cancel(
            invitation_id=INVITATION_ID,
            actor_user_id=ACTOR_ID,
            reason="Security review no longer requires this administrator",
            recent_step_up=True,
        )

    assert unit.committed is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "accepted_by_user_id", "expires_at"),
    [
        ("accepted", USER_ID, NOW + timedelta(hours=24)),
        ("cancelled", None, NOW + timedelta(hours=24)),
        ("expired", None, NOW - timedelta(seconds=1)),
        ("pending", USER_ID, NOW + timedelta(hours=24)),
        ("pending", None, NOW),
    ],
)
async def test_non_pending_or_consumed_or_expired_invitation_cannot_be_cancelled(
    status: str,
    accepted_by_user_id: uuid.UUID | None,
    expires_at: datetime,
) -> None:
    repository = FakeRepository()
    assert repository.invitation is not None
    repository.invitation.status = status
    repository.invitation.accepted_by_user_id = accepted_by_user_id
    repository.invitation.expires_at = expires_at
    service, unit = _service(repository)

    with pytest.raises(
        AdministratorInvitationLifecycleConflictError,
        match="not cancellable",
    ):
        await service.cancel(
            invitation_id=INVITATION_ID,
            actor_user_id=ACTOR_ID,
            reason="Security review no longer requires this administrator",
            recent_step_up=True,
        )

    assert unit.committed is False


@pytest.mark.asyncio
async def test_unknown_invitation_cannot_be_cancelled() -> None:
    repository = FakeRepository()
    repository.invitation = None
    service, unit = _service(repository)

    with pytest.raises(
        AdministratorInvitationLifecycleConflictError,
        match="not cancellable",
    ):
        await service.cancel(
            invitation_id=INVITATION_ID,
            actor_user_id=ACTOR_ID,
            reason="Security review no longer requires this administrator",
            recent_step_up=True,
        )

    assert unit.committed is False
