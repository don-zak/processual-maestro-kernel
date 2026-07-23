from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from processual_api.auth.platform_supervisor_service import (
    PlatformSupervisorConflictError,
    PlatformSupervisorDeniedError,
    PlatformSupervisorService,
)


class Repository:
    def __init__(self, *, admin=True, target=True, target_admin=None, supervisor=None):
        self.admin = admin
        self.target = target
        self.target_admin = target_admin
        self.supervisor = supervisor
        self.added = None

    async def active_platform_admin(self, *, user_id):
        return SimpleNamespace() if self.admin else None

    async def active_user(self, *, user_id):
        return SimpleNamespace() if self.target else None

    async def authority_for_update(self, *, user_id, authority):
        return self.target_admin if authority == "platform_admin" else self.supervisor

    def add_supervisor_authority(
        self, *, user_id, granted_by_user_id, grant_reason, now
    ):
        self.added = SimpleNamespace(
            status="active",
            granted_by_user_id=granted_by_user_id,
            grant_reason=grant_reason,
            granted_at=now,
            revoked_at=None,
            revoked_by_user_id=None,
            revocation_reason=None,
        )
        self.supervisor = self.added
        return self.added


class Unit:
    def __init__(self, repository):
        self.repository = repository
        self.commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    async def commit(self):
        self.commits += 1


def service(repository, now):
    unit = Unit(repository)
    return PlatformSupervisorService(
        unit_of_work_factory=lambda: unit,
        clock=lambda: now,
    ), unit


def test_grant_requires_step_up_and_blocks_self_delegation():
    now = datetime(2026, 7, 23, 10, tzinfo=UTC)
    actor = uuid.uuid4()
    target = uuid.uuid4()
    subject, _ = service(Repository(), now)

    with pytest.raises(PlatformSupervisorDeniedError):
        asyncio.run(subject.grant(
            actor_user_id=actor,
            target_user_id=target,
            reason="Delegated operational supervision",
            recent_step_up=False,
        ))

    with pytest.raises(PlatformSupervisorDeniedError):
        asyncio.run(subject.grant(
            actor_user_id=actor,
            target_user_id=actor,
            reason="Delegated operational supervision",
            recent_step_up=True,
        ))


def test_grant_and_revoke_governed_supervisor():
    now = datetime(2026, 7, 23, 10, tzinfo=UTC)
    actor = uuid.uuid4()
    target = uuid.uuid4()
    repository = Repository()
    subject, unit = service(repository, now)

    granted = asyncio.run(subject.grant(
        actor_user_id=actor,
        target_user_id=target,
        reason="  Delegated   operational supervision  ",
        recent_step_up=True,
    ))
    assert granted.authority == "platform_supervisor"
    assert granted.status == "active"
    assert repository.added.grant_reason == "Delegated operational supervision"

    revoked = asyncio.run(subject.revoke(
        actor_user_id=actor,
        target_user_id=target,
        reason="Operational delegation withdrawn",
        recent_step_up=True,
    ))
    assert revoked.status == "revoked"
    assert repository.supervisor.revoked_by_user_id == actor
    assert unit.commits == 2


def test_duplicate_active_supervisor_is_rejected():
    now = datetime(2026, 7, 23, 10, tzinfo=UTC)
    subject, _ = service(
        Repository(supervisor=SimpleNamespace(status="active")),
        now,
    )
    with pytest.raises(PlatformSupervisorConflictError):
        asyncio.run(subject.grant(
            actor_user_id=uuid.uuid4(),
            target_user_id=uuid.uuid4(),
            reason="Delegated operational supervision",
            recent_step_up=True,
        ))
