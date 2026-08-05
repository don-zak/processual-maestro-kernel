from __future__ import annotations

import inspect

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute
from starlette.requests import Request

from processual_api.admin_marketplace import lemon_squeezy_secure_webhook_router as transport
from processual_api.billing.router import router as billing_router


def _request(*, body: bytes = b"{}", headers: dict[str, str] | None = None) -> Request:
    sent = False

    async def receive():
        nonlocal sent
        if sent:
            return {"type": "http.request", "body": b"", "more_body": False}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    raw_headers = [
        (key.lower().encode("latin-1"), value.encode("latin-1"))
        for key, value in (headers or {}).items()
    ]
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/billing/webhook",
            "headers": raw_headers,
        },
        receive,
    )


def test_legacy_webhook_route_is_replaced_not_duplicated() -> None:
    routes = [
        route
        for route in billing_router.routes
        if isinstance(route, APIRoute)
        and route.path == "/billing/webhook"
        and "POST" in route.methods
    ]
    assert len(routes) == 1
    assert routes[0].endpoint is transport.secure_lemon_squeezy_webhook
    source = inspect.getsource(routes[0].endpoint)
    assert "_save_subscriptions" not in source
    assert "send_billing_alert" not in source


@pytest.mark.asyncio
async def test_missing_configuration_fails_closed_before_ingestion(monkeypatch) -> None:
    monkeypatch.delenv("LEMONSQUEEZY_WEBHOOK_SECRET", raising=False)
    monkeypatch.delenv("LEMONSQUEEZY_STORE_ID", raising=False)

    with pytest.raises(HTTPException) as captured:
        await transport.secure_lemon_squeezy_webhook(_request())

    assert captured.value.status_code == 503
    assert captured.value.detail == "Webhook processing is unavailable."


@pytest.mark.asyncio
async def test_declared_or_actual_oversized_body_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("LEMONSQUEEZY_WEBHOOK_SECRET", "secret")
    monkeypatch.setenv("LEMONSQUEEZY_STORE_ID", "42")

    with pytest.raises(HTTPException) as declared:
        await transport.secure_lemon_squeezy_webhook(
            _request(headers={"content-length": str(transport._MAX_BODY_BYTES + 1)})
        )
    assert declared.value.status_code == 413

    with pytest.raises(HTTPException) as actual:
        await transport.secure_lemon_squeezy_webhook(
            _request(body=b"x" * (transport._MAX_BODY_BYTES + 1))
        )
    assert actual.value.status_code == 413


@pytest.mark.asyncio
async def test_verification_errors_are_sanitized(monkeypatch) -> None:
    monkeypatch.setenv("LEMONSQUEEZY_WEBHOOK_SECRET", "secret")
    monkeypatch.setenv("LEMONSQUEEZY_STORE_ID", "42")

    with pytest.raises(HTTPException) as captured:
        await transport.secure_lemon_squeezy_webhook(
            _request(
                headers={
                    "X-Signature": "bad",
                    "X-Event-Name": "order_created",
                }
            )
        )

    assert captured.value.status_code == 400
    assert captured.value.detail == "Invalid webhook request."
    assert "signature" not in captured.value.detail.lower()
