"""Tests for read-only operator pilot handoff readiness actions 14D."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from processual_api.main import app
from processual_api.services.operator_pilot_handoff_actions import (
    build_operator_pilot_handoff_actions_preview,
)

ACTIONS_ROUTE = "/settings/admin/operator-pilot-handoff/actions-preview"


def test_actions_preview_service_contract_14d() -> None:
    package = build_operator_pilot_handoff_actions_preview()

    assert package["phase_id"] == "operator-pilot-handoff-actions-14d"
    assert package["package_id"] == "operator-pilot-handoff-14a"
    assert package["action_plan_status"] == "draft_review"
    assert package["handoff_status"] == "pending_operator_inputs"
    assert package["pilot_ready"] is False
    assert package["read_only"] is True
    assert package["preview_only"] is True
    assert package["action_count"] >= 10

    guardrails = package["guardrails"]
    assert guardrails["production_allowed"] is False
    assert guardrails["runtime_connector_approved"] is False
    assert guardrails["customer_credentials_present"] is False
    assert guardrails["external_http_allowed"] is False
    assert guardrails["persistent_write_allowed"] is False
    assert guardrails["automatic_activation_allowed"] is False


def test_actions_are_copy_only_and_safe_14d() -> None:
    package = build_operator_pilot_handoff_actions_preview()
    actions = package["actions"]

    assert len(actions) == package["action_count"]
    assert len({action["action_id"] for action in actions}) == len(actions)

    for action in actions:
        assert action["status"] == "pending_operator_input"
        assert action["execution_mode"] == "copy_only"
        assert action["safe_to_execute"] is True
        assert action["requires_credentials"] is False
        assert action["requires_production"] is False
        assert action["runtime_connector_approved"] is False
        assert action["external_http_allowed"] is False
        assert action["persistent_write_allowed"] is False


def test_actions_preview_route_is_get_only_14d() -> None:
    client = TestClient(app)

    response = client.get(ACTIONS_ROUTE)
    assert response.status_code == 200

    payload = response.json()
    assert payload["phase_id"] == "operator-pilot-handoff-actions-14d"
    assert payload["read_only"] is True
    assert payload["preview_only"] is True
    assert payload["action_count"] >= 10

    post_response = client.post(ACTIONS_ROUTE, json={"status": "approved"})
    assert post_response.status_code == 405


def test_actions_preview_contains_no_secret_or_runtime_activation_contract_14d() -> None:
    package = build_operator_pilot_handoff_actions_preview()
    serialized = json.dumps(package, sort_keys=True).lower()

    assert "raw_secret" not in serialized
    assert "client_secret" not in serialized
    assert "private_key" not in serialized
    assert "production_allowed" in serialized
    assert "runtime_connector_approved" in serialized
    assert "external_http_allowed" in serialized


def test_main_registers_only_get_actions_preview_route_14d() -> None:
    source = Path("processual_api/main.py").read_text(encoding="utf-8")

    get_decorator = '@app.get("/settings/admin/operator-pilot-handoff/actions-preview")'
    post_decorator = '@app.post("/settings/admin/operator-pilot-handoff/actions-preview")'

    assert source.count(get_decorator) == 1
    assert post_decorator not in source
    assert "build_operator_pilot_handoff_actions_preview" in source
