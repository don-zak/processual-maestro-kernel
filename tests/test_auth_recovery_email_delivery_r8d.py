from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from processual_api.auth.delivery_contracts import (
    DeliveryClaim,
)
from processual_api.auth.delivery_crypto import (
    DeliveryPayloadCipher,
)
from processual_api.auth.delivery_dispatcher import (
    DeliveryDispatcher,
    DeliveryDispatcherConfig,
)
from processual_api.auth.delivery_provider import (
    HttpEmailDeliveryProvider,
)

NOW = datetime(2026, 7, 23, 13, tzinfo=UTC)


class FakeRepository:
    def __init__(self, claims) -> None:
        self.claims = tuple(claims)
        self.delivered = []
        self.failed = []

    async def claim_batch(self, **values):
        return self.claims

    async def mark_delivered(self, **values):
        self.delivered.append(values)
        return True

    async def mark_failed(self, **values):
        self.failed.append(values)
        return True


class FakeProvider:
    def __init__(self) -> None:
        self.calls = []

    async def send_verification_email(self, **values):
        self.calls.append(values)


class FakeAsyncClient:
    request = None

    def __init__(self, **values) -> None:
        self.values = values

    async def __aenter__(self):
        return self

    async def __aexit__(
        self,
        exc_type,
        exc,
        traceback,
    ):
        return None

    async def post(
        self,
        endpoint,
        *,
        headers,
        json,
    ):
        type(self).request = {
            "endpoint": endpoint,
            "headers": headers,
            "json": json,
        }
        return SimpleNamespace(status_code=202)


def _cipher():
    return DeliveryPayloadCipher(
        current_key_version="test-v1",
        keys={"test-v1": b"k" * 32},
    )


def _claim(
    *,
    event_type,
    purpose,
    user_status,
    recipient_email,
):
    cipher = _cipher()
    outbox_id = uuid.uuid4()
    user_id = uuid.uuid4()
    action_token_id = uuid.uuid4()
    encrypted = cipher.encrypt(
        "secret-action-token",
        outbox_id=str(outbox_id),
        user_id=str(user_id),
        action_token_id=str(action_token_id),
        purpose=purpose,
    )

    return DeliveryClaim(
        outbox_id=outbox_id,
        user_id=user_id,
        action_token_id=action_token_id,
        claim_id=uuid.uuid4(),
        recipient_email=recipient_email,
        user_status=user_status,
        event_type=event_type,
        payload_ciphertext=encrypted.ciphertext,
        payload_key_version=encrypted.key_version,
        action_token_expires_at=(
            NOW + timedelta(hours=1)
        ),
        action_token_consumed_at=None,
        action_token_invalidated_at=None,
        attempt_count=1,
    )


def _dispatcher(repository, provider):
    return DeliveryDispatcher(
        repository=repository,
        provider=provider,
        cipher=_cipher(),
        config=DeliveryDispatcherConfig(
            public_base_url=(
                "https://accounts.example.test"
            ),
            batch_size=10,
            lease_timeout=timedelta(minutes=5),
            max_attempts=3,
            retry_base=timedelta(seconds=30),
            retry_max=timedelta(minutes=10),
        ),
        clock=lambda: NOW,
    )


def test_primary_verification_contract_is_preserved():
    claim = _claim(
        event_type="verify_email",
        purpose="verify_email",
        user_status="pending_verification",
        recipient_email="primary@example.test",
    )
    repository = FakeRepository([claim])
    provider = FakeProvider()

    result = asyncio.run(
        _dispatcher(
            repository,
            provider,
        ).dispatch_once()
    )

    assert result.delivered == 1
    assert len(provider.calls) == 1
    assert provider.calls[0]["template"] == "verify_email"
    assert provider.calls[0]["recipient"] == (
        "primary@example.test"
    )
    assert provider.calls[0]["idempotency_key"] == (
        f"pmk-auth-delivery-v1:{claim.outbox_id}"
    )
    assert provider.calls[0][
        "verification_url"
    ].startswith(
        "https://accounts.example.test/"
        "verify-email?token="
    )


def test_recovery_verification_uses_recovery_contract():
    claim = _claim(
        event_type="verify_recovery_email",
        purpose="verify_recovery_email",
        user_status="active",
        recipient_email="recovery@example.test",
    )
    repository = FakeRepository([claim])
    provider = FakeProvider()

    result = asyncio.run(
        _dispatcher(
            repository,
            provider,
        ).dispatch_once()
    )

    assert result.delivered == 1
    assert result.dead_lettered == 0
    assert provider.calls[0]["template"] == (
        "verify_recovery_email"
    )
    assert provider.calls[0]["recipient"] == (
        "recovery@example.test"
    )
    assert provider.calls[0][
        "verification_url"
    ].startswith(
        "https://accounts.example.test/"
        "auth/recovery-email/verify?token="
    )
    assert "secret-action-token" not in repr(result)


@pytest.mark.parametrize(
    ("event_type", "user_status", "recipient", "error"),
    (
        (
            "verify_recovery_email",
            "pending_verification",
            "recovery@example.test",
            "user_ineligible",
        ),
        (
            "verify_recovery_email",
            "active",
            None,
            "recipient_unavailable",
        ),
        (
            "unknown_event",
            "active",
            "recovery@example.test",
            "event_type_invalid",
        ),
    ),
)
def test_ineligible_recovery_delivery_is_terminal(
    event_type,
    user_status,
    recipient,
    error,
):
    purpose = (
        event_type
        if event_type != "unknown_event"
        else "verify_recovery_email"
    )
    claim = _claim(
        event_type=event_type,
        purpose=purpose,
        user_status=user_status,
        recipient_email=recipient,
    )
    repository = FakeRepository([claim])
    provider = FakeProvider()

    result = asyncio.run(
        _dispatcher(
            repository,
            provider,
        ).dispatch_once()
    )

    assert result.dead_lettered == 1
    assert result.delivered == 0
    assert provider.calls == []
    assert repository.failed[0]["error_code"] == error
    assert repository.failed[0]["dead_lettered_at"] == NOW


def test_http_provider_emits_recovery_template(
    monkeypatch,
):
    from processual_api.auth import delivery_provider

    monkeypatch.setattr(
        delivery_provider.httpx,
        "AsyncClient",
        FakeAsyncClient,
    )

    provider = HttpEmailDeliveryProvider(
        endpoint="https://mail.example.test/send",
        bearer_token="t" * 32,
        timeout_seconds=5,
    )

    asyncio.run(
        provider.send_verification_email(
            template="verify_recovery_email",
            recipient="recovery@example.test",
            verification_url=(
                "https://accounts.example.test/"
                "auth/recovery-email/verify?token=value"
            ),
            idempotency_key="delivery-key",
        )
    )

    assert FakeAsyncClient.request is not None
    assert FakeAsyncClient.request["json"] == {
        "template": "verify_recovery_email",
        "recipient": "recovery@example.test",
        "verification_url": (
            "https://accounts.example.test/"
            "auth/recovery-email/verify?token=value"
        ),
    }


def test_http_provider_rejects_unknown_template():
    provider = HttpEmailDeliveryProvider(
        endpoint="https://mail.example.test/send",
        bearer_token="t" * 32,
        timeout_seconds=5,
    )

    with pytest.raises(ValueError):
        asyncio.run(
            provider.send_verification_email(
                template="unknown",
                recipient="person@example.test",
                verification_url=(
                    "https://accounts.example.test/"
                    "verify?token=value"
                ),
                idempotency_key="delivery-key",
            )
        )
