
from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient


def _seed_case(path: Path) -> str:
    case_id = "client_visible_12b:request_visible_12b:crm:enterprise_core_api_reference:visible"
    payload = {
        "cases": [
            {
                "case_id": case_id,
                "client_id": "client_visible_12b",
                "request_id": "request_visible_12b",
                "adapter_id": "crm",
                "status": "readiness_tracking",
                "input_statuses": [
                    {
                        "item_key": "enterprise_core_api_reference",
                        "label": "Enterprise core API reference",
                        "status": "missing",
                    }
                ],
                "security_control_statuses": [
                    {
                        "item_key": "no_raw_secrets",
                        "label": "No raw secrets supplied",
                        "status": "verified",
                    }
                ],
                "timeline": [],
            }
        ]
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return case_id


def _headers_12b(scope: str = "admin:integration_readiness:review") -> dict[str, str]:
    return {
        "X-Admin-Supervisor-Session": "test-supervisor-session-12b",
        "X-Admin-Supervisor-Scope": scope,
    }


def test_integration_readiness_12b_read_routes_remain_safe_without_supervisor(
    tmp_path,
    monkeypatch,
):
    store_path = tmp_path / "integration_readiness_cases.json"
    _seed_case(store_path)
    monkeypatch.setenv("PMK_INTEGRATION_READINESS_CASES_PATH", str(store_path))

    from processual_api.main import app

    client = TestClient(app)

    summary = client.get("/settings/admin/integration-readiness-tracking")
    cases = client.get("/settings/admin/integration-readiness-tracking/cases")

    assert summary.status_code == 200
    assert cases.status_code == 200
    assert summary.json()["raw_secret_visible"] is False
    assert cases.json()["external_http_enabled"] is False


def test_integration_readiness_12b_write_without_supervisor_is_forbidden(
    tmp_path,
    monkeypatch,
):
    store_path = tmp_path / "integration_readiness_cases.json"
    case_id = _seed_case(store_path)
    monkeypatch.setenv("PMK_INTEGRATION_READINESS_CASES_PATH", str(store_path))

    from processual_api.main import app

    client = TestClient(app)
    response = client.post(
        "/settings/admin/integration-readiness-tracking/case-item-action",
        json={
            "case_id": case_id,
            "item_key": "enterprise_core_api_reference",
            "status": "provided",
            "safe_reference": "docs-ref-12b",
        },
    )

    assert response.status_code == 403
    payload = response.json()
    assert "Supervisor session required" in payload["detail"]
    assert payload["production_allowed"] is False
    assert payload["runtime_connector_approved"] is False
    assert payload["external_http_enabled"] is False
    assert payload["raw_secret_visible"] is False


def test_integration_readiness_12b_wrong_scope_is_forbidden(
    tmp_path,
    monkeypatch,
):
    store_path = tmp_path / "integration_readiness_cases.json"
    case_id = _seed_case(store_path)
    monkeypatch.setenv("PMK_INTEGRATION_READINESS_CASES_PATH", str(store_path))

    from processual_api.main import app

    client = TestClient(app)
    response = client.post(
        "/settings/admin/integration-readiness-tracking/case-item-action",
        headers=_headers_12b("admin:billing:read"),
        json={
            "case_id": case_id,
            "item_key": "enterprise_core_api_reference",
            "status": "provided",
            "safe_reference": "docs-ref-12b",
        },
    )

    assert response.status_code == 403
    payload = response.json()
    assert "does not allow" in payload["detail"]
    assert payload["raw_secret_visible"] is False


def test_integration_readiness_12b_write_with_supervisor_scope_is_audited(
    tmp_path,
    monkeypatch,
):
    store_path = tmp_path / "integration_readiness_cases.json"
    audit_path = tmp_path / "admin_audit_events.jsonl"
    case_id = _seed_case(store_path)
    monkeypatch.setenv("PMK_INTEGRATION_READINESS_CASES_PATH", str(store_path))
    monkeypatch.setenv("PMK_ADMIN_AUDIT_EVENTS_PATH", str(audit_path))

    from processual_api.main import app

    client = TestClient(app)
    response = client.post(
        "/settings/admin/integration-readiness-tracking/case-item-action",
        headers=_headers_12b(),
        json={
            "case_id": case_id,
            "item_key": "enterprise_core_api_reference",
            "status": "provided",
            "safe_reference": "docs-ref-12b",
            "note": "scope audit proof",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["provided_inputs"] == 1
    assert payload["summary"]["timeline_events"] == 1

    lines = audit_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["event"] == "integration_readiness_case_write"
    assert event["case_id"] == case_id
    assert event["item_key"] == "enterprise_core_api_reference"
    assert event["status"] == "provided"
    assert event["supervisor_session_present"] is True
    assert event["production_allowed"] is False
    assert event["runtime_connector_approved"] is False
    assert event["external_http_enabled"] is False
    assert event["raw_secret_visible"] is False
