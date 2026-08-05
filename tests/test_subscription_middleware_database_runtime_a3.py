from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest
from starlette.requests import Request
from starlette.responses import Response

from processual_api.middleware import subscription as middleware_module
from processual_api.middleware.subscription import SubscriptionMiddleware


def _request(*, method: str = "GET", path: str = "/workflows", authenticated: bool = True) -> Request:
    headers = []
    if authenticated:
        headers.append((b"authorization", b"Bearer token"))
    return Request(
        {
            "type": "http",
            "method": method,
            "path": path,
            "headers": headers,
            "query_string": b"",
            "scheme": "https",
            "server": ("test", 443),
            "client": ("127.0.0.1", 1),
        }
    )


async def _next(_: Request) -> Response:
    return Response("ok", status_code=200)


def _middleware() -> SubscriptionMiddleware:
    return SubscriptionMiddleware(app=lambda scope, receive, send: None)


@pytest.mark.asyncio
async def test_active_runtime_allows_request(monkeypatch) -> None:
    monkeypatch.setattr(middleware_module, "_extract_customer_ref", lambda request: "customer-1")

    async def resolve(customer_ref):
        assert customer_ref == "customer-1"
        return SimpleNamespace(access_stage="active")

    monkeypatch.setattr(middleware_module, "resolve_subscription_access", resolve)

    response = await _middleware().dispatch(_request(), _next)

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_grace_is_read_only(monkeypatch) -> None:
    monkeypatch.setattr(middleware_module, "_extract_customer_ref", lambda request: "customer-1")

    async def resolve(customer_ref):
        return SimpleNamespace(access_stage="grace")

    monkeypatch.setattr(middleware_module, "resolve_subscription_access", resolve)

    read_response = await _middleware().dispatch(_request(method="GET"), _next)
    write_response = await _middleware().dispatch(_request(method="POST"), _next)

    assert read_response.status_code == 200
    assert write_response.status_code == 403
    assert b'"subscription_stage": "grace"' in write_response.body


@pytest.mark.asyncio
async def test_suspended_only_allows_billing_and_terminated_blocks_all(monkeypatch) -> None:
    monkeypatch.setattr(middleware_module, "_extract_customer_ref", lambda request: "customer-1")
    stage = "suspended"

    async def resolve(customer_ref):
        return SimpleNamespace(access_stage=stage)

    monkeypatch.setattr(middleware_module, "resolve_subscription_access", resolve)

    blocked = await _middleware().dispatch(_request(path="/workflows"), _next)
    billing = await _middleware().dispatch(_request(path="/billing/portal"), _next)
    assert blocked.status_code == 403
    assert billing.status_code == 200

    stage = "terminated"
    terminated = await _middleware().dispatch(_request(path="/billing/portal"), _next)
    assert terminated.status_code == 403
    assert b'"subscription_stage": "terminated"' in terminated.body


@pytest.mark.asyncio
async def test_runtime_lookup_failure_is_fail_closed(monkeypatch) -> None:
    monkeypatch.setattr(middleware_module, "_extract_customer_ref", lambda request: "customer-1")

    async def resolve(customer_ref):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(middleware_module, "resolve_subscription_access", resolve)

    response = await _middleware().dispatch(_request(), _next)

    assert response.status_code == 503
    assert b"database" not in response.body.lower()
    assert b'"subscription_stage": "unavailable"' in response.body


@pytest.mark.asyncio
async def test_public_and_unauthenticated_requests_do_not_open_runtime_lookup(monkeypatch) -> None:
    calls = 0

    async def resolve(customer_ref):
        nonlocal calls
        calls += 1
        return None

    monkeypatch.setattr(middleware_module, "resolve_subscription_access", resolve)
    monkeypatch.setattr(middleware_module, "_extract_customer_ref", lambda request: None)

    public = await _middleware().dispatch(_request(path="/billing/webhook"), _next)
    unauthenticated = await _middleware().dispatch(_request(authenticated=False), _next)

    assert public.status_code == 200
    assert unauthenticated.status_code == 200
    assert calls == 0


def test_middleware_has_no_json_subscription_file_fallback() -> None:
    source = inspect.getsource(middleware_module)

    assert "subscriptions.json" not in source
    assert "_load_subscriptions" not in source
    assert "_compute_stage" not in source
    assert "Path(" not in source
