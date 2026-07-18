from __future__ import annotations

import asyncio
import json

from fastapi.routing import APIRoute

from processual_api.routers import settings as settings_router


def test_client_usage_summary_route_is_registered():
    paths = {
        route.path
        for route in settings_router.router.routes
        if isinstance(route, APIRoute)
    }

    assert "/settings/client/usage-summary" in paths
    assert "/settings/usage-summary" in paths


def test_client_usage_summary_returns_current_client_payload(tmp_path, monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)

    settings_file = tmp_path / "settings_client-alpha-user.json"
    settings_file.write_text(
        json.dumps(
            {
                "subscription": {"plan_id": "enterprise"},
                "llm_provider": {
                    "configured": True,
                    "provider": "openai",
                    "model": "gpt-test",
                    "encrypted_key": "must-not-leak",
                },
                "client_requests": [
                    {"status": "completed", "requested_plan": "enterprise"},
                    {"status": "pending", "requested_plan": "business"},
                ],
            }
        ),
        encoding="utf-8",
    )

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
            "total_units": 12,
            "quota_status": "ok",
            "latest_usage_at": "2026-07-06T00:00:00Z",
            "current_period": "2026-07",
        }

    monkeypatch.setattr(
        settings_router,
        "summarize_usage_logs",
        fake_summarize_usage_logs,
    )

    result = asyncio.run(
        settings_router.get_client_usage_summary({
            "sub": "client-alpha-user",
            "user_id": "client-alpha-user",
            "client_id": "client-alpha",
            "auth_method": "jwt",
            "role": "client",
        })
    )

    assert captured == {
        "client_id": "client-alpha",
        "api_key_id": None,
        "latest_limit": 10,
    }
    assert result["client_id"] == "client-alpha"
    assert result["user_id"] == "client-alpha-user"
    assert result["plan"]["plan_id"] == "enterprise"
    assert result["plan"]["source"] == "settings"
    assert result["plan"]["monthly_unit_allowance"] > 0
    assert result["usage"]["monthly_units_used"] == 12
    assert result["usage"]["monthly_units_allowance"] == result["plan"]["monthly_unit_allowance"]
    assert result["usage"]["monthly_units_remaining"] is not None
    assert result["usage"]["usage_percent"] is not None
    assert result["quota"]["near_limit"] is False
    assert result["quota"]["exceeded"] is False
    assert result["requests"]["open"] == 1
    assert result["requests"]["latest_status"] == "pending"
    assert result["provider"]["byok_required"] is True
    assert result["provider"]["connection_status"] == "configured"


def test_client_usage_summary_filters_by_api_key_identity(tmp_path, monkeypatch):
    captured: dict[str, object] = {}
    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)

    (tmp_path / "settings_service-user.json").write_text("{}", encoding="utf-8")

    def fake_summarize_usage_logs(
        *,
        client_id: str | None = None,
        api_key_id: str | None = None,
        latest_limit: int = 10,
    ) -> dict[str, object]:
        captured["client_id"] = client_id
        captured["api_key_id"] = api_key_id
        captured["latest_limit"] = latest_limit
        return {"client_id": client_id or "", "api_key_id": api_key_id or ""}

    monkeypatch.setattr(
        settings_router,
        "summarize_usage_logs",
        fake_summarize_usage_logs,
    )

    result = asyncio.run(
        settings_router.get_client_usage_summary({
            "sub": "service-user",
            "user_id": "service-user",
            "client_id": "client-alpha",
            "auth_method": "api_key",
            "api_key_id": "key-alpha",
            "role": "service",
        })
    )

    assert result["client_id"] == "client-alpha"
    assert captured == {
        "client_id": "client-alpha",
        "api_key_id": "key-alpha",
        "latest_limit": 10,
    }
