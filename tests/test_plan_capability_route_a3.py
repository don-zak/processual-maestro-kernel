from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute

from processual_api.billing import router as billing_router
from processual_api.billing.plan_capability_router import get_plan_capabilities


SAFE_CAPABILITY_FIELDS = {
    "capability_code",
    "entitlement_code",
    "status",
    "execution_surface",
    "customer_executable",
    "production_allowed",
    "notes",
}
SENSITIVE_CAPABILITY_FIELDS = {
    "credential_value",
    "secret",
    "api_key",
    "token",
    "authorization",
}


def test_plan_capability_route_is_registered() -> None:
    paths = {
        route.path
        for route in billing_router.router.routes
        if isinstance(route, APIRoute)
    }

    assert "/billing/plan-capabilities/{plan_code}" in paths


def test_plan_capability_route_returns_safe_enterprise_boundary() -> None:
    payload = asyncio.run(get_plan_capabilities("enterprise_scale"))

    assert payload["plan_code"] == "enterprise_scale"
    assert payload["production_advanced_integration_allowed"] is False

    capabilities = payload["capabilities"]
    assert isinstance(capabilities, list)
    for item in capabilities:
        assert isinstance(item, dict)
        assert set(item) == SAFE_CAPABILITY_FIELDS
        assert SENSITIVE_CAPABILITY_FIELDS.isdisjoint(item)


def test_plan_capability_route_rejects_unknown_plan() -> None:
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(get_plan_capabilities("not_a_plan"))

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Unknown plan."
