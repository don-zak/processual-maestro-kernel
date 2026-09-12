from __future__ import annotations

import asyncio
import base64
from email import policy
from email.parser import BytesParser

import httpx
import pytest

import processual_api.auth.delivery_provider as provider_module
from processual_api.auth.delivery_provider import (
    DeliveryProviderError,
    GMAIL_OAUTH_TOKEN_ENDPOINT,
    GMAIL_SEND_ENDPOINT,
    GmailApiDeliveryProvider,
)

CLIENT_ID = "gmail-client-id.apps.googleusercontent.com"
CLIENT_SECRET = "gmail-client-secret-value"
REFRESH_TOKEN = "refresh-token-" + "r" * 40
SENDER = "maestro.sender@gmail.com"
RECIPIENT = "recovery@example.test"
RECOVERY_URL = "https://accounts.example.test/auth/account-recovery/verify?token=secret-token"


class GmailRecordingClient:
    def __init__(self, *, token_status=200, send_status=200, token_payload=None):
        self.token_status = token_status
        self.send_status = send_status
        self.token_payload = token_payload or {
            "access_token": "access-token-value",
            "token_type": "Bearer",
        }
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def post(self, url, *, headers, data=None, json=None):
        self.calls.append(
            {"url": url, "headers": headers, "data": data, "json": json}
        )
        if url == GMAIL_OAUTH_TOKEN_ENDPOINT:
            return httpx.Response(
                self.token_status,
                json=self.token_payload,
                request=httpx.Request("POST", url),
            )
        return httpx.Response(
            self.send_status,
            json={"id": "gmail-message-id"},
            request=httpx.Request("POST", url),
        )


def _provider() -> GmailApiDeliveryProvider:
    return GmailApiDeliveryProvider(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        refresh_token=REFRESH_TOKEN,
        sender_email=SENDER,
        timeout_seconds=10,
    )


def _send(provider):
    return provider.send_verification_email(
        template="account_recovery_verification",
        recipient=RECIPIENT,
        verification_url=RECOVERY_URL,
        idempotency_key="pmk-auth-delivery-v1:outbox-id",
    )


def test_gmail_provider_refreshes_oauth_and_sends_rfc822_message(monkeypatch):
    client = GmailRecordingClient()
    monkeypatch.setattr(
        provider_module.httpx,
        "AsyncClient",
        lambda **kwargs: client,
    )

    asyncio.run(_send(_provider()))

    assert [call["url"] for call in client.calls] == [
        GMAIL_OAUTH_TOKEN_ENDPOINT,
        GMAIL_SEND_ENDPOINT,
    ]
    token_call = client.calls[0]
    assert token_call["data"] == {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": REFRESH_TOKEN,
        "grant_type": "refresh_token",
    }

    send_call = client.calls[1]
    assert send_call["headers"]["Authorization"] == "Bearer access-token-value"
    raw = send_call["json"]["raw"]
    padding = "=" * (-len(raw) % 4)
    parsed = BytesParser(policy=policy.default).parsebytes(
        base64.urlsafe_b64decode(raw + padding)
    )
    assert parsed["From"] == SENDER
    assert parsed["To"] == RECIPIENT
    assert parsed["Subject"] == "Recover your Processual Maestro account"
    assert RECOVERY_URL in parsed.get_body(preferencelist=("plain",)).get_content()


@pytest.mark.parametrize(
    ("token_status", "error_code", "retryable"),
    (
        (400, "provider_oauth_rejected", False),
        (401, "provider_oauth_rejected", False),
        (429, "provider_rate_limited", True),
        (500, "provider_5xx", True),
    ),
)
def test_gmail_oauth_failures_are_classified_without_secret_leakage(
    monkeypatch,
    token_status,
    error_code,
    retryable,
):
    client = GmailRecordingClient(token_status=token_status)
    monkeypatch.setattr(provider_module.httpx, "AsyncClient", lambda **kwargs: client)

    with pytest.raises(DeliveryProviderError) as captured:
        asyncio.run(_send(_provider()))

    assert captured.value.error_code == error_code
    assert captured.value.retryable is retryable
    text = repr(captured.value)
    assert CLIENT_SECRET not in text
    assert REFRESH_TOKEN not in text
    assert RECOVERY_URL not in text
    assert RECIPIENT not in text


@pytest.mark.parametrize(
    ("send_status", "error_code", "retryable"),
    (
        (400, "provider_4xx", False),
        (408, "provider_timeout", True),
        (429, "provider_rate_limited", True),
        (503, "provider_5xx", True),
    ),
)
def test_gmail_send_failures_are_classified(monkeypatch, send_status, error_code, retryable):
    client = GmailRecordingClient(send_status=send_status)
    monkeypatch.setattr(provider_module.httpx, "AsyncClient", lambda **kwargs: client)

    with pytest.raises(DeliveryProviderError) as captured:
        asyncio.run(_send(_provider()))

    assert captured.value.error_code == error_code
    assert captured.value.retryable is retryable


def test_gmail_provider_rejects_invalid_sender_and_short_oauth_material():
    with pytest.raises(ValueError):
        GmailApiDeliveryProvider(
            client_id="short",
            client_secret=CLIENT_SECRET,
            refresh_token=REFRESH_TOKEN,
            sender_email=SENDER,
            timeout_seconds=10,
        )
    with pytest.raises(ValueError):
        GmailApiDeliveryProvider(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            refresh_token=REFRESH_TOKEN,
            sender_email="invalid sender",
            timeout_seconds=10,
        )
