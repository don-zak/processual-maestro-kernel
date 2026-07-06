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


def test_admin_subscription_analytics_adds_operational_risk_indicators(tmp_path):
    now = datetime.now(UTC).isoformat()

    _write_json(
        tmp_path / "settings_client-risk.json",
        {
            "client_id": "client-risk",
            "plan_id": "mystery-plan",
            "api_keys": [
                {
                    "key_id": "revoked-key",
                    "profile": "client_api",
                    "status": "revoked",
                }
            ],
        },
    )

    _write_json(
        tmp_path / "subscriptions.json",
        {
            "subscriptions": [
                {
                    "client_id": "client-risk",
                    "plan_id": "mystery-plan",
                    "status": "suspended",
                }
            ]
        },
    )

    _append_jsonl(
        tmp_path / "usage_logs.jsonl",
        {
            "client_id": "client-risk",
            "plan_id": "mystery-plan",
            "timestamp": now,
            "units": 1200,
        },
    )

    summary = build_admin_subscription_analytics(tmp_path)
    risks = {item["kind"]: item for item in summary["risk"]}

    assert risks["subscription_suspended"]["severity"] == "danger"
    assert risks["inactive_keys"]["severity"] == "warning"
    assert risks["unknown_plan"]["severity"] == "warning"
    assert risks["usage_without_allowance"]["severity"] == "warning"
    assert risks["usage_without_allowance"]["used"] == 1200
    assert risks["usage_without_allowance"]["limit"] == 0


def test_admin_subscription_analytics_keeps_risk_payload_secret_free(tmp_path):
    now = datetime.now(UTC).isoformat()

    _write_json(
        tmp_path / "settings_client-secret-safe.json",
        {
            "client_id": "client-secret-safe",
            "plan_id": "unknown",
            "api_keys": [
                {
                    "key_id": "revoked-key",
                    "status": "revoked",
                    "provider_secret": "do-not-leak",
                    "encrypted_key": "do-not-leak-either",
                }
            ],
        },
    )

    _append_jsonl(
        tmp_path / "usage_logs.jsonl",
        {
            "client_id": "client-secret-safe",
            "plan_id": "unknown",
            "timestamp": now,
            "units": 1,
        },
    )

    summary = build_admin_subscription_analytics(tmp_path)
    serialized = json.dumps(summary).lower()

    assert "do-not-leak" not in serialized
    assert "provider_secret" not in serialized
    assert "encrypted_key" not in serialized

def test_admin_subscription_analytics_allows_safe_client_ids_with_sensitive_words(tmp_path):
    _write_json(
        tmp_path / "settings_api_key_user.json",
        {
            "client_id": "api_key_user",
            "plan_id": "unknown",
            "api_keys": [],
        },
    )

    summary = build_admin_subscription_analytics(tmp_path)

    assert summary["clients"]["total"] == 1
    assert any(item["client_id"] == "api_key_user" for item in summary["risk"])
