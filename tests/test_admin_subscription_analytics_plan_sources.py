import json
from pathlib import Path

from processual_api.services.admin_subscription_analytics import (
    build_admin_subscription_analytics,
)


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_admin_subscription_analytics_resolves_plan_from_approved_client_request(
    tmp_path,
):
    _write_json(
        tmp_path / "settings_plan-request-client.json",
        {
            "client_id": "plan-request-client",
            "client_requests": [
                {
                    "status": "approved",
                    "requested_plan": "business",
                }
            ],
            "api_keys": [],
        },
    )

    summary = build_admin_subscription_analytics(tmp_path)

    assert summary["plans"]["business"] == 1
    assert summary["plans"]["unknown"] == 0
    assert summary["plan_sources"]["client_requests"] == 1
    assert not any(
        item["kind"] == "unknown_plan"
        and item["client_id"] == "plan-request-client"
        for item in summary["risk"]
    )


def test_admin_subscription_analytics_keeps_blank_request_plan_unknown(tmp_path):
    _write_json(
        tmp_path / "settings_blank-request-client.json",
        {
            "client_id": "blank-request-client",
            "client_requests": [
                {
                    "status": "approved",
                    "requested_plan": "",
                }
            ],
            "api_keys": [],
        },
    )

    summary = build_admin_subscription_analytics(tmp_path)
    risks = {
        item["client_id"]: item
        for item in summary["risk"]
        if item["kind"] == "unknown_plan"
    }

    assert summary["plans"]["unknown"] == 1
    assert summary["plan_sources"]["missing"] == 1
    assert risks["blank-request-client"]["plan_source"] == "missing"


def test_admin_subscription_analytics_ignores_unapproved_requested_plan(tmp_path):
    _write_json(
        tmp_path / "settings_pending-request-client.json",
        {
            "client_id": "pending-request-client",
            "client_requests": [
                {
                    "status": "pending",
                    "requested_plan": "enterprise",
                }
            ],
            "api_keys": [],
        },
    )

    summary = build_admin_subscription_analytics(tmp_path)

    assert summary["plans"]["unknown"] == 1
    assert summary["plan_sources"]["missing"] == 1
    assert any(
        item["kind"] == "unknown_plan"
        and item["client_id"] == "pending-request-client"
        for item in summary["risk"]
    )
