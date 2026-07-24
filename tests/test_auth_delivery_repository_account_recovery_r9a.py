from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from processual_api.auth.delivery_repository import (
    SqlAlchemyDeliveryRepository,
)


class FakeResult:
    def __init__(self, rows) -> None:
        self._rows = list(rows)

    def all(self):
        return list(self._rows)


class FakeTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(
        self,
        exc_type,
        exc,
        traceback,
    ):
        return False


class FakeSession:
    def __init__(self, rows) -> None:
        self.rows = list(rows)
        self.statements = []

    async def __aenter__(self):
        return self

    async def __aexit__(
        self,
        exc_type,
        exc,
        traceback,
    ):
        return False

    def begin(self):
        return FakeTransaction()

    async def execute(self, statement):
        self.statements.append(statement)
        return FakeResult(self.rows)


def _repository(rows):
    session = FakeSession(rows)

    return (
        SqlAlchemyDeliveryRepository(session_factory=lambda: session),
        session,
    )


@pytest.mark.asyncio
async def test_claims_account_recovery_delivery_with_verified_address():
    now = datetime(
        2026,
        7,
        24,
        9,
        tzinfo=UTC,
    )
    user_id = uuid.uuid4()
    request_id = uuid.uuid4()

    outbox = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user_id,
        action_token_id=None,
        account_recovery_request_id=request_id,
        event_type="account_recovery_verification",
        payload_ciphertext=b"encrypted-payload",
        payload_key_version="delivery-v1",
        available_at=now,
        created_at=now,
        delivered_at=None,
        dead_lettered_at=None,
        claim_id=None,
        claimed_at=None,
        attempt_count=0,
    )
    user = SimpleNamespace(
        id=user_id,
        status="active",
        email_normalized="primary@example.com",
    )
    recovery_request = SimpleNamespace(
        id=request_id,
        state="pending",
        expires_at=now + timedelta(minutes=30),
        revoked_at=None,
    )
    verified_address = SimpleNamespace(
        email_normalized="recovery@example.com",
    )

    repository, session = _repository(
        [
            (
                outbox,
                user,
                None,
                recovery_request,
                None,
                verified_address,
            )
        ]
    )

    claims = await repository.claim_batch(
        now=now,
        lease_timeout=timedelta(minutes=5),
        batch_size=10,
    )

    assert len(claims) == 1
    assert len(session.statements) == 1

    claim = claims[0]

    assert claim.outbox_id == outbox.id
    assert claim.user_id == user_id
    assert claim.action_token_id is None
    assert claim.account_recovery_request_id == (request_id)
    assert claim.recipient_email == ("recovery@example.com")
    assert claim.user_status == "active"
    assert claim.event_type == ("account_recovery_verification")
    assert claim.payload_ciphertext == (b"encrypted-payload")
    assert claim.account_recovery_state == "pending"
    assert claim.account_recovery_expires_at == (recovery_request.expires_at)
    assert claim.account_recovery_revoked_at is None
    assert claim.attempt_count == 1
    assert outbox.claim_id == claim.claim_id
    assert outbox.claimed_at == now
    assert outbox.attempt_count == 1


@pytest.mark.asyncio
async def test_legacy_action_token_claim_remains_supported():
    now = datetime(
        2026,
        7,
        24,
        9,
        tzinfo=UTC,
    )
    user_id = uuid.uuid4()
    action_token_id = uuid.uuid4()

    outbox = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user_id,
        action_token_id=action_token_id,
        account_recovery_request_id=None,
        event_type="verify_email",
        payload_ciphertext=b"legacy-encrypted",
        payload_key_version="delivery-v1",
        available_at=now,
        created_at=now,
        delivered_at=None,
        dead_lettered_at=None,
        claim_id=None,
        claimed_at=None,
        attempt_count=0,
    )
    user = SimpleNamespace(
        id=user_id,
        status="pending_verification",
        email_normalized="primary@example.com",
    )
    action_token = SimpleNamespace(
        id=action_token_id,
        expires_at=now + timedelta(hours=1),
        consumed_at=None,
        invalidated_at=None,
    )

    repository, _ = _repository(
        [
            (
                outbox,
                user,
                action_token,
                None,
                None,
                None,
            )
        ]
    )

    claims = await repository.claim_batch(
        now=now,
        lease_timeout=timedelta(minutes=5),
        batch_size=10,
    )

    assert len(claims) == 1

    claim = claims[0]

    assert claim.action_token_id == action_token_id
    assert claim.account_recovery_request_id is None
    assert claim.recipient_email == ("primary@example.com")
    assert claim.action_token_expires_at == (action_token.expires_at)
    assert claim.action_token_consumed_at is None
    assert claim.action_token_invalidated_at is None
