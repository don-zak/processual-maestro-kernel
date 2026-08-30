from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from processual_api.admin_governance.onboarding_activation_service import (
    AdministratorOnboardingActivationDeniedError,
    AdministratorOnboardingActivationService,
    OPERATIONS_SUPERVISOR_PERMISSIONS,
    REVIEW_SUPERVISOR_PERMISSIONS,
)

NOW = datetime(2026, 8, 18, 12, 30, tzinfo=UTC)
USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000060")
ACTOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000061")
INVITATION_ID = uuid.UUID("00000000-0000-0000-0000-000000000062")


@dataclass
class FakeInvitation:
    id: uuid.UUID = INVITATION_ID
    status: str = "accepted"
    accepted_by_user_id: uuid.UUID | None = USER_ID
    onboarding_mfa_proof_hash: str | None = None
    onboarding_mfa_proof_expires_at: datetime | None = None
    email_normalized: str = "supervisor@example.com"
    supervision_level: str = "operations_supervisor"
    invited_by_user_id: uuid.UUID = ACTOR_ID
    invite_reason: str = "Operational supervision for administrator support"


@dataclass
class FakeUser:
    id: uuid.UUID = USER_ID
    email_normalized: str = "supervisor@example.com"
    status: str = "pending_verification"
    email_verified_at: datetime | None = NOW
    updated_at: datetime | None = None


class FakeRepository:
    def __init__(self) -> None:
        self.invitation = FakeInvitation()
        self.user = FakeUser()
        self.mfa = object()
        self.actor = object()
        self.authorities: list[dict] = []
        self.permission_grants: list[dict] = []
        self.audit_events: list[dict] = []

    async def invitation_for_update(self, *, invitation_id: uuid.UUID):
        return self.invitation if invitation_id == INVITATION_ID else None

    async def onboarding_user_for_update(self, *, user_id: uuid.UUID):
        return self.user if user_id == USER_ID else None

    async def active_mfa_factor_for_update(self, *, user_id: uuid.UUID):
        return self.mfa if user_id == USER_ID else None

    async def active_platform_admin(self, *, user_id: uuid.UUID):
        return self.actor if user_id == ACTOR_ID else None

    async def platform_authority_for_update(self, *, user_id: uuid.UUID, authority: str):
        del user_id, authority
        return None

    async def permission_grant_for_update(self, *, user_id: uuid.UUID, permission: str):
        del user_id, permission
        return None

    def add_platform_supervisor_authority(self, **values):
        self.authorities.append(values)

    def add_permission_grant(self, **values):
        self.permission_grants.append(values)

    def add_governance_audit_event(self, **values):
        self.audit_events.append(values)


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
        AdministratorOnboardingActivationService(
            unit_of_work_factory=lambda: unit,
            clock=lambda: NOW,
        ),
        unit,
    )


@pytest.mark.asyncio
async def test_operations_supervisor_activation_is_atomic_and_bounded() -> None:
    repository = FakeRepository()
    service, unit = _service(repository)

    receipt = await service.activate(invitation_id=INVITATION_ID, user_id=USER_ID)

    assert unit.committed is True
    assert repository.user.status == "active"
    assert receipt.platform_authority == "platform_supervisor"
    assert set(receipt.permissions) == OPERATIONS_SUPERVISOR_PERMISSIONS
    assert len(repository.authorities) == 1
    assert {row["permission"] for row in repository.permission_grants} == OPERATIONS_SUPERVISOR_PERMISSIONS
    assert all("*" not in row["permission"] for row in repository.permission_grants)
    assert all(not row["permission"].startswith("marketplace.") for row in repository.permission_grants)
    assert len(repository.audit_events) == len(OPERATIONS_SUPERVISOR_PERMISSIONS) + 1
    assert repository.audit_events[-1]["event_type"] == "administrator.activated"


@pytest.mark.asyncio
async def test_review_supervisor_receives_read_only_permissions() -> None:
    repository = FakeRepository()
    repository.invitation.supervision_level = "review_supervisor"
    service, _ = _service(repository)

    receipt = await service.activate(invitation_id=INVITATION_ID, user_id=USER_ID)

    assert set(receipt.permissions) == REVIEW_SUPERVISOR_PERMISSIONS
    assert all(permission.endswith(".view") for permission in receipt.permissions)


@pytest.mark.asyncio
async def test_activation_requires_active_mfa_and_active_inviter() -> None:
    repository = FakeRepository()
    repository.mfa = None
    service, unit = _service(repository)

    with pytest.raises(AdministratorOnboardingActivationDeniedError, match="Active administrator MFA"):
        await service.activate(invitation_id=INVITATION_ID, user_id=USER_ID)

    assert unit.committed is False
    assert repository.user.status == "pending_verification"
    assert repository.authorities == []
    assert repository.permission_grants == []

    repository = FakeRepository()
    repository.actor = None
    service, unit = _service(repository)
    with pytest.raises(AdministratorOnboardingActivationDeniedError, match="inviting platform administrator"):
        await service.activate(invitation_id=INVITATION_ID, user_id=USER_ID)

    assert unit.committed is False
    assert repository.user.status == "pending_verification"
