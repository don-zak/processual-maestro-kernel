from __future__ import annotations

import asyncio

import httpx
import pytest

import processual_api.auth.delivery_provider as provider_module
from processual_api.auth.delivery_provider import (
    DeliveryProviderError,
    HttpEmailDeliveryProvider,
)


class RecordingAsyncClient:
    def __init__(
        self,
        *,
        timeout,
        follow_redirects,
        response_status=202,
        request_error=None,
    ) -> None:
        self.timeout = timeout
        self.follow_redirects = follow_redirects
        self.response_status = response_status
        self.request_error = request_error
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(
        self,
        exc_type,
        exc,
        traceback,
    ):
        return False

    async def post(
        self,
        endpoint,
        *,
        headers,
        json,
    ):
        self.calls.append(
            {
                "endpoint": endpoint,
                "headers": headers,
                "json": json,
            }
        )

        if self.request_error is not None:
            raise self.request_error

        return httpx.Response(
            self.response_status,
            request=httpx.Request(
                "POST",
                endpoint,
            ),
        )


def _provider():
    return HttpEmailDeliveryProvider(
        endpoint="https://provider.example.test/send",
        bearer_token="p" * 32,
        timeout_seconds=7.5,
    )


def _send(provider):
    return provider.send_verification_email(
        template="account_recovery_verification",
        recipient="recovery@example.test",
        verification_url=(
            "https://accounts.example.test/"
            "auth/account-recovery/verify?token=secret"
        ),
        idempotency_key="pmk-auth-delivery-v1:outbox-id",
    )


def test_http_provider_sends_bounded_authenticated_request(
    monkeypatch,
):
    client = RecordingAsyncClient(
        timeout=7.5,
        follow_redirects=False,
    )

    def build_client(**values):
        assert values == {
            "timeout": 7.5,
            "follow_redirects": False,
        }

        return client

    monkeypatch.setattr(
        provider_module.httpx,
        "AsyncClient",
        build_client,
    )

    asyncio.run(_send(_provider()))

    assert len(client.calls) == 1

    call = client.calls[0]

    assert call["endpoint"] == (
        "https://provider.example.test/send"
    )
    assert call["headers"] == {
        "Authorization": f"Bearer {'p' * 32}",
        "Idempotency-Key": (
            "pmk-auth-delivery-v1:outbox-id"
        ),
    }
    assert call["json"] == {
        "template": "account_recovery_verification",
        "recipient": "recovery@example.test",
        "verification_url": (
            "https://accounts.example.test/"
            "auth/account-recovery/verify?token=secret"
        ),
    }


@pytest.mark.parametrize(
    ("status_code", "error_code", "retryable"),
    (
        (400, "provider_4xx", False),
        (401, "provider_4xx", False),
        (408, "provider_timeout", True),
        (429, "provider_rate_limited", True),
        (500, "provider_5xx", True),
        (503, "provider_5xx", True),
    ),
)
def test_http_provider_classifies_response_failures(
    monkeypatch,
    status_code,
    error_code,
    retryable,
):
    client = RecordingAsyncClient(
        timeout=7.5,
        follow_redirects=False,
        response_status=status_code,
    )

    monkeypatch.setattr(
        provider_module.httpx,
        "AsyncClient",
        lambda **values: client,
    )

    with pytest.raises(DeliveryProviderError) as captured:
        asyncio.run(_send(_provider()))

    assert captured.value.error_code == error_code
    assert captured.value.retryable is retryable

    failure_text = repr(captured.value)

    assert "recovery@example.test" not in failure_text
    assert "token=secret" not in failure_text
    assert ("p" * 32) not in failure_text


@pytest.mark.parametrize(
    ("exception_factory", "error_code"),
    (
        (
            lambda request: httpx.ReadTimeout(
                "provider timed out",
                request=request,
            ),
            "provider_timeout",
        ),
        (
            lambda request: httpx.ConnectError(
                "provider unavailable",
                request=request,
            ),
            "provider_network",
        ),
    ),
)
def test_http_provider_classifies_transport_failures(
    monkeypatch,
    exception_factory,
    error_code,
):
    request = httpx.Request(
        "POST",
        "https://provider.example.test/send",
    )

    client = RecordingAsyncClient(
        timeout=7.5,
        follow_redirects=False,
        request_error=exception_factory(request),
    )

    monkeypatch.setattr(
        provider_module.httpx,
        "AsyncClient",
        lambda **values: client,
    )

    with pytest.raises(DeliveryProviderError) as captured:
        asyncio.run(_send(_provider()))

    assert captured.value.error_code == error_code
    assert captured.value.retryable is True


def test_http_provider_rejects_unknown_template_before_network(
    monkeypatch,
):
    client_created = False

    def create_client(**values):
        nonlocal client_created
        client_created = True

        return RecordingAsyncClient(
            timeout=7.5,
            follow_redirects=False,
        )

    monkeypatch.setattr(
        provider_module.httpx,
        "AsyncClient",
        create_client,
    )

    provider = _provider()

    with pytest.raises(
        ValueError,
        match="template is invalid",
    ):
        asyncio.run(
            provider.send_verification_email(
                template="unapproved-template",
                recipient="recovery@example.test",
                verification_url=(
                    "https://accounts.example.test/"
                    "auth/account-recovery/verify?token=secret"
                ),
                idempotency_key=(
                    "pmk-auth-delivery-v1:outbox-id"
                ),
            )
        )

    assert client_created is False
