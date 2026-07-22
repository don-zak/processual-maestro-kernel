from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from processual_api.auth.delivery_crypto import DeliveryPayloadCipher
from processual_api.auth.email_verification_service import (
    RESEND_COOLDOWN,
    EmailVerificationService,
)
from processual_api.auth.token_material import TokenDigester


class FakeRepository:
    def __init__(self) -> None:
        self.principals = None
        self.pending_user = None
        self.latest = None
        self.invalidations = []
        self.deliveries = []

    async def verification_principals_for_update(self, token_hash):
        return self.principals if self.principals and self.principals[0].token_hash == token_hash else None

    async def pending_user_for_update(self, email_normalized):
        if self.pending_user and self.pending_user.email_normalized == email_normalized:
            return self.pending_user
        return None

    async def latest_active_verification_token(self, user_id):
        return self.latest

    async def invalidate_active_verification_tokens(self, user_id, *, invalidated_at):
        self.invalidations.append((user_id, invalidated_at))

    def add_verification_delivery(self, **values):
        self.deliveries.append(values)


class FakeUnitOfWork:
    def __init__(self, repository) -> None:
        self.repository = repository
        self.commit_count = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    async def commit(self):
        self.commit_count += 1


def _service(repository, unit_of_work, *, now):
    return EmailVerificationService(
        unit_of_work_factory=lambda: unit_of_work,
        token_digester=TokenDigester(b"t" * 32),
        delivery_cipher=DeliveryPayloadCipher(
            current_key_version="v1",
            keys={"v1": b"k" * 32},
        ),
        clock=lambda: now,
    )


def test_valid_verification_consumes_once_and_activates_pending_user():
    now = datetime(2026, 7, 22, 12, tzinfo=UTC)
    digester = TokenDigester(b"t" * 32)
    material = digester.generate_token(purpose="verify_email")
    user = SimpleNamespace(status="pending_verification", email_verified_at=None)
    token = SimpleNamespace(
        token_hash=material.digest,
        consumed_at=None,
        invalidated_at=None,
        expires_at=now + timedelta(hours=1),
    )
    repository = FakeRepository()
    repository.principals = (token, user)
    unit_of_work = FakeUnitOfWork(repository)
    service = _service(repository, unit_of_work, now=now)

    first = asyncio.run(service.verify(material.raw))
    second = asyncio.run(service.verify(material.raw))

    assert first.processed is second.processed is True
    assert token.consumed_at == now
    assert user.status == "active"
    assert user.email_verified_at == now
    assert unit_of_work.commit_count == 1


def test_expired_or_invalidated_verification_is_generic_and_has_no_write():
    now = datetime(2026, 7, 22, 12, tzinfo=UTC)
    digester = TokenDigester(b"t" * 32)
    material = digester.generate_token(purpose="verify_email")
    user = SimpleNamespace(status="pending_verification", email_verified_at=None)
    repository = FakeRepository()
    repository.principals = (
        SimpleNamespace(
            token_hash=material.digest,
            consumed_at=None,
            invalidated_at=now - timedelta(seconds=1),
            expires_at=now + timedelta(hours=1),
        ),
        user,
    )
    unit_of_work = FakeUnitOfWork(repository)

    outcome = asyncio.run(_service(repository, unit_of_work, now=now).verify(material.raw))

    assert outcome.processed is True
    assert user.status == "pending_verification"
    assert unit_of_work.commit_count == 0


def test_resend_rotates_token_and_outbox_in_one_commit():
    now = datetime(2026, 7, 22, 12, tzinfo=UTC)
    user = SimpleNamespace(
        id="00000000-0000-0000-0000-000000000001",
        email_normalized="person@example.com",
    )
    repository = FakeRepository()
    repository.pending_user = user
    repository.latest = SimpleNamespace(created_at=now - RESEND_COOLDOWN - timedelta(seconds=1))
    unit_of_work = FakeUnitOfWork(repository)

    outcome = asyncio.run(
        _service(repository, unit_of_work, now=now).resend(" Person@Example.com ")
    )

    assert outcome.accepted is True
    assert repository.invalidations == [(user.id, now)]
    assert len(repository.deliveries) == 1
    assert repository.deliveries[0]["user"] is user
    assert repository.deliveries[0]["payload_ciphertext"]
    assert "raw_action_token" not in repository.deliveries[0]
    assert unit_of_work.commit_count == 1


def test_resend_cooldown_and_unknown_email_are_generic_without_delivery():
    now = datetime(2026, 7, 22, 12, tzinfo=UTC)
    repository = FakeRepository()
    repository.pending_user = SimpleNamespace(
        id="00000000-0000-0000-0000-000000000001",
        email_normalized="person@example.com",
    )
    repository.latest = SimpleNamespace(created_at=now - RESEND_COOLDOWN + timedelta(seconds=1))
    unit_of_work = FakeUnitOfWork(repository)
    service = _service(repository, unit_of_work, now=now)

    cooldown = asyncio.run(service.resend("person@example.com"))
    missing = asyncio.run(service.resend("missing@example.com"))

    assert cooldown.accepted is missing.accepted is True
    assert repository.invalidations == []
    assert repository.deliveries == []
    assert unit_of_work.commit_count == 0
