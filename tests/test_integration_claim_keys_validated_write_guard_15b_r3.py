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
        "pmk_supervisor_session_keys_test_helpers_15b_r3",
        helper_path,
    )

    if spec is None or spec.loader is None:
        raise AssertionError(
            "Could not load supervisor session key test helpers"
        )

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
            "label": "15B-R3 integration claim key write guard",
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


def _configure_paths(monkeypatch, tmp_path: Path) -> dict[str, Path]:
    paths = {
        "claim_store": tmp_path / "integration_claim_keys.json",
        "session_store": tmp_path / "supervisor_session_keys.json",
        "audit": tmp_path / "admin_audit_events.jsonl",
    }

    monkeypatch.setenv(
        "PMK_INTEGRATION_CLAIM_KEYS_STORE",
        str(paths["claim_store"]),
    )
    monkeypatch.setenv(
        "PMK_SUPERVISOR_SESSION_KEYS_PATH",
        str(paths["session_store"]),
    )
    monkeypatch.setenv(
        "PMK_ADMIN_AUDIT_EVENTS_PATH",
        str(paths["audit"]),
    )

    return paths


def _claim_payload() -> dict[str, object]:
    return {
        "client_id": "operator-client-15b-r3",
        "issued_to": "integration.officer@example.invalid",
        "operator_org_id": "operator-org-15b-r3",
        "allowed_domains": ["telecom"],
    }


def test_15b_r3_fake_canonical_session_with_forged_scope_is_rejected(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _configure_paths(monkeypatch, tmp_path)

    response = TestClient(app).post(
        "/settings/admin/integration-claim-keys",
        headers={
            "X-Supervisor-Session-Key": "fake-canonical-session",
            "X-Admin-Supervisor-Scope": (
                "admin:integration_readiness:write"
            ),
        },
        json=_claim_payload(),
    )

    assert response.status_code == 403
    detail = response.json()["detail"]

    assert detail["error"] == "invalid_supervisor_session"
    assert detail["supervisor_session_present"] is True
    assert detail["supervisor_session_validated"] is False
    assert detail["production_allowed"] is False
    assert detail["runtime_enabled"] is False
    assert detail["external_http_enabled"] is False
    assert detail["raw_secret_visible"] is False


def test_15b_r3_legacy_session_cannot_gain_forged_write_scope(
    monkeypatch,
    tmp_path: Path,
) -> None:
    paths = _configure_paths(monkeypatch, tmp_path)
    issued = _issue_session(
        paths["session_store"],
        scopes=["admin:audit:read"],
    )

    response = TestClient(app).post(
        "/settings/admin/integration-claim-keys",
        headers={
            "X-Admin-Supervisor-Session": str(issued["raw_key"]),
            "X-Admin-Supervisor-Scopes": (
                "admin:integration_readiness:write"
            ),
        },
        json=_claim_payload(),
    )

    assert response.status_code == 403
    detail = response.json()["detail"]

    assert detail["error"] == "supervisor_scope_required"
    assert detail["supervisor_session_validated"] is True
    assert detail["session_key_id"] == issued["record"]["session_key_id"]
    assert "admin:audit:read" in detail["provided_scopes"]
    assert (
        "admin:integration_readiness:write"
        not in detail["provided_scopes"]
    )


def test_15b_r3_issue_and_revoke_persist_only_safe_session_actor(
    monkeypatch,
    tmp_path: Path,
) -> None:
    paths = _configure_paths(monkeypatch, tmp_path)
    issued_session = _issue_session(
        paths["session_store"],
        scopes=["admin:integration_readiness:write"],
    )

    raw_session = str(issued_session["raw_key"])
    safe_actor = str(issued_session["record"]["session_key_id"])
    client = TestClient(app)

    issue_response = client.post(
        "/settings/admin/integration-claim-keys",
        headers={
            "X-Supervisor-Session-Key": raw_session,
            "X-Admin-Supervisor-Scope": "admin:billing:read",
        },
        json=_claim_payload(),
    )

    assert issue_response.status_code == 200
    issued_claim = issue_response.json()
    claim_key_id = str(issued_claim["claim_key"]["claim_key_id"])

    assert issued_claim["claim_key"]["issued_by"] == safe_actor
    assert raw_session not in issue_response.text
    assert issued_claim["guardrails"]["runtime_enabled"] is False
    assert issued_claim["guardrails"]["production_allowed"] is False
    assert issued_claim["guardrails"]["external_http_enabled"] is False
    assert issued_claim["guardrails"]["raw_secret_visible"] is False

    revoke_response = client.post(
        (
            "/settings/admin/integration-claim-keys/"
            f"{claim_key_id}/revoke"
        ),
        headers={
            "X-Admin-Supervisor-Session": raw_session,
            "X-Admin-Supervisor-Scope": "admin:billing:read",
        },
        json={"reason": "R3 safe actor proof"},
    )

    assert revoke_response.status_code == 200
    revoked = revoke_response.json()

    assert revoked["ok"] is True
    assert revoked["claim_key"]["revoked"] is True
    assert revoked["claim_key"]["revoked_by"] == safe_actor
    assert raw_session not in revoke_response.text

    store_text = paths["claim_store"].read_text(encoding="utf-8")
    audit_text = paths["audit"].read_text(encoding="utf-8")

    assert raw_session not in store_text
    assert raw_session not in audit_text
    assert safe_actor in store_text
    assert safe_actor in audit_text
    assert "integration_claim_key_issued" in audit_text
    assert "integration_claim_key_revoked" in audit_text
