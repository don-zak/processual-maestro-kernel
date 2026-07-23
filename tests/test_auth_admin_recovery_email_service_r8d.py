from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from processual_api.auth.admin_recovery_email_service import (
    AdminRecoveryEmailService,
    RecoveryEmailConflictError,
    RecoveryEmailDeniedError,
)


class Repository:
    def __init__(self, actor, current=None, owner=None):
        self.actor = actor
        self.current = current
        self.owner = owner
        self.added = None

    async def platform_admin_user(self, *, user_id):
        return self.actor

    async def email_owner(self, *, email_normalized):
        return self.owner

    async def recovery_email_for_update(self, *, user_id):
        return self.current

    def add_recovery_email(self, *, user_id, email_normalized, now):
        self.added = SimpleNamespace(
            email_normalized=email_normalized,
            status="pending",
            verified_at=None,
            revoked_at=None,
            updated_at=now,
        )
        self.current = self.added
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
    return AdminRecoveryEmailService(
        unit_of_work_factory=lambda: unit,
        clock=lambda: now,
    ), unit


def test_pending_requires_step_up_and_distinct_email():
    now = datetime(2026, 7, 23, 10, tzinfo=UTC)
    actor_id = uuid.uuid4()
    actor = SimpleNamespace(email_normalized="admin@example.com")
    subject, _ = service(Repository(actor), now)

    with pytest.raises(RecoveryEmailDeniedError):
        asyncio.run(subject.set_pending(
            actor_user_id=actor_id,
            recovery_email="recovery@example.com",
            recent_step_up=False,
        ))

    with pytest.raises(RecoveryEmailConflictError):
        asyncio.run(subject.set_pending(
            actor_user_id=actor_id,
            recovery_email=" ADMIN@example.com ",
            recent_step_up=True,
        ))


def test_pending_verify_and_revoke_lifecycle():
    now = datetime(2026, 7, 23, 10, tzinfo=UTC)
    actor_id = uuid.uuid4()
    repository = Repository(
        SimpleNamespace(email_normalized="admin@example.com")
    )
    subject, unit = service(repository, now)

    pending = asyncio.run(subject.set_pending(
        actor_user_id=actor_id,
        recovery_email=" Recovery@Example.COM ",
        recent_step_up=True,
    ))
    assert pending.email_normalized == "recovery@example.com"
    assert pending.status == "pending"

    verified = asyncio.run(subject.mark_verified(
        actor_user_id=actor_id,
        expected_email="recovery@example.com",
    ))
    assert verified.status == "verified"
    assert repository.current.verified_at == now

    revoked = asyncio.run(subject.revoke(
        actor_user_id=actor_id,
        recent_step_up=True,
    ))
    assert revoked.status == "revoked"
    assert repository.current.revoked_at == now
    assert unit.commits == 3
