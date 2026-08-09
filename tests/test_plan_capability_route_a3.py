from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute

from processual_api.billing import router as billing_router
from processual_api.billing.plan_capability_router import get_plan_capabilities


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
    assert all("credential" not in str(item).lower() for item in payload["capabilities"])
    assert all("secret" not in str(item).lower() for item in payload["capabilities"])


def test_plan_capability_route_rejects_unknown_plan() -> None:
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(get_plan_capabilities("not_a_plan"))

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Unknown plan."
