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
        "pmk_supervisor_session_keys_test_helpers_15b_r2",
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
            "label": "15B-R2 readiness write guard test",
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
        "client_id": "client_15b_r2",
        "request_id": "request_15b_r2",
        "adapter_contract_id": "crm",
        "credential_profile_id": "enterprise_core_api_reference",
        "readiness_check_id": "crm:enterprise_core_api_reference:readiness",
        "operational_profile_id": "service_integration_read_only",
        "missing_inputs": ["api_documentation", "sandbox_access"],
        "missing_security_controls": ["enterprise_review"],
        "assigned_supervisor": "review_supervisor",
    }


def test_15b_r2_canonical_fake_session_with_forged_scope_is_rejected(
    monkeypatch,
    tmp_path: Path,
) -> None:
    store = tmp_path / "supervisor_session_keys.json"
    monkeypatch.setenv("PMK_SUPERVISOR_SESSION_KEYS_PATH", str(store))

    client = TestClient(app)
    response = client.post(
        "/settings/admin/integration-readiness-tracking/cases",
        json=_sample_case_payload(),
        headers={
            "X-Supervisor-Session-Key": "fake-supervisor-session",
            "X-Admin-Supervisor-Scope": "admin:integration_readiness:write",
        },
    )

    assert response.status_code == 403
    payload = response.json()
    assert payload["error"] == "invalid_supervisor_session"
    assert payload["supervisor_session_present"] is True
    assert payload["supervisor_session_validated"] is False
    assert payload["production_allowed"] is False
    assert payload["runtime_connector_approved"] is False


def test_15b_r2_canonical_valid_session_ignores_forged_scope_header(
    monkeypatch,
    tmp_path: Path,
) -> None:
    store = tmp_path / "supervisor_session_keys.json"
    monkeypatch.setenv("PMK_SUPERVISOR_SESSION_KEYS_PATH", str(store))

    issued = _issue_session(
        store,
        scopes=["admin:audit:read"],
    )

    client = TestClient(app)
    response = client.post(
        "/settings/admin/integration-readiness-tracking/cases",
        json=_sample_case_payload(),
        headers={
            "X-Supervisor-Session-Key": str(issued["raw_key"]),
            "X-Admin-Supervisor-Scope": "admin:integration_readiness:write",
        },
    )

    assert response.status_code == 403
    payload = response.json()
    assert payload["error"] == "supervisor_scope_required"
    assert payload["supervisor_session_validated"] is True
    assert payload["session_key_id"] == issued["record"]["session_key_id"]
    assert "admin:audit:read" in payload["provided_scopes"]


def test_15b_r2_canonical_valid_write_session_can_create_readiness_case(
    monkeypatch,
    tmp_path: Path,
) -> None:
    store = tmp_path / "supervisor_session_keys.json"
    monkeypatch.setenv("PMK_SUPERVISOR_SESSION_KEYS_PATH", str(store))

    issued = _issue_session(
        store,
        scopes=["admin:integration_readiness:write"],
    )

    client = TestClient(app)
    response = client.post(
        "/settings/admin/integration-readiness-tracking/cases",
        json=_sample_case_payload(),
        headers={
            "X-Supervisor-Session-Key": str(issued["raw_key"]),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["production_allowed"] is False
    assert payload["runtime_connector_approved"] is False
    assert payload["external_http_enabled"] is False
    assert payload["raw_secret_visible"] is False
    assert str(issued["raw_key"]) not in str(payload)
