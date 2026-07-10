
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from fastapi.testclient import TestClient

from processual_api.supervisor_session_keys import issue_supervisor_session_key


def _seed_case(path):
    case_id = "client_visible_12a:request_visible_12a:crm:enterprise_core_api_reference:visible"
    payload = {
        "cases": [
            {
                "case_id": case_id,
                "client_id": "client_visible_12a",
                "request_id": "request_visible_12a",
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


def _supervisor_session_keys_test_helper_module_12a():
    helper_path = Path("tests/test_admin_supervisor_session_keys.py").resolve()
    spec = importlib.util.spec_from_file_location(
        "pmk_supervisor_session_keys_test_helpers_12a",
        helper_path,
    )

    if spec is None or spec.loader is None:
        raise AssertionError("Could not load supervisor session key test helpers")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _issue_legacy_session_12a(store: Path) -> dict[str, object]:
    module = _supervisor_session_keys_test_helper_module_12a()
    scopes = ["admin:integration_readiness:review"]

    issued = issue_supervisor_session_key(
        store,
        dict(module._owner()),
        {
            "label": "12A validated legacy readiness session",
            "level": "operations_supervisor",
            "scopes": scopes,
        },
    )

    raw_store = json.loads(store.read_text(encoding="utf-8"))
    records = raw_store.get("supervisor_session_keys") or []

    for record in records:
        if (
            str(record.get("session_key_id") or "")
            == str(issued["record"]["session_key_id"])
        ):
            record["scopes"] = list(scopes)

    store.write_text(
        json.dumps(raw_store, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )

    issued["record"]["scopes"] = list(scopes)
    return issued


def _headers_12b_for_12a(raw_key: str) -> dict[str, str]:
    return {
        "X-Admin-Supervisor-Session": raw_key,
        "X-Admin-Supervisor-Scope": "admin:integration_readiness:review",
    }


def test_admin_integration_readiness_case_management_12a_list_detail_and_action(
    tmp_path,
    monkeypatch,
):
    store_path = tmp_path / "integration_readiness_cases.json"
    supervisor_store = tmp_path / "supervisor_session_keys.json"
    case_id = _seed_case(store_path)
    monkeypatch.setenv("PMK_INTEGRATION_READINESS_CASES_PATH", str(store_path))
    monkeypatch.setenv(
        "PMK_SUPERVISOR_SESSION_KEYS_PATH",
        str(supervisor_store),
    )
    issued = _issue_legacy_session_12a(supervisor_store)

    from processual_api.main import app

    client = TestClient(app)

    list_response = client.get("/settings/admin/integration-readiness-tracking/cases")
    assert list_response.status_code == 200
    list_payload = list_response.json()

    assert list_payload["persisted_cases"] == 1
    assert list_payload["production_allowed"] is False
    assert list_payload["runtime_connector_approved"] is False
    assert list_payload["external_http_enabled"] is False
    assert list_payload["raw_secret_visible"] is False
    assert list_payload["cases"][0]["case_id"] == case_id

    detail_response = client.get(
        "/settings/admin/integration-readiness-tracking/case-detail",
        params={"case_id": case_id},
    )
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["case_id"] == case_id
    assert detail_payload["input_statuses"][0]["item_key"] == "enterprise_core_api_reference"

    action_response = client.post(
        "/settings/admin/integration-readiness-tracking/case-item-action",
        headers=_headers_12b_for_12a(str(issued["raw_key"])),
        json={
            "case_id": case_id,
            "item_key": "enterprise_core_api_reference",
            "status": "provided",
            "safe_reference": "docs-ref-12a",
            "note": "provided by supervisor",
        },
    )
    assert action_response.status_code == 200
    action_payload = action_response.json()

    assert action_payload["case_id"] == case_id
    assert action_payload["input_statuses"][0]["status"] == "provided"
    assert action_payload["input_statuses"][0]["safe_reference"] == "docs-ref-12a"
    assert len(action_payload["timeline"]) == 1
    assert action_payload["timeline"][0]["event"] == "item_provided"

    persisted = json.loads(store_path.read_text(encoding="utf-8"))
    persisted_text = json.dumps(persisted).lower()
    assert "docs-ref-12a" in persisted_text
    for forbidden in ("http://", "https://", "sk-", "password", "bearer "):
        assert forbidden not in persisted_text


def test_admin_integration_readiness_case_management_12a_rejects_invalid_status(
    tmp_path,
    monkeypatch,
):
    store_path = tmp_path / "integration_readiness_cases.json"
    supervisor_store = tmp_path / "supervisor_session_keys.json"
    case_id = _seed_case(store_path)
    monkeypatch.setenv("PMK_INTEGRATION_READINESS_CASES_PATH", str(store_path))
    monkeypatch.setenv(
        "PMK_SUPERVISOR_SESSION_KEYS_PATH",
        str(supervisor_store),
    )
    issued = _issue_legacy_session_12a(supervisor_store)

    from processual_api.main import app

    client = TestClient(app)
    response = client.post(
        "/settings/admin/integration-readiness-tracking/case-item-action",
        headers=_headers_12b_for_12a(str(issued["raw_key"])),
        json={
            "case_id": case_id,
            "item_key": "enterprise_core_api_reference",
            "status": "approved_for_production",
            "safe_reference": "unsafe-prod-ref",
        },
    )

    assert response.status_code == 400
    assert "Unsupported readiness item status" in response.text


def test_admin_integration_readiness_case_management_12a_missing_case_returns_404(
    tmp_path,
    monkeypatch,
):
    store_path = tmp_path / "integration_readiness_cases.json"
    store_path.write_text(json.dumps({"cases": []}), encoding="utf-8")
    monkeypatch.setenv("PMK_INTEGRATION_READINESS_CASES_PATH", str(store_path))

    from processual_api.main import app

    client = TestClient(app)
    response = client.get(
        "/settings/admin/integration-readiness-tracking/case-detail",
        params={"case_id": "missing-case"},
    )

    assert response.status_code == 404


def test_admin_integration_readiness_summary_route_12a_compat(
    tmp_path,
    monkeypatch,
):
    store_path = tmp_path / "integration_readiness_cases.json"
    supervisor_store = tmp_path / "supervisor_session_keys.json"
    case_id = _seed_case(store_path)
    monkeypatch.setenv("PMK_INTEGRATION_READINESS_CASES_PATH", str(store_path))
    monkeypatch.setenv(
        "PMK_SUPERVISOR_SESSION_KEYS_PATH",
        str(supervisor_store),
    )
    issued = _issue_legacy_session_12a(supervisor_store)

    from processual_api.main import app

    client = TestClient(app)
    action_response = client.post(
        "/settings/admin/integration-readiness-tracking/case-item-action",
        headers=_headers_12b_for_12a(str(issued["raw_key"])),
        json={
            "case_id": case_id,
            "item_key": "enterprise_core_api_reference",
            "status": "provided",
            "safe_reference": "docs-ref-12a",
            "note": "summary compat proof",
        },
    )
    assert action_response.status_code == 200

    summary_response = client.get("/settings/admin/integration-readiness-tracking")
    assert summary_response.status_code == 200

    payload = summary_response.json()
    assert payload["persisted_cases"] == 1
    assert payload["provided_inputs"] == 1
    assert payload["verified_items"] == 1
    assert payload["rejected_items"] == 0
    assert payload["timeline_events"] == 1
    assert payload["production_allowed"] is False
    assert payload["runtime_connector_approved"] is False
    assert payload["external_http_enabled"] is False
    assert payload["raw_secret_visible"] is False
