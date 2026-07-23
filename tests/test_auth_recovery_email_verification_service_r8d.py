from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from processual_api.auth.delivery_crypto import (
    DeliveryPayloadCipher,
    EncryptedDeliveryPayload,
)
from processual_api.auth.recovery_email_verification_service import (
    RecoveryEmailVerificationDeniedError,
    RecoveryEmailVerificationService,
)
from processual_api.auth.token_material import TokenDigester

NOW = datetime(2026, 7, 23, 10, 0, tzinfo=UTC)


class FakeRepository:
    def __init__(self) -> None:
        self.actor = SimpleNamespace(id=uuid.uuid4())
        self.email = SimpleNamespace(
            user_id=self.actor.id,
            email_normalized="recovery@example.com",
            status="pending",
            verified_at=None,
            revoked_at=None,
            updated_at=NOW,
        )
        self.tokens = []
        self.outboxes = []
        self.invalidated = 0

    async def platform_admin_user(self, *, user_id):
        if user_id == self.actor.id:
            return self.actor
        return None

    async def pending_recovery_email_for_update(
        self,
        *,
        user_id,
    ):
        if (
            user_id == self.actor.id
            and self.email.status == "pending"
        ):
            return self.email
        return None

    async def verification_principals_for_update(
        self,
        *,
        token_hash,
    ):
        for token in self.tokens:
            if token.token_hash == token_hash:
                return token, self.email
        return None

    async def invalidate_active_tokens(
        self,
        *,
        user_id,
        invalidated_at,
    ):
        count = 0

        for token in self.tokens:
            if (
                token.user_id == user_id
                and token.consumed_at is None
            ):
                token.consumed_at = invalidated_at
                count += 1

        self.invalidated += count
        return count

    def add_verification(self, **values):
        token = SimpleNamespace(
            id=values["token_id"],
            user_id=values["user_id"],
            purpose="verify_recovery_email",
            token_hash=values["token_hash"],
            expires_at=values["expires_at"],
            consumed_at=None,
            created_at=values["available_at"],
        )

        outbox = SimpleNamespace(
            id=values["outbox_id"],
            user_id=values["user_id"],
            action_token_id=values["token_id"],
            event_type="verify_recovery_email",
            payload_ciphertext=(
                values["payload_ciphertext"]
            ),
            payload_key_version=(
                values["payload_key_version"]
            ),
        )

        self.tokens.append(token)
        self.outboxes.append(outbox)
        return token, outbox


class FakeUnitOfWork:
    def __init__(self, repository) -> None:
        self.repository = repository
        self.commit_count = 0

    async def __aenter__(self):
        return self

    async def __aexit__(
        self,
        exc_type,
        exc,
        traceback,
    ):
        return None

    async def commit(self):
        self.commit_count += 1


def build_service(repository, *, clock=lambda: NOW):
    cipher = DeliveryPayloadCipher(
        current_key_version="test-v1",
        keys={"test-v1": b"k" * 32},
    )

    unit = FakeUnitOfWork(repository)

    service = RecoveryEmailVerificationService(
        unit_of_work_factory=lambda: unit,
        token_digester=TokenDigester(b"p" * 32),
        delivery_cipher=cipher,
        clock=clock,
    )

    return service, cipher, unit


@pytest.mark.asyncio
async def test_issue_persists_digest_only_and_encrypted_outbox():
    repository = FakeRepository()
    service, cipher, unit = build_service(repository)

    receipt = await service.issue(
        actor_user_id=repository.actor.id,
        recent_step_up=True,
    )

    assert receipt.user_id == repository.actor.id
    assert len(repository.tokens) == 1
    assert len(repository.outboxes) == 1
    assert unit.commit_count == 1

    token = repository.tokens[0]
    outbox = repository.outboxes[0]

    assert token.purpose == "verify_recovery_email"
    assert token.token_hash
    assert "recovery@example.com" not in token.token_hash
    assert outbox.event_type == "verify_recovery_email"

    raw_token = cipher.decrypt(
        EncryptedDeliveryPayload(
            ciphertext=outbox.payload_ciphertext,
            key_version=outbox.payload_key_version,
        ),
        outbox_id=str(outbox.id),
        user_id=str(repository.actor.id),
        action_token_id=str(token.id),
        purpose="verify_recovery_email",
    )

    assert raw_token
    assert raw_token != token.token_hash


@pytest.mark.asyncio
async def test_replacement_invalidates_previous_token():
    repository = FakeRepository()
    service, _, _ = build_service(repository)

    await service.issue(
        actor_user_id=repository.actor.id,
        recent_step_up=True,
    )

    first = repository.tokens[0]
    assert first.consumed_at is None

    receipt = await service.issue(
        actor_user_id=repository.actor.id,
        recent_step_up=True,
    )

    assert first.consumed_at == NOW
    assert receipt.invalidated_token_count == 1
    assert len(repository.tokens) == 2


@pytest.mark.asyncio
async def test_verify_marks_email_verified_and_replay_is_denied():
    repository = FakeRepository()
    service, cipher, _ = build_service(repository)

    await service.issue(
        actor_user_id=repository.actor.id,
        recent_step_up=True,
    )

    token = repository.tokens[0]
    outbox = repository.outboxes[0]

    raw_token = cipher.decrypt(
        EncryptedDeliveryPayload(
            ciphertext=outbox.payload_ciphertext,
            key_version=outbox.payload_key_version,
        ),
        outbox_id=str(outbox.id),
        user_id=str(repository.actor.id),
        action_token_id=str(token.id),
        purpose="verify_recovery_email",
    )

    receipt = await service.verify(raw_token=raw_token)

    assert receipt.status == "verified"
    assert repository.email.status == "verified"
    assert repository.email.verified_at == NOW
    assert token.consumed_at == NOW

    with pytest.raises(
        RecoveryEmailVerificationDeniedError
    ):
        await service.verify(raw_token=raw_token)


@pytest.mark.asyncio
async def test_expired_token_is_denied():
    repository = FakeRepository()
    service, cipher, _ = build_service(repository)

    await service.issue(
        actor_user_id=repository.actor.id,
        recent_step_up=True,
    )

    token = repository.tokens[0]
    outbox = repository.outboxes[0]

    raw_token = cipher.decrypt(
        EncryptedDeliveryPayload(
            ciphertext=outbox.payload_ciphertext,
            key_version=outbox.payload_key_version,
        ),
        outbox_id=str(outbox.id),
        user_id=str(repository.actor.id),
        action_token_id=str(token.id),
        purpose="verify_recovery_email",
    )

    token.expires_at = NOW - timedelta(seconds=1)

    with pytest.raises(
        RecoveryEmailVerificationDeniedError
    ):
        await service.verify(raw_token=raw_token)


@pytest.mark.asyncio
async def test_issue_requires_step_up_and_platform_admin():
    repository = FakeRepository()
    service, _, _ = build_service(repository)

    with pytest.raises(
        RecoveryEmailVerificationDeniedError
    ):
        await service.issue(
            actor_user_id=repository.actor.id,
            recent_step_up=False,
        )

    with pytest.raises(
        RecoveryEmailVerificationDeniedError
    ):
        await service.issue(
            actor_user_id=uuid.uuid4(),
            recent_step_up=True,
        )
