from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from fastapi.testclient import TestClient

from processual_api.main import app
from processual_api.supervisor_session_keys import issue_supervisor_session_key


def _supervisor_session_keys_test_helper_module():
    helper_path = Path("tests/test_admin_supervisor_session_keys.py").resolve()
    spec = importlib.util.spec_from_file_location(
        "pmk_supervisor_session_keys_test_helpers_15b_r2b",
        helper_path,
    )

    if spec is None or spec.loader is None:
        raise AssertionError("Could not load supervisor session key test helpers")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _issue_session(
    store: Path,
    *,
    scopes: list[str],
) -> dict[str, object]:
    module = _supervisor_session_keys_test_helper_module()

    issued = issue_supervisor_session_key(
        store,
        dict(module._owner()),
        {
            "label": "15B-R2B legacy readiness write guard test",
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


def _sample_case_payload() -> dict[str, object]:
    return {
        "client_id": "client_15b_r2b",
        "request_id": "request_15b_r2b",
        "adapter_contract_id": "crm",
        "credential_profile_id": "enterprise_core_api_reference",
        "readiness_check_id": (
            "crm:enterprise_core_api_reference:readiness"
        ),
        "operational_profile_id": "service_integration_read_only",
        "missing_inputs": ["api_documentation", "sandbox_access"],
        "missing_security_controls": ["enterprise_review"],
        "assigned_supervisor": "review_supervisor",
    }


def test_15b_r2b_legacy_fake_session_with_forged_scope_is_rejected(
    monkeypatch,
    tmp_path: Path,
) -> None:
    supervisor_store = tmp_path / "supervisor_session_keys.json"
    case_store = tmp_path / "integration_readiness_cases.json"

    monkeypatch.setenv(
        "PMK_SUPERVISOR_SESSION_KEYS_PATH",
        str(supervisor_store),
    )
    monkeypatch.setenv(
        "PMK_INTEGRATION_READINESS_CASES_PATH",
        str(case_store),
    )

    client = TestClient(app)
    response = client.post(
        "/settings/admin/integration-readiness-tracking/cases",
        json=_sample_case_payload(),
        headers={
            "X-Admin-Supervisor-Session": "fake-legacy-supervisor-session",
            "X-Admin-Supervisor-Scope": (
                "admin:integration_readiness:write"
            ),
        },
    )

    assert response.status_code == 403
    payload = response.json()

    assert payload["error"] == "invalid_supervisor_session"
    assert payload["supervisor_session_present"] is True
    assert payload["supervisor_session_validated"] is False
    assert payload["production_allowed"] is False
    assert payload["runtime_connector_approved"] is False
    assert payload["external_http_enabled"] is False
    assert payload["raw_secret_visible"] is False


def test_15b_r2b_legacy_session_cannot_gain_forged_write_scope(
    monkeypatch,
    tmp_path: Path,
) -> None:
    supervisor_store = tmp_path / "supervisor_session_keys.json"
    case_store = tmp_path / "integration_readiness_cases.json"

    monkeypatch.setenv(
        "PMK_SUPERVISOR_SESSION_KEYS_PATH",
        str(supervisor_store),
    )
    monkeypatch.setenv(
        "PMK_INTEGRATION_READINESS_CASES_PATH",
        str(case_store),
    )

    issued = _issue_session(
        supervisor_store,
        scopes=["admin:audit:read"],
    )

    client = TestClient(app)
    response = client.post(
        "/settings/admin/integration-readiness-tracking/cases",
        json=_sample_case_payload(),
        headers={
            "X-Admin-Supervisor-Session": str(issued["raw_key"]),
            "X-Admin-Supervisor-Scopes": (
                "admin:integration_readiness:write"
            ),
        },
    )

    assert response.status_code == 403
    payload = response.json()

    assert payload["error"] == "supervisor_scope_required"
    assert payload["supervisor_session_present"] is True
    assert payload["supervisor_session_validated"] is True
    assert payload["session_key_id"] == issued["record"]["session_key_id"]
    assert "admin:audit:read" in payload["provided_scopes"]
    assert "admin:integration_readiness:write" not in payload[
        "provided_scopes"
    ]


def test_15b_r2b_legacy_valid_write_session_uses_safe_audit_actor(
    monkeypatch,
    tmp_path: Path,
) -> None:
    supervisor_store = tmp_path / "supervisor_session_keys.json"
    case_store = tmp_path / "integration_readiness_cases.json"
    audit_path = tmp_path / "admin_audit_events.jsonl"

    monkeypatch.setenv(
        "PMK_SUPERVISOR_SESSION_KEYS_PATH",
        str(supervisor_store),
    )
    monkeypatch.setenv(
        "PMK_INTEGRATION_READINESS_CASES_PATH",
        str(case_store),
    )
    monkeypatch.setenv(
        "PMK_ADMIN_AUDIT_EVENTS_PATH",
        str(audit_path),
    )

    issued = _issue_session(
        supervisor_store,
        scopes=["admin:integration_readiness:write"],
    )

    raw_key = str(issued["raw_key"])

    client = TestClient(app)
    response = client.post(
        "/settings/admin/integration-readiness-tracking/cases",
        json=_sample_case_payload(),
        headers={
            "X-Admin-Supervisor-Session": raw_key,
            "X-Admin-Supervisor-Scope": "admin:billing:read",
        },
    )

    assert response.status_code == 200

    response_text = response.text
    assert raw_key not in response_text

    payload = response.json()
    assert payload["production_allowed"] is False
    assert payload["runtime_connector_approved"] is False
    assert payload["external_http_enabled"] is False
    assert payload["raw_secret_visible"] is False

    audit_lines = audit_path.read_text(encoding="utf-8").splitlines()
    assert len(audit_lines) == 1

    event = json.loads(audit_lines[0])

    assert event["supervisor_session_present"] is True
    assert event["supervisor_session_validated"] is True
    assert event["session_key_id"] == issued["record"]["session_key_id"]
    assert "admin:integration_readiness:write" in event["supervisor_scope"]
    assert "admin:billing:read" not in event["supervisor_scope"]
    assert raw_key not in json.dumps(event)
    assert event["production_allowed"] is False
    assert event["runtime_connector_approved"] is False
    assert event["external_http_enabled"] is False
    assert event["raw_secret_visible"] is False
