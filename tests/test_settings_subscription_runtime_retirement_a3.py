from __future__ import annotations

import inspect
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute

from processual_api.routers import settings_router
from processual_api.routers import settings_subscription_runtime as runtime_route


def _subscription_routes() -> list[APIRoute]:
    return [
        route
        for route in settings_router.routes
        if isinstance(route, APIRoute)
        and route.path == "/settings/subscription"
        and "GET" in route.methods
    ]


def test_settings_subscription_route_is_registered_once_from_runtime_source() -> None:
    routes = _subscription_routes()
    assert len(routes) == 1
    assert routes[0].endpoint is runtime_route.get_runtime_subscription

    source = inspect.getsource(routes[0].endpoint)
    assert "resolve_subscription_access" in source
    assert "subscriptions.json" not in source
    assert "_load_billing_subscriptions" not in source
    assert "_compute_stage" not in source


@pytest.mark.asyncio
async def test_runtime_subscription_maps_authoritative_snapshot(monkeypatch) -> None:
    customer_id = uuid.uuid4()
    snapshot = SimpleNamespace(
        entitlement_profile_ref="professional",
        access_stage="grace",
        grace_until=None,
        effective_at=None,
    )

    async def fake_resolver(customer_ref: str):
        assert customer_ref == str(customer_id)
        return snapshot

    monkeypatch.setattr(runtime_route, "resolve_subscription_access", fake_resolver)
    result = await runtime_route.get_runtime_subscription({"user_id": str(customer_id)})

    assert result.plan == "professional"
    assert result.status == "grace"
    assert result.stage == "grace"


@pytest.mark.asyncio
async def test_runtime_subscription_missing_or_failure_is_fail_closed(monkeypatch) -> None:
    customer_id = uuid.uuid4()

    async def missing(_customer_ref: str):
        return None

    monkeypatch.setattr(runtime_route, "resolve_subscription_access", missing)
    result = await runtime_route.get_runtime_subscription({"user_id": str(customer_id)})
    assert result.status == "inactive"
    assert result.stage == "expired"

    async def failing(_customer_ref: str):
        raise RuntimeError("database connection details")

    monkeypatch.setattr(runtime_route, "resolve_subscription_access", failing)
    with pytest.raises(HTTPException) as captured:
        await runtime_route.get_runtime_subscription({"user_id": str(customer_id)})
    assert captured.value.status_code == 503
    assert "database" not in str(captured.value.detail).lower()


def test_invalid_identity_is_rejected_before_runtime_lookup() -> None:
    with pytest.raises(HTTPException) as captured:
        runtime_route._customer_ref({"user_id": "not-a-uuid"})
    assert captured.value.status_code == 403
