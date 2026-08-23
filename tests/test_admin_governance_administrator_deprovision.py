from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from processual_api.admin_governance.administrator_deprovision_service import (
    AdministratorDeprovisionConflictError,
    AdministratorDeprovisionDeniedError,
    AdministratorDeprovisionService,
)


NOW = datetime(2026, 8, 23, 3, 30, tzinfo=UTC)


class FakeRepository:
    def __init__(self) -> None:
        self.actor_admin = SimpleNamespace(status="active")
        self.target_admin = None
        self.authority = SimpleNamespace(
            status="active",
            revoked_by_user_id=None,
            revoke_reason=None,
            revoked_at=None,
        )
        invitation_id = uuid.uuid4()
        self.grants = [
            SimpleNamespace(
                permission="governance.activity.view",
                status="active",
                source_invitation_id=invitation_id,
                revoked_by_user_id=None,
                revocation_reason=None,
                revoked_at=None,
            ),
            SimpleNamespace(
                permission="governance.sessions.view",
                status="active",
                source_invitation_id=invitation_id,
                revoked_by_user_id=None,
                revocation_reason=None,
                revoked_at=None,
            ),
        ]
        self.revoked_sessions: list[tuple[uuid.UUID, datetime, str]] = []
        self.audit_events: list[dict] = []

    async def active_platform_admin_for_update(self, *, user_id: uuid.UUID):
        if user_id == ACTOR_ID:
            return self.actor_admin
        if user_id == TARGET_ID:
            return self.target_admin
        return None

    async def platform_supervisor_for_update(self, *, user_id: uuid.UUID):
        assert user_id == TARGET_ID
        return self.authority

    async def active_permission_grants_for_update(self, *, user_id: uuid.UUID):
        assert user_id == TARGET_ID
        return tuple(grant for grant in self.grants if grant.status == "active")

    async def revoke_all_sessions(
        self,
        *,
        user_id: uuid.UUID,
        revoked_at: datetime,
        reason: str,
    ) -> None:
        self.revoked_sessions.append((user_id, revoked_at, reason))

    def add_governance_audit_event(self, **values):
        self.audit_events.append(values)
        return values


class FakeUnitOfWork:
    def __init__(self, repository: FakeRepository) -> None:
        self.repository = repository
        self.commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1


ACTOR_ID = uuid.uuid4()
TARGET_ID = uuid.uuid4()


def build_service(repository: FakeRepository):
    unit = FakeUnitOfWork(repository)
    service = AdministratorDeprovisionService(
        unit_of_work_factory=lambda: unit,
        clock=lambda: NOW,
    )
    return service, unit


@pytest.mark.asyncio
async def test_revoke_supervisor_authority_is_atomic_and_audited():
    repository = FakeRepository()
    service, unit = build_service(repository)

    receipt = await service.revoke_supervisor_authority(
        actor_user_id=ACTOR_ID,
        target_user_id=TARGET_ID,
        reason="Supervisor access is no longer required.",
        recent_step_up=True,
    )

    assert receipt.status == "revoked"
    assert receipt.revoked_permission_count == 2
    assert receipt.occurred_at == NOW
    assert unit.commits == 1
    assert repository.authority.status == "revoked"
    assert repository.authority.revoked_by_user_id == ACTOR_ID
    assert repository.authority.revoked_at == NOW
    assert all(grant.status == "revoked" for grant in repository.grants)
    assert all(grant.revoked_by_user_id == ACTOR_ID for grant in repository.grants)
    assert all(grant.revoked_at == NOW for grant in repository.grants)
    assert repository.revoked_sessions == [
        (TARGET_ID, NOW, "administrator_supervisor_authority_revoked")
    ]
    assert [event["event_type"] for event in repository.audit_events] == [
        "administrator.permission.revoked",
        "administrator.permission.revoked",
        "administrator.supervisor_authority.revoked",
    ]


@pytest.mark.asyncio
async def test_revoke_supervisor_authority_requires_recent_step_up():
    repository = FakeRepository()
    service, unit = build_service(repository)

    with pytest.raises(AdministratorDeprovisionDeniedError, match="recent_mfa_step_up_required"):
        await service.revoke_supervisor_authority(
            actor_user_id=ACTOR_ID,
            target_user_id=TARGET_ID,
            reason="Supervisor access is no longer required.",
            recent_step_up=False,
        )

    assert unit.commits == 0


@pytest.mark.asyncio
async def test_revoke_supervisor_authority_requires_active_platform_admin():
    repository = FakeRepository()
    repository.actor_admin = None
    service, unit = build_service(repository)

    with pytest.raises(
        AdministratorDeprovisionDeniedError,
        match="active_platform_administrator_required",
    ):
        await service.revoke_supervisor_authority(
            actor_user_id=ACTOR_ID,
            target_user_id=TARGET_ID,
            reason="Supervisor access is no longer required.",
            recent_step_up=True,
        )

    assert unit.commits == 0


@pytest.mark.asyncio
async def test_revoke_supervisor_authority_protects_platform_administrator():
    repository = FakeRepository()
    repository.target_admin = SimpleNamespace(status="active")
    service, unit = build_service(repository)

    with pytest.raises(
        AdministratorDeprovisionDeniedError,
        match="platform_administrator_deprovision_denied",
    ):
        await service.revoke_supervisor_authority(
            actor_user_id=ACTOR_ID,
            target_user_id=TARGET_ID,
            reason="Supervisor access is no longer required.",
            recent_step_up=True,
        )

    assert unit.commits == 0
    assert repository.authority.status == "active"


@pytest.mark.asyncio
async def test_revoke_supervisor_authority_replay_conflicts():
    repository = FakeRepository()
    repository.authority.status = "revoked"
    service, unit = build_service(repository)

    with pytest.raises(AdministratorDeprovisionConflictError):
        await service.revoke_supervisor_authority(
            actor_user_id=ACTOR_ID,
            target_user_id=TARGET_ID,
            reason="Supervisor access is no longer required.",
            recent_step_up=True,
        )

    assert unit.commits == 0
