from __future__ import annotations

import asyncio

from fastapi.routing import APIRoute

from processual_api.routers import settings as settings_router


def test_provider_connection_route_is_registered() -> None:
    paths = {
        route.path
        for route in settings_router.router.routes
        if isinstance(route, APIRoute)
    }

    assert "/settings/provider-connection" in paths


def test_provider_connection_returns_client_safe_empty_status(monkeypatch) -> None:
    monkeypatch.setattr(settings_router, "provider_ids", lambda: ["openai", "opencode"])
    monkeypatch.setattr(settings_router, "_load_raw", lambda user_id: {})

    result = asyncio.run(
        settings_router.get_provider_connection({
            "sub": "client-a",
            "user_id": "client-a",
            "client_id": "client-a",
            "role": "client",
        })
    )

    assert result["configured"] is False
    assert result["status"] == "not_configured"
    assert result["provider"] == ""
    assert result["model"] == ""
    assert result["provider_cost_included"] is False
    assert result["billing_policy"] == "byok"
    assert result["available_providers"] == ["openai", "opencode"]


def test_provider_connection_never_returns_provider_secret_material(monkeypatch) -> None:
    monkeypatch.setattr(settings_router, "provider_ids", lambda: ["openai"])
    monkeypatch.setattr(
        settings_router,
        "_load_raw",
        lambda user_id: {
            "llm_provider": {
                "configured": True,
                "provider": "openai",
                "model": "gpt-test",
                "last_tested": "2026-07-03T10:00:00+00:00",
                "encrypted_key": "secret-envelope",
                "api_key": "raw-secret",
            },
        },
    )

    result = asyncio.run(
        settings_router.get_provider_connection({
            "sub": "client-a",
            "user_id": "client-a",
            "client_id": "client-a",
            "role": "client",
        })
    )

    assert result["configured"] is True
    assert result["status"] == "configured"
    assert result["provider"] == "openai"
    assert result["model"] == "gpt-test"
    assert result["last_tested"] == "2026-07-03T10:00:00+00:00"

    assert "encrypted_key" not in result
    assert "api_key" not in result
    assert "raw-secret" not in str(result)
    assert "secret-envelope" not in str(result)
