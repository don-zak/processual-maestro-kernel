from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from processual_api.services.admin_subscription_analytics import (
    build_admin_subscription_analytics,
)


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _append_jsonl(path: Path, payload: dict) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")


def test_empty_admin_subscription_analytics_returns_safe_zero_summary(tmp_path):
    summary = build_admin_subscription_analytics(tmp_path)

    assert summary["clients"] == {
        "total": 0,
        "active": 0,
        "pilot": 0,
        "suspended": 0,
        "expired": 0,
    }
    assert summary["usage"]["monthly_units_used"] == 0
    assert summary["usage"]["monthly_units_allowance"] == 0
    assert summary["api_keys"]["active"] == 0
    assert summary["subscriptions"]["active"] == 0
    assert summary["risk"] == []


def test_admin_subscription_analytics_aggregates_usage_plans_and_risk(tmp_path):
    now = datetime.now(UTC).isoformat()

    _write_json(
        tmp_path / "settings_client-alpha.json",
        {
            "client_id": "client-alpha",
            "plan_id": "starter",
            "api_keys": [
                {
                    "key_id": "key-active",
                    "profile": "client_api",
                    "api_key": "pmk_should_never_leak",
                },
                {
                    "key_id": "key-revoked",
                    "category": "billing_service",
                    "status": "revoked",
                    "encrypted_key": "encrypted_should_never_leak",
                },
            ],
        },
    )

    _write_json(
        tmp_path / "settings_client-beta.json",
        {
            "client_id": "client-beta",
            "plan_id": "enterprise",
            "api_keys": [
                {
                    "key_id": "key-ops",
                    "profile": "ops_admin",
                    "provider_secret": "provider_should_never_leak",
                }
            ],
        },
    )

    _write_json(
        tmp_path / "subscriptions.json",
        {
            "subscriptions": [
                {
                    "client_id": "client-alpha",
                    "plan_id": "starter",
                    "status": "active",
                },
                {
                    "client_id": "client-beta",
                    "plan_id": "enterprise",
                    "status": "past_due",
                },
            ]
        },
    )

    _append_jsonl(
        tmp_path / "usage_logs.jsonl",
        {
            "client_id": "client-alpha",
            "plan_id": "starter",
            "timestamp": now,
            "units": 8500,
            "quota_limit": 10000,
        },
    )
    _append_jsonl(
        tmp_path / "usage_logs.jsonl",
        {
            "client_id": "client-beta",
            "plan_id": "enterprise",
            "timestamp": now,
            "units": 51000,
            "quota_limit": 50000,
        },
    )

    summary = build_admin_subscription_analytics(tmp_path)

    assert summary["clients"]["total"] == 2
    assert summary["plans"]["starter"] == 1
    assert summary["plans"]["enterprise"] == 1
    assert summary["subscriptions"]["active"] == 1
    assert summary["subscriptions"]["past_due"] == 1

    assert summary["usage"]["monthly_units_used"] == 59500
    assert summary["usage"]["monthly_units_allowance"] == 60000
    assert summary["usage"]["near_quota_limit"] == 1
    assert summary["usage"]["quota_exceeded"] == 1

    assert summary["api_keys"]["active"] == 2
    assert summary["api_keys"]["revoked"] == 1
    assert summary["api_keys"]["client_keys"] == 1
    assert summary["api_keys"]["billing_keys"] == 1
    assert summary["api_keys"]["ops_keys"] == 1

    kinds = {risk["kind"] for risk in summary["risk"]}
    assert "near_quota_limit" in kinds
    assert "quota_exceeded" in kinds
    assert "subscription_past_due" in kinds

    serialized = json.dumps(summary).lower()
    assert "pmk_should_never_leak" not in serialized
    assert "encrypted_should_never_leak" not in serialized
    assert "provider_should_never_leak" not in serialized
    assert "api_keys" in serialized
    assert "billing_keys" in serialized
    assert "ops_keys" in serialized


def test_admin_subscription_analytics_route_is_wired_to_admin_read_guard():
    text = Path("processual_api/routers/settings.py").read_text(encoding="utf-8")

    assert '"/admin/subscription-analytics"' in text
    assert "build_admin_subscription_analytics(_DATA_DIR)" in text
    assert "_require_admin_client_requests_read(current_user)" in text
