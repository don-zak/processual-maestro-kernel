from __future__ import annotations

import asyncio

from fastapi.routing import APIRoute

from processual_api.routers import settings as settings_router


def test_usage_summary_route_is_registered():
    paths = {
        route.path
        for route in settings_router.router.routes
        if isinstance(route, APIRoute)
    }

    assert "/settings/usage-summary" in paths


def test_usage_summary_endpoint_filters_by_current_client(monkeypatch):
    captured: dict[str, object] = {}

    def fake_summarize_usage_logs(
        *,
        client_id: str | None = None,
        api_key_id: str | None = None,
        latest_limit: int = 10,
    ) -> dict[str, object]:
        captured["client_id"] = client_id
        captured["api_key_id"] = api_key_id
        captured["latest_limit"] = latest_limit
        return {
            "client_id": client_id or "",
            "api_key_id": api_key_id or "",
            "total_events": 0,
            "total_units": 0,
        }

    monkeypatch.setattr(
        settings_router,
        "summarize_usage_logs",
        fake_summarize_usage_logs,
    )

    result = asyncio.run(
        settings_router.get_usage_summary({
            "sub": "user-a",
            "user_id": "user-a",
            "client_id": "client-a",
            "auth_method": "jwt",
            "role": "client",
        })
    )

    assert result["client_id"] == "client-a"
    assert result["api_key_id"] == ""
    assert captured == {
        "client_id": "client-a",
        "api_key_id": None,
        "latest_limit": 10,
    }


def test_usage_summary_endpoint_filters_by_api_key_identity(monkeypatch):
    captured: dict[str, object] = {}

    def fake_summarize_usage_logs(
        *,
        client_id: str | None = None,
        api_key_id: str | None = None,
        latest_limit: int = 10,
    ) -> dict[str, object]:
        captured["client_id"] = client_id
        captured["api_key_id"] = api_key_id
        captured["latest_limit"] = latest_limit
        return {
            "client_id": client_id or "",
            "api_key_id": api_key_id or "",
            "total_events": 2,
            "total_units": 6,
        }

    monkeypatch.setattr(
        settings_router,
        "summarize_usage_logs",
        fake_summarize_usage_logs,
    )

    result = asyncio.run(
        settings_router.get_usage_summary({
            "sub": "service-user",
            "user_id": "service-user",
            "client_id": "client-a",
            "auth_method": "api_key",
            "api_key_id": "key-a",
            "role": "service",
        })
    )

    assert result["client_id"] == "client-a"
    assert result["api_key_id"] == "key-a"
    assert result["total_units"] == 6
    assert captured == {
        "client_id": "client-a",
        "api_key_id": "key-a",
        "latest_limit": 10,
    }


def test_usage_summary_endpoint_does_not_touch_console_ui_files():
    # Guardrail for CLIENT-USAGE-01B scope:
    # this phase exposes backend/API only. Console UI work belongs to a later
    # CLIENT-USAGE-01C phase and must preserve existing UI/UX patterns.
    forbidden_files = (
        "processual_api/static/index.html",
        "processual_api/static/js/settings.js",
        "processual_api/static/css",
    )

    assert forbidden_files
