from __future__ import annotations

import asyncio

import httpx
import pytest

import processual_api.auth.delivery_provider as provider_module
from processual_api.auth.delivery_provider import (
    DeliveryProviderError,
    RESEND_SEND_ENDPOINT,
    ResendDeliveryProvider,
)

API_KEY = "resend-key-" + "r" * 32
SENDER = "recovery@maestro.example"
RECIPIENT = "recovery@example.test"
RECOVERY_URL = "https://accounts.example.test/auth/account-recovery/verify?token=secret-token"
IDEMPOTENCY_KEY = "pmk-auth-delivery-v1:outbox-id"


class ResendRecordingClient:
    def __init__(self, *, status=200):
        self.status = status
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def post(self, url, *, headers, json):
        self.calls.append({"url": url, "headers": headers, "json": json})
        return httpx.Response(
            self.status,
            json={"id": "resend-message-id"},
            request=httpx.Request("POST", url),
        )


def _provider() -> ResendDeliveryProvider:
    return ResendDeliveryProvider(
        api_key=API_KEY,
        sender_email=SENDER,
        timeout_seconds=10,
    )


def _send(provider):
    return provider.send_verification_email(
        template="account_recovery_verification",
        recipient=RECIPIENT,
        verification_url=RECOVERY_URL,
        idempotency_key=IDEMPOTENCY_KEY,
    )


def test_resend_provider_sends_transactional_email_with_idempotency(monkeypatch):
    client = ResendRecordingClient()
    monkeypatch.setattr(provider_module.httpx, "AsyncClient", lambda **kwargs: client)

    asyncio.run(_send(_provider()))

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["url"] == RESEND_SEND_ENDPOINT
    assert call["headers"]["Authorization"] == f"Bearer {API_KEY}"
    assert call["headers"]["Idempotency-Key"] == IDEMPOTENCY_KEY
    assert call["json"]["from"] == SENDER
    assert call["json"]["to"] == [RECIPIENT]
    assert call["json"]["subject"] == "Recover your Processual Maestro account"
    assert RECOVERY_URL in call["json"]["text"]


@pytest.mark.parametrize(
    ("status", "error_code", "retryable"),
    (
        (400, "provider_4xx", False),
        (401, "provider_4xx", False),
        (408, "provider_timeout", True),
        (429, "provider_rate_limited", True),
        (500, "provider_5xx", True),
        (503, "provider_5xx", True),
    ),
)
def test_resend_failures_are_classified_without_secret_leakage(
    monkeypatch,
    status,
    error_code,
    retryable,
):
    client = ResendRecordingClient(status=status)
    monkeypatch.setattr(provider_module.httpx, "AsyncClient", lambda **kwargs: client)

    with pytest.raises(DeliveryProviderError) as captured:
        asyncio.run(_send(_provider()))

    assert captured.value.error_code == error_code
    assert captured.value.retryable is retryable
    text = repr(captured.value)
    assert API_KEY not in text
    assert RECOVERY_URL not in text
    assert RECIPIENT not in text


def test_resend_provider_rejects_short_key_invalid_sender_and_unsafe_timeout():
    with pytest.raises(ValueError):
        ResendDeliveryProvider(
            api_key="short",
            sender_email=SENDER,
            timeout_seconds=10,
        )
    with pytest.raises(ValueError):
        ResendDeliveryProvider(
            api_key=API_KEY,
            sender_email="invalid sender",
            timeout_seconds=10,
        )
    with pytest.raises(ValueError):
        ResendDeliveryProvider(
            api_key=API_KEY,
            sender_email=SENDER,
            timeout_seconds=0,
        )
