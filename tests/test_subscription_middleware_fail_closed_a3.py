from __future__ import annotations

from dataclasses import dataclass

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

import processual_api.middleware.subscription as subscription_module


@dataclass
class _Access:
    access_stage: str


async def _ok_endpoint(request):
    return JSONResponse({"ok": True})


def _client(monkeypatch, access):
    async def resolve(customer_ref: str):
        assert customer_ref == "customer-1"
        if isinstance(access, Exception):
            raise access
        return access

    monkeypatch.setattr(subscription_module, "resolve_subscription_access", resolve)
    monkeypatch.setattr(
        subscription_module,
        "_extract_customer_ref",
        lambda request: "customer-1",
    )

    app = Starlette(routes=[Route("/protected", _ok_endpoint, methods=["GET", "POST"])])
    app.add_middleware(subscription_module.SubscriptionMiddleware)
    return TestClient(app)


def test_auth_namespace_is_exempt_from_subscription_gating(monkeypatch) -> None:
    async def auth_endpoint(request):
        return JSONResponse({"auth": True})

    async def resolve(customer_ref: str):
        raise AssertionError("subscription lookup must not run for /auth/*")

    monkeypatch.setattr(subscription_module, "resolve_subscription_access", resolve)
    monkeypatch.setattr(
        subscription_module,
        "_extract_customer_ref",
        lambda request: "customer-1",
    )

    app = Starlette(
        routes=[Route("/auth/future-route", auth_endpoint, methods=["POST"])]
    )
    app.add_middleware(subscription_module.SubscriptionMiddleware)

    response = TestClient(app).post("/auth/future-route")

    assert response.status_code == 200
    assert response.json() == {"auth": True}


def test_missing_subscription_access_is_denied(monkeypatch) -> None:
    response = _client(monkeypatch, None).get("/protected")

    assert response.status_code == 403
    assert response.json() == {
        "detail": "No active subscription access record was found.",
        "subscription_stage": "inactive",
    }


def test_subscription_lookup_failure_is_fail_closed(monkeypatch) -> None:
    response = _client(monkeypatch, RuntimeError("database unavailable")).get(
        "/protected"
    )

    assert response.status_code == 503
    assert response.json()["subscription_stage"] == "unavailable"
    assert "database unavailable" not in response.text


def test_active_subscription_allows_request(monkeypatch) -> None:
    response = _client(monkeypatch, _Access("active")).get("/protected")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_grace_subscription_is_read_only(monkeypatch) -> None:
    client = _client(monkeypatch, _Access("grace"))

    assert client.get("/protected").status_code == 200
    denied = client.post("/protected")
    assert denied.status_code == 403
    assert denied.json()["subscription_stage"] == "grace"


def test_suspended_subscription_only_allows_billing(monkeypatch) -> None:
    async def billing_endpoint(request):
        return JSONResponse({"billing": True})

    async def resolve(customer_ref: str):
        return _Access("suspended")

    monkeypatch.setattr(subscription_module, "resolve_subscription_access", resolve)
    monkeypatch.setattr(
        subscription_module,
        "_extract_customer_ref",
        lambda request: "customer-1",
    )

    app = Starlette(
        routes=[
            Route("/protected", _ok_endpoint),
            Route("/billing/portal", billing_endpoint),
        ]
    )
    app.add_middleware(subscription_module.SubscriptionMiddleware)
    client = TestClient(app)

    assert client.get("/protected").status_code == 403
    assert client.get("/billing/portal").status_code == 200


def test_terminated_and_unknown_stages_are_denied(monkeypatch) -> None:
    terminated = _client(monkeypatch, _Access("terminated")).get("/protected")
    unknown = _client(monkeypatch, _Access("unexpected")).get("/protected")

    assert terminated.status_code == 403
    assert terminated.json()["subscription_stage"] == "terminated"
    assert unknown.status_code == 503
    assert unknown.json()["subscription_stage"] == "unavailable"
