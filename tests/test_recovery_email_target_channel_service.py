from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from processual_api.auth.recovery_email_verification_service import (
    RecoveryEmailVerificationDeniedError,
    RecoveryEmailVerificationService,
)


class _TokenDigester:
    def generate_token(self, *, purpose: str):
        assert purpose == "verify_recovery_email"
        return SimpleNamespace(raw="raw-verification", digest="verification-digest")

    def digest(self, raw_token: str, *, purpose: str):
        assert purpose == "verify_recovery_email"
        return f"digest:{raw_token}"


class _Cipher:
    def encrypt(self, raw: str, **values):
        assert raw == "raw-verification"
        assert values["purpose"] == "verify_recovery_email"
        return SimpleNamespace(ciphertext="ciphertext", key_version="v1")


class _Repository:
    def __init__(self, *, actor, target, collision=None, current=None):
        self.actor = actor
        self.target = target
        self.collision = collision
        self.current = current
        self.invalidated = []
        self.added_addresses = []
        self.verifications = []

    async def platform_admin_user(self, *, user_id):
        return self.actor if self.actor and self.actor.id == user_id else None

    async def active_user_by_login_for_update(self, *, login_normalized):
        if self.target and self.target.email_normalized == login_normalized:
            return self.target
        return None

    async def recovery_email_by_address_for_update(self, *, email_normalized):
        if self.collision and self.collision.email_normalized == email_normalized:
            return self.collision
        return None

    async def recovery_email_for_update(self, *, user_id):
        if self.current and self.current.user_id == user_id:
            return self.current
        return None

    def add_pending_recovery_email(self, **values):
        address = SimpleNamespace(
            id=values["address_id"],
            user_id=values["user_id"],
            email_normalized=values["email_normalized"],
            purpose="recovery",
            status="pending",
            verified_at=None,
            revoked_at=None,
            created_at=values["created_at"],
            updated_at=values["created_at"],
        )
        self.added_addresses.append(address)
        self.current = address
        return address

    async def invalidate_active_tokens(self, *, user_id, invalidated_at):
        self.invalidated.append((user_id, invalidated_at))
        return 2

    def add_verification(self, **values):
        self.verifications.append(values)


class _Unit:
    def __init__(self, repository):
        self.repository = repository
        self.commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    async def commit(self):
        self.commits += 1


def _service(repository, now):
    return RecoveryEmailVerificationService(
        unit_of_work_factory=lambda: _Unit(repository),
        token_digester=_TokenDigester(),
        delivery_cipher=_Cipher(),
        clock=lambda: now,
    )


def test_platform_admin_can_stage_target_recovery_channel_and_issue_verification() -> None:
    now = datetime(2026, 8, 21, 15, 0, tzinfo=UTC)
    actor = SimpleNamespace(id=uuid.uuid4())
    target = SimpleNamespace(id=uuid.uuid4(), email_normalized="customer@example.test")
    repository = _Repository(actor=actor, target=target)
    service = _service(repository, now)

    receipt = asyncio.run(
        service.issue_for_target(
            actor_user_id=actor.id,
            target_login="Customer@Example.Test",
            recovery_email="Safe.Contact@Example.Test",
            recent_step_up=True,
        )
    )

    assert receipt.user_id == target.id
    assert receipt.invalidated_token_count == 2
    assert len(repository.added_addresses) == 1
    address = repository.added_addresses[0]
    assert address.email_normalized == "safe.contact@example.test"
    assert address.status == "pending"
    assert address.verified_at is None
    assert repository.invalidated == [(target.id, now)]
    assert len(repository.verifications) == 1
    verification = repository.verifications[0]
    assert verification["user_id"] == target.id
    assert verification["token_hash"] == "verification-digest"
    assert verification["payload_ciphertext"] == "ciphertext"


def test_target_channel_replacement_reuses_existing_row_but_requires_new_verification() -> None:
    now = datetime(2026, 8, 21, 15, 5, tzinfo=UTC)
    actor = SimpleNamespace(id=uuid.uuid4())
    target = SimpleNamespace(id=uuid.uuid4(), email_normalized="customer@example.test")
    current = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=target.id,
        email_normalized="old@example.test",
        status="verified",
        verified_at=now,
        revoked_at=None,
        updated_at=now,
    )
    repository = _Repository(actor=actor, target=target, current=current)
    service = _service(repository, now)

    asyncio.run(
        service.issue_for_target(
            actor_user_id=actor.id,
            target_login="customer@example.test",
            recovery_email="new@example.test",
            recent_step_up=True,
        )
    )

    assert current.email_normalized == "new@example.test"
    assert current.status == "pending"
    assert current.verified_at is None
    assert len(repository.verifications) == 1


def test_target_channel_replacement_rejects_cross_account_recovery_email_collision() -> None:
    now = datetime(2026, 8, 21, 15, 10, tzinfo=UTC)
    actor = SimpleNamespace(id=uuid.uuid4())
    target = SimpleNamespace(id=uuid.uuid4(), email_normalized="customer@example.test")
    collision = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        email_normalized="safe@example.test",
    )
    repository = _Repository(actor=actor, target=target, collision=collision)
    service = _service(repository, now)

    with pytest.raises(RecoveryEmailVerificationDeniedError):
        asyncio.run(
            service.issue_for_target(
                actor_user_id=actor.id,
                target_login="customer@example.test",
                recovery_email="safe@example.test",
                recent_step_up=True,
            )
        )

    assert repository.invalidated == []
    assert repository.verifications == []
    assert repository.added_addresses == []


def test_target_channel_replacement_requires_platform_admin_and_recent_mfa() -> None:
    now = datetime(2026, 8, 21, 15, 15, tzinfo=UTC)
    actor = SimpleNamespace(id=uuid.uuid4())
    target = SimpleNamespace(id=uuid.uuid4(), email_normalized="customer@example.test")

    no_admin_repository = _Repository(actor=None, target=target)
    no_admin_service = _service(no_admin_repository, now)
    with pytest.raises(RecoveryEmailVerificationDeniedError):
        asyncio.run(
            no_admin_service.issue_for_target(
                actor_user_id=actor.id,
                target_login="customer@example.test",
                recovery_email="safe@example.test",
                recent_step_up=True,
            )
        )

    repository = _Repository(actor=actor, target=target)
    service = _service(repository, now)
    with pytest.raises(RecoveryEmailVerificationDeniedError):
        asyncio.run(
            service.issue_for_target(
                actor_user_id=actor.id,
                target_login="customer@example.test",
                recovery_email="safe@example.test",
                recent_step_up=False,
            )
        )

    assert repository.verifications == []
