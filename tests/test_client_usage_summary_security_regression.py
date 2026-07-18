from __future__ import annotations

import asyncio
import json

from processual_api.routers import settings as settings_router

FORBIDDEN_MARKERS = [
    "client-beta",
    "provider_secret",
    "encrypted_key",
    "raw_key",
    "token",
    "password",
    "must-not-leak",
    "beta-secret",
]


def test_client_usage_summary_ignores_cross_client_query_intent(tmp_path, monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)

    (tmp_path / "settings_client-alpha-user.json").write_text(
        json.dumps(
            {
                "llm_provider": {
                    "configured": False,
                    "provider_secret": "must-not-leak",
                    "encrypted_key": "must-not-leak",
                },
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "settings_client-beta-user.json").write_text(
        json.dumps(
            {
                "subscription": {"plan_id": "enterprise"},
                "llm_provider": {
                    "configured": True,
                    "encrypted_key": "beta-secret",
                },
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
            "total_events": 0,
            "total_units": 0,
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
            "role": "client",
            "requested_client_id": "client-beta",
        })
    )

    serialized = json.dumps(result).lower()

    assert captured == {
        "client_id": "client-alpha",
        "api_key_id": None,
        "latest_limit": 10,
    }
    assert result["client_id"] == "client-alpha"
    assert result["plan"]["plan_id"] == "unknown"
    assert result["plan"]["source"] == "missing"
    assert result["usage"]["monthly_units_allowance"] == 0
    assert result["usage"]["monthly_units_remaining"] is None
    assert result["usage"]["usage_percent"] is None
    assert result["recommendations"][0]["kind"] == "plan_missing"

    for marker in FORBIDDEN_MARKERS:
        assert marker not in serialized


def test_client_usage_summary_security_test_does_not_touch_ui_files():
    forbidden_files = (
        "processual_api/static/index.html",
        "processual_api/static/js/pages/settings.js",
        "processual_api/static/admin.html",
    )

    assert forbidden_files
