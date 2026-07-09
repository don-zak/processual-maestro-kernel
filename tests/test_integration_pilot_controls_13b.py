from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from processual_api.main import app
from processual_api.services import integration_pilot_controls as pilot


def _setup_paths(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "PMK_INTEGRATION_PILOT_TASKS_STORE",
        str(tmp_path / "integration_pilot_tasks.json"),
    )
    monkeypatch.setenv(
        "PMK_ADMIN_AUDIT_EVENTS_PATH",
        str(tmp_path / "admin_audit_events.jsonl"),
    )


def test_create_task_and_issue_activation_permission_key_once(tmp_path, monkeypatch):
    _setup_paths(tmp_path, monkeypatch)

    created = pilot.create_integration_task(
        {
            "client_id": "operator-client-13b",
            "operator_org_id": "operator-org-13b",
            "pilot_terms_note": "Sandbox only.",
        },
        created_by="supervisor-proof",
    )

    assert created["ok"] is True
    assert created["task"]["status"] == "pending_supervisor_review"
    assert created["task"]["sandbox_only"] is True
    assert created["task"]["runtime_enabled"] is False
    assert created["task"]["production_allowed"] is False

    task_id = created["task"]["task_id"]

    issued = pilot.issue_activation_permission_key(
        task_id,
        issued_by="supervisor-proof",
    )

    assert issued["ok"] is True
    assert issued["package_version"] == "integration-pilot-controls-13b"
    assert issued["activation_permission_key_once"].startswith("iapk_")
    assert issued["raw_activation_permission_key_visible_once"] is True
    assert issued["task"]["status"] == "activation_permission_issued"
    assert issued["guardrails"]["external_http_enabled"] is False
    assert issued["guardrails"]["raw_secret_visible"] is False

    listed = pilot.list_integration_tasks()
    listed_json = json.dumps(listed)

    assert listed["task_count"] == 1
    assert issued["activation_permission_key_once"] not in listed_json
    assert "activation_permission_key_hash" not in listed_json
    assert listed["tasks"][0]["masked_activation_permission_key"].startswith("iapk_")


def test_supervisor_controls_disable_task_safely(tmp_path, monkeypatch):
    _setup_paths(tmp_path, monkeypatch)

    created = pilot.create_integration_task(
        {
            "client_id": "operator-client-13b",
            "operator_org_id": "operator-org-13b",
        },
        created_by="supervisor-proof",
    )
    task_id = created["task"]["task_id"]

    suspended = pilot.control_integration_task(
        task_id,
        "suspend",
        actor="supervisor-proof",
        reason="pilot terms not satisfied",
    )

    assert suspended["ok"] is True
    assert suspended["task"]["status"] == "suspended"
    assert suspended["task"]["sandbox_grant_disabled"] is True
    assert suspended["task"]["runtime_connector_grant_disabled"] is True
    assert suspended["task"]["production_allowed"] is False

    blocked = pilot.issue_activation_permission_key(
        task_id,
        issued_by="supervisor-proof",
    )

    assert blocked["ok"] is False
    assert blocked["error"] == "task_not_eligible_for_activation_permission"

    resumed = pilot.control_integration_task(task_id, "resume", actor="supervisor-proof")
    assert resumed["ok"] is True
    assert resumed["task"]["status"] == "pending_supervisor_review"

    revoked = pilot.control_integration_task(
        task_id,
        "revoke",
        actor="supervisor-proof",
        reason="pilot revoked",
    )

    assert revoked["ok"] is True
    assert revoked["task"]["status"] == "revoked"
    assert revoked["task"]["integration_key_revoked"] is True


def test_routes_require_supervisor_and_do_not_leak_activation_permission_key(
    tmp_path,
    monkeypatch,
):
    _setup_paths(tmp_path, monkeypatch)
    client = TestClient(app)

    payload = {
        "client_id": "operator-client-route-13b",
        "operator_org_id": "operator-org-route-13b",
        "pilot_terms_note": "Sandbox only from route proof.",
    }

    no_session = client.post("/settings/admin/integration-tasks", json=payload)
    assert no_session.status_code == 403
    assert no_session.json()["detail"]["production_allowed"] is False

    wrong_scope = client.post(
        "/settings/admin/integration-tasks",
        headers={
            "X-Admin-Supervisor-Session": "session-proof",
            "X-Admin-Supervisor-Scope": "admin:billing:read",
        },
        json=payload,
    )
    assert wrong_scope.status_code == 403

    headers = {
        "X-Admin-Supervisor-Session": "session-proof",
        "X-Admin-Supervisor-Scope": "admin:integration_readiness:write",
    }

    created_response = client.post(
        "/settings/admin/integration-tasks",
        headers=headers,
        json=payload,
    )
    assert created_response.status_code == 200
    created = created_response.json()
    task_id = created["task"]["task_id"]

    issued_response = client.post(
        f"/settings/admin/integration-tasks/{task_id}/activation-permission-key",
        headers=headers,
        json={},
    )
    assert issued_response.status_code == 200
    issued = issued_response.json()
    raw_key = issued["activation_permission_key_once"]

    listed_response = client.get("/settings/admin/integration-tasks")
    assert listed_response.status_code == 200
    listed = listed_response.json()
    listed_json = json.dumps(listed)

    assert raw_key not in listed_json
    assert "activation_permission_key_hash" not in listed_json
    assert listed["tasks"][0]["masked_activation_permission_key"].startswith("iapk_")

    suspended_response = client.post(
        f"/settings/admin/integration-tasks/{task_id}/suspend",
        headers=headers,
        json={"reason": "route proof suspension"},
    )
    assert suspended_response.status_code == 200
    suspended = suspended_response.json()
    assert suspended["task"]["status"] == "suspended"
    assert suspended["task"]["runtime_connector_grant_disabled"] is True

    audit_path = Path(tmp_path / "admin_audit_events.jsonl")
    audit_text = audit_path.read_text(encoding="utf-8")
    assert "integration_task_created" in audit_text
    assert "integration_activation_permission_key_issued" in audit_text
    assert "integration_task_suspended" in audit_text
