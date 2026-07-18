from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from processual_api.billing.usage_pricing import monthly_unit_allowance
from processual_api.routers import settings as settings_router
from processual_api.services.admin_subscription_analytics import (
    build_admin_subscription_analytics,
)
from processual_api.services.client_usage_summary import build_client_usage_summary


def _operations_supervisor() -> dict:
    return {
        "sub": "ops-supervisor@example.test",
        "user_id": "ops-supervisor@example.test",
        "role": "admin",
        "session_type": "ui_admin",
        "supervision_level": "operations_supervisor",
        "scopes": ["*"],
    }


def _review_supervisor() -> dict:
    return {
        "sub": "review-supervisor@example.test",
        "user_id": "review-supervisor@example.test",
        "role": "admin",
        "session_type": "ui_admin",
        "supervision_level": "review_supervisor",
        "scopes": ["admin:clients:status_review"],
    }


def _plan_sources(payload: dict) -> dict:
    sources = payload.get("plan_sources")
    return sources if isinstance(sources, dict) else {}


def test_admin_direct_client_plan_route_is_registered() -> None:
    routes = {
        (getattr(route, "path", ""), tuple(sorted(getattr(route, "methods", []))))
        for route in settings_router.router.routes
    }

    assert any(
        path == "/settings/admin/clients/{client_id}/plan" and "POST" in methods
        for path, methods in routes
    )


def test_admin_direct_client_plan_sets_settings_source(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)

    result = asyncio.run(
        settings_router.set_admin_client_plan(
            "client-direct-a",
            {"plan_id": "enterprise"},
            _operations_supervisor(),
        )
    )

    assert result["status"] == "plan_set"
    assert result["changed"] is True
    assert result["plan"]["plan_id"] == "enterprise"
    assert result["plan"]["source"] == "settings"
    assert result["plan"]["monthly_unit_allowance"] == monthly_unit_allowance("enterprise")

    raw = settings_router._load_raw("client-direct-a")
    assert raw["approved_plan"] == "enterprise"
    assert raw["plan_source"] == "settings"
    assert raw["plan_applied"] is True
    assert raw["plan_applied_at"]
    assert raw["plan_applied_by"]
    assert raw["subscription"]["plan_id"] == "enterprise"
    assert raw["subscription"]["plan"] == "enterprise"
    assert raw["plan_history"][-1]["event"] == "plan_set"
    assert raw["plan_history"][-1]["plan_source"] == "settings"


def test_admin_direct_client_plan_is_idempotent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)

    first = asyncio.run(
        settings_router.set_admin_client_plan(
            "client-direct-a",
            {"plan": "enterprise"},
            _operations_supervisor(),
        )
    )
    second = asyncio.run(
        settings_router.set_admin_client_plan(
            "client-direct-a",
            {"plan": "enterprise"},
            _operations_supervisor(),
        )
    )

    raw = settings_router._load_raw("client-direct-a")
    history = [item for item in raw.get("plan_history", []) if item.get("event") == "plan_set"]

    assert first["status"] == "plan_set"
    assert second["status"] == "already_set"
    assert second["changed"] is False
    assert len(history) == 1


def test_admin_direct_client_plan_rejects_unsupported_plan(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            settings_router.set_admin_client_plan(
                "client-direct-a",
                {"plan_id": "unsupported-direct-plan"},
                _operations_supervisor(),
            )
        )

    assert exc.value.status_code == 422
    assert exc.value.detail == "unsupported_plan"


def test_admin_direct_client_plan_requires_decide_scope(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            settings_router.set_admin_client_plan(
                "client-direct-a",
                {"plan_id": "enterprise"},
                _review_supervisor(),
            )
        )

    assert exc.value.status_code == 403


def test_admin_direct_client_plan_updates_client_usage_summary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)

    asyncio.run(
        settings_router.set_admin_client_plan(
            "client-direct-a",
            {"approved_plan": "enterprise"},
            _operations_supervisor(),
        )
    )

    raw = settings_router._load_raw("client-direct-a")
    summary = build_client_usage_summary(
        user_id="client-direct-a",
        client_id="client-direct-a",
        ledger_summary={},
        raw_settings=raw,
    )
    serialized = json.dumps(summary, sort_keys=True)

    assert summary["plan"]["plan_id"] == "enterprise"
    assert summary["plan"]["source"] == "settings"
    assert summary["plan"]["monthly_unit_allowance"] == monthly_unit_allowance("enterprise")
    assert "plan_missing" not in serialized


def test_admin_direct_client_plan_updates_admin_analytics_sources(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)

    asyncio.run(
        settings_router.set_admin_client_plan(
            "client-direct-a",
            {"plan_id": "enterprise"},
            _operations_supervisor(),
        )
    )

    analytics = build_admin_subscription_analytics(tmp_path)
    sources = _plan_sources(analytics)

    assert sources.get("settings", 0) >= 1
    assert sources.get("missing", 0) == 0


def test_admin_direct_client_plan_response_has_no_secret_markers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)

    result = asyncio.run(
        settings_router.set_admin_client_plan(
            "client-direct-a",
            {"plan_id": "enterprise"},
            _operations_supervisor(),
        )
    )

    serialized = json.dumps(result, sort_keys=True)
    forbidden = [
        "provider_secret",
        "encrypted_key",
        "raw_key",
        "raw key",
        "token",
        "password",
        "api_key",
        "/settings/llm-provider",
    ]

    for marker in forbidden:
        assert marker not in serialized
