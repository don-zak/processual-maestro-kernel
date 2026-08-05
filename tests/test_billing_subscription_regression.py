from __future__ import annotations

import asyncio
import inspect
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.routing import APIRoute

import processual_api.billing.router as billing_router

ROOT = Path(__file__).resolve().parents[1]


def _routes(path: str, method: str) -> list[APIRoute]:
    return [
        route
        for route in billing_router.router.routes
        if isinstance(route, APIRoute)
        and route.path == path
        and method in route.methods
    ]


def test_billing_router_keeps_public_contracts_without_legacy_storage() -> None:
    expected = {
        ("POST", "/billing/checkout"),
        ("GET", "/billing/portal"),
        ("POST", "/billing/webhook"),
        ("GET", "/billing/subscription"),
        ("GET", "/billing/subscription-preparation"),
        ("GET", "/billing/public-plan-journey"),
        ("GET", "/billing/pricing-catalog"),
        ("GET", "/billing/offer-pricebook"),
        ("GET", "/billing/unit-cost-assumptions"),
    }
    actual = {
        (method, route.path)
        for route in billing_router.router.routes
        if isinstance(route, APIRoute)
        for method in route.methods
        if method in {"GET", "POST"}
    }
    assert expected <= actual
    assert len(_routes("/billing/webhook", "POST")) == 1

    source = inspect.getsource(billing_router)
    forbidden = (
        "subscriptions.json",
        "checkouts.json",
        "_load_subscriptions",
        "_save_subscriptions",
        "_load_checkouts",
        "_save_checkouts",
        "lemon_squeezy_webhook(request",
    )
    for marker in forbidden:
        assert marker not in source


def test_billing_subscription_reads_authoritative_runtime(monkeypatch) -> None:
    snapshot = SimpleNamespace(
        subscription_id="00000000-0000-0000-0000-000000000001",
        entitlement_profile_ref="professional",
        access_stage="active",
        grace_until=None,
    )
    resolver = AsyncMock(return_value=snapshot)
    monkeypatch.setattr(billing_router, "resolve_subscription_access", resolver)

    response = asyncio.run(
        billing_router.get_billing_subscription(
            {"sub": "00000000-0000-0000-0000-000000000002"}
        )
    )

    resolver.assert_awaited_once_with("00000000-0000-0000-0000-000000000002")
    assert response == {
        "subscription_id": "00000000-0000-0000-0000-000000000001",
        "plan": "professional",
        "status": "active",
        "renews_at": None,
        "billing_provider": "lemonsqueezy",
        "has_subscription": True,
    }


def test_billing_subscription_missing_runtime_is_inactive(monkeypatch) -> None:
    monkeypatch.setattr(
        billing_router,
        "resolve_subscription_access",
        AsyncMock(return_value=None),
    )
    response = asyncio.run(
        billing_router.get_billing_subscription(
            {"sub": "00000000-0000-0000-0000-000000000003"}
        )
    )
    assert response["has_subscription"] is False
    assert response["status"] == "inactive"
    assert response["plan"] is None


def test_billing_subscription_lookup_failure_is_fail_closed(monkeypatch) -> None:
    monkeypatch.setattr(
        billing_router,
        "resolve_subscription_access",
        AsyncMock(side_effect=RuntimeError("database detail")),
    )
    with pytest.raises(Exception) as captured:
        asyncio.run(
            billing_router.get_billing_subscription(
                {"sub": "00000000-0000-0000-0000-000000000004"}
            )
        )
    assert getattr(captured.value, "status_code", None) == 503
    assert "database detail" not in str(getattr(captured.value, "detail", ""))


def test_billing_package_is_side_effect_free() -> None:
    package_source = (
        ROOT / "processual_api" / "billing" / "__init__.py"
    ).read_text(encoding="utf-8")
    assert "import_module" not in package_source
    assert "billing_router" not in package_source
