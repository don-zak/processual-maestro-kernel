from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from processual_api.routers import settings as settings_router
from processual_api.services.admin_subscription_analytics import (
    build_admin_subscription_analytics,
)
from processual_api.services.client_usage_summary import build_client_usage_summary

ROOT = Path(__file__).resolve().parents[1]


def _admin_user() -> dict:
    return {
        "sub": "owner-admin",
        "user_id": "owner-admin",
        "client_id": "owner-admin",
        "role": "owner_admin",
        "session_type": "ui_admin",
        "scopes": ["admin:*", "admin:clients:read", "admin:clients:write"],
    }


def _operations_supervisor() -> dict:
    return {
        "sub": "ops-supervisor",
        "user_id": "ops-supervisor",
        "client_id": "ops-supervisor",
        "role": "admin",
        "session_type": "supervisor",
        "scopes": ["admin:clients:read", "admin:clients:write"],
        "supervision_level": "operations_supervisor",
        "supervision_scopes": [settings_router.CLIENTS_STATUS_DECIDE_SCOPE],
    }


def _review_supervisor() -> dict:
    return {
        "sub": "review-supervisor",
        "user_id": "review-supervisor",
        "client_id": "review-supervisor",
        "role": "admin",
        "session_type": "supervisor",
        "scopes": ["admin:clients:read", "admin:clients:write"],
        "supervision_level": "review_supervisor",
        "supervision_scopes": [settings_router.CLIENTS_STATUS_REVIEW_SCOPE],
    }


def _seed_request(
    *,
    status: str = "approved",
    requested_plan: str = "enterprise",
) -> dict:
    return {
        "request_id": "creq_apply123456",
        "created_at": "2026-07-04T10:00:00+00:00",
        "updated_at": "2026-07-04T10:00:00+00:00",
        "user_id": "client-a",
        "client_id": "client-a",
        "role": "client",
        "request_type": "enterprise_integration_upgrade",
        "request_label": "Upgrade to Enterprise",
        "requested_plan": requested_plan,
        "message": "Client is asking for a verified plan upgrade.",
        "status": status,
        "status_history": [
            {
                "status": status,
                "at": "2026-07-04T10:00:00+00:00",
                "source": "client_settings",
            }
        ],
    }


def _save_request(request: dict) -> None:
    settings_router._save_raw("client-a", {"client_requests": [request]})


def _load_saved_request(tmp_path: Path) -> dict:
    saved_files = list(tmp_path.rglob("*.json"))
    assert saved_files
    saved = json.loads(saved_files[0].read_text(encoding="utf-8"))
    return saved["client_requests"][0]


def _plan_sources(payload: dict) -> dict:
    direct = payload.get("plan_sources")
    if isinstance(direct, dict):
        return direct
    subscriptions = payload.get("subscriptions")
    if isinstance(subscriptions, dict):
        nested = subscriptions.get("plan_sources")
        if isinstance(nested, dict):
            return nested
    return {}


def test_admin_client_request_apply_plan_route_is_registered() -> None:
    source = (ROOT / "processual_api" / "routers" / "settings.py").read_text(
        encoding="utf-8"
    )

    assert (
        '@router.post("/admin/client-requests/{request_id}/apply-plan", response_model=dict)'
        in source
    )
    assert "apply_admin_client_request_plan" in source
    assert "apply_verified_client_request_plan" in source


def test_admin_client_request_apply_plan_saves_verified_plan(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)
    _save_request(_seed_request())

    result = asyncio.run(
        settings_router.apply_admin_client_request_plan(
            "creq_apply123456",
            _admin_user(),
        )
    )

    assert result["status"] == "plan_applied"
    assert result["changed"] is True
    assert result["plan"]["plan_id"] == "enterprise"
    assert result["plan"]["source"] == "client_requests"
    assert result["plan"]["monthly_unit_allowance"] > 0
    assert result["request"]["approved_plan"] == "enterprise"
    assert result["request"]["plan_source"] == "client_requests"
    assert result["request"]["plan_applied"] is True

    saved_request = _load_saved_request(tmp_path)
    assert saved_request["approved_plan"] == "enterprise"
    assert saved_request["plan_source"] == "client_requests"
    assert saved_request["plan_applied"] is True
    assert saved_request["plan_applied_at"]
    assert saved_request["plan_applied_by"] == "owner-admin"
    assert saved_request["status_history"][-1]["event"] == "plan_applied"
    assert saved_request["status_history"][-1]["plan_id"] == "enterprise"
    assert saved_request["status_history"][-1]["plan_source"] == "client_requests"
    assert saved_request["status_history"][-1]["source"] == "admin_clients_panel"

    serialized = json.dumps(result, sort_keys=True)
    for marker in (
        "provider_secret",
        "encrypted_key",
        "raw_key",
        "raw key",
        "token",
        "password",
        "api_key",
    ):
        assert marker not in serialized


def test_admin_client_request_apply_plan_is_idempotent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)
    _save_request(_seed_request())

    first = asyncio.run(
        settings_router.apply_admin_client_request_plan(
            "creq_apply123456",
            _admin_user(),
        )
    )
    second = asyncio.run(
        settings_router.apply_admin_client_request_plan(
            "creq_apply123456",
            _admin_user(),
        )
    )

    assert first["status"] == "plan_applied"
    assert second["status"] == "already_applied"
    saved_request = _load_saved_request(tmp_path)
    applied_events = [
        event
        for event in saved_request["status_history"]
        if event.get("event") == "plan_applied"
    ]
    assert len(applied_events) == 1


def test_admin_client_request_apply_plan_can_load_by_short_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)
    request = _seed_request()
    _save_request(request)
    short_id = settings_router._admin_client_request_summary(request, "client-a")[
        "short_id"
    ]

    result = asyncio.run(
        settings_router.apply_admin_client_request_plan(
            short_id,
            _admin_user(),
        )
    )

    assert result["status"] == "plan_applied"
    assert result["request"]["request_id"] == "creq_apply123456"


def test_admin_client_request_apply_plan_rejects_unapproved_request(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)
    _save_request(_seed_request(status="reviewed"))

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            settings_router.apply_admin_client_request_plan(
                "creq_apply123456",
                _admin_user(),
            )
        )

    assert exc.value.status_code == 409


def test_admin_client_request_apply_plan_rejects_unsupported_plan(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)
    _save_request(_seed_request(requested_plan="unsupported-super-plan"))

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            settings_router.apply_admin_client_request_plan(
                "creq_apply123456",
                _admin_user(),
            )
        )

    assert exc.value.status_code == 422


def test_admin_client_request_apply_plan_rejects_review_supervisor(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)
    _save_request(_seed_request())

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            settings_router.apply_admin_client_request_plan(
                "creq_apply123456",
                _review_supervisor(),
            )
        )

    assert exc.value.status_code == 403


def test_admin_client_request_apply_plan_allows_operations_supervisor(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)
    _save_request(_seed_request())

    result = asyncio.run(
        settings_router.apply_admin_client_request_plan(
            "creq_apply123456",
            _operations_supervisor(),
        )
    )

    assert result["status"] == "plan_applied"
    assert result["plan"]["source"] == "client_requests"


def test_admin_client_request_apply_plan_updates_client_usage_summary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)
    _save_request(_seed_request())

    asyncio.run(
        settings_router.apply_admin_client_request_plan(
            "creq_apply123456",
            _admin_user(),
        )
    )

    saved_files = list(tmp_path.rglob("*.json"))
    saved = json.loads(saved_files[0].read_text(encoding="utf-8"))
    summary = build_client_usage_summary(
        user_id="client-a",
        client_id="client-a",
        ledger_summary={"total_units": 0, "total_events": 0},
        raw_settings=saved,
    )

    assert summary["plan"]["source"] == "client_requests"
    assert summary["plan"]["monthly_unit_allowance"] > 0
    assert not any(
        item.get("kind") == "plan_missing"
        for item in summary["recommendations"]
        if isinstance(item, dict)
    )


def test_admin_client_request_apply_plan_preserves_admin_plan_source_consistency(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)
    _save_request(_seed_request())

    before = _plan_sources(build_admin_subscription_analytics(tmp_path))
    result = asyncio.run(
        settings_router.apply_admin_client_request_plan(
            "creq_apply123456",
            _admin_user(),
        )
    )
    after = _plan_sources(build_admin_subscription_analytics(tmp_path))
    saved_request = _load_saved_request(tmp_path)

    assert result["status"] == "plan_applied"
    assert saved_request["approved_plan"] == "enterprise"
    assert saved_request["plan_source"] == "client_requests"
    assert after.get("client_requests", 0) >= before.get("client_requests", 0)
    assert after.get("client_requests", 0) >= 1
    assert after.get("missing", 0) <= before.get("missing", 0)
