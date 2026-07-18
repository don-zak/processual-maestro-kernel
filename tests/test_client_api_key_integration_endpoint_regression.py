from __future__ import annotations

import asyncio

from fastapi.routing import APIRoute

from processual_api.routers import settings as settings_router


def test_api_key_integration_route_is_registered() -> None:
    paths = {
        route.path
        for route in settings_router.router.routes
        if isinstance(route, APIRoute)
    }

    assert "/settings/api-key-integration" in paths


def test_api_key_integration_is_locked_for_non_enterprise_plan(monkeypatch) -> None:
    monkeypatch.setattr(settings_router, "_load_billing_subscriptions", lambda: [])
    monkeypatch.setattr(
        settings_router,
        "_load_raw",
        lambda user_id: {
            "subscription": {
                "plan_id": "starter",
            },
            "api_keys": [],
        },
    )

    result = asyncio.run(
        settings_router.get_api_key_integration({
            "sub": "client-a",
            "user_id": "client-a",
            "client_id": "client-a",
            "role": "client",
        })
    )

    assert result["enabled"] is False
    assert result["status"] == "locked"
    assert result["plan_id"] == "starter"
    assert result["keys"] == []
    assert result["key_count"] == 0


def test_api_key_integration_is_enabled_for_enterprise_integration_plan(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings_router, "_load_billing_subscriptions", lambda: [])
    monkeypatch.setattr(
        settings_router,
        "_load_raw",
        lambda user_id: {
            "subscription": {
                "plan_id": "enterprise_integration",
            },
            "api_keys": [
                {
                    "id": "key-a",
                    "prefix": "pmk_safe...",
                    "hashed": "secret-hash",
                    "api_key": "pmk_raw_secret",
                    "client_id": "client-a",
                    "status": "enabled",
                    "scopes": ["read:health", "run:govern"],
                    "quota_limit": 500000,
                    "quota_used": 12,
                    "quota_rejected_count": 1,
                    "last_used_at": "2026-07-03T10:00:00+00:00",
                },
                {
                    "id": "key-revoked",
                    "prefix": "pmk_old...",
                    "client_id": "client-a",
                    "status": "revoked",
                    "revoked_at": "2026-07-03T10:00:00+00:00",
                },
            ],
        },
    )

    result = asyncio.run(
        settings_router.get_api_key_integration({
            "sub": "client-a",
            "user_id": "client-a",
            "client_id": "client-a",
            "role": "client",
        })
    )

    assert result["enabled"] is True
    assert result["status"] == "available"
    assert result["plan_id"] == "enterprise_integration"
    assert result["key_count"] == 1

    key = result["keys"][0]
    assert key["key_id"] == "key-a"
    assert key["prefix"] == "pmk_safe..."
    assert key["quota_limit"] == 500000
    assert key["quota_used"] == 12
    assert key["quota_remaining"] == 499988
    assert "hashed" not in key
    assert "api_key" not in key
    assert "hashed_key" not in key


def test_api_key_integration_accepts_legacy_enterprise_private_plan(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings_router, "_load_billing_subscriptions", lambda: [])
    monkeypatch.setattr(
        settings_router,
        "_load_raw",
        lambda user_id: {
            "subscription": {
                "plan_id": "enterprise_private",
            },
            "api_keys": [],
        },
    )

    result = asyncio.run(
        settings_router.get_api_key_integration({
            "sub": "client-a",
            "user_id": "client-a",
            "client_id": "client-a",
            "role": "client",
        })
    )

    assert result["enabled"] is True
    assert result["plan_id"] == "enterprise_private"
    assert "enterprise_private" in result["eligible_plans"]
