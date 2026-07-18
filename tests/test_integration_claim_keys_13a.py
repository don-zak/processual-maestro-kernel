from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from fastapi.testclient import TestClient

from processual_api.main import app
from processual_api.services import integration_claim_keys as claim_keys
from processual_api.supervisor_session_keys import issue_supervisor_session_key


def _setup_paths(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "PMK_INTEGRATION_CLAIM_KEYS_STORE",
        str(tmp_path / "integration_claim_keys.json"),
    )
    monkeypatch.setenv(
        "PMK_ADMIN_AUDIT_EVENTS_PATH",
        str(tmp_path / "admin_audit_events.jsonl"),
    )
    monkeypatch.setenv(
        "PMK_SUPERVISOR_SESSION_KEYS_PATH",
        str(tmp_path / "supervisor_session_keys.json"),
    )


def _supervisor_session_keys_test_helper_module_13a():
    helper_path = Path("tests/test_admin_supervisor_session_keys.py").resolve()
    spec = importlib.util.spec_from_file_location(
        "pmk_supervisor_session_keys_test_helpers_13a",
        helper_path,
    )

    if spec is None or spec.loader is None:
        raise AssertionError(
            "Could not load supervisor session key test helpers"
        )

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _issue_supervisor_session_13a(
    store: Path,
    *,
    scopes: list[str],
) -> dict[str, object]:
    module = _supervisor_session_keys_test_helper_module_13a()

    issued = issue_supervisor_session_key(
        store,
        dict(module._owner()),
        {
            "label": "13A validated claim key route session",
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


def test_issue_claim_key_masks_raw_and_preserves_guardrails(tmp_path, monkeypatch):
    _setup_paths(tmp_path, monkeypatch)

    issued = claim_keys.issue_integration_claim_key(
        {
            "client_id": "operator-client-13a",
            "issued_to": "integration.officer@example.invalid",
            "operator_org_id": "operator-org-13a",
            "allowed_domains": ["telecom"],
        },
        issued_by="supervisor-proof",
    )

    assert issued["package_version"] == "integration-claim-keys-13a"
    assert issued["raw_claim_key_visible_once"] is True
    assert issued["claim_key_once"].startswith(issued["claim_key"]["claim_key_id"])
    assert "claim_key_hash" not in issued["claim_key"]
    assert issued["guardrails"]["runtime_enabled"] is False
    assert issued["guardrails"]["production_allowed"] is False
    assert issued["guardrails"]["external_http_enabled"] is False
    assert issued["guardrails"]["raw_secret_visible"] is False

    listed = claim_keys.list_integration_claim_keys()
    listed_json = json.dumps(listed)

    assert listed["claim_key_count"] == 1
    assert issued["claim_key_once"] not in listed_json
    assert "claim_key_hash" not in listed_json
    masked = listed["claim_keys"][0]["masked_claim_key"]
    assert masked.endswith("************************")


def test_redeem_claim_key_creates_safe_onboarding_case(tmp_path, monkeypatch):
    _setup_paths(tmp_path, monkeypatch)

    issued = claim_keys.issue_integration_claim_key(
        {
            "client_id": "operator-client-13a",
            "issued_to": "integration.officer@example.invalid",
            "operator_org_id": "operator-org-13a",
        },
        issued_by="supervisor-proof",
    )

    redeemed = claim_keys.redeem_integration_claim_key(
        {
            "claim_key": issued["claim_key_once"],
            "client_id": "operator-client-13a",
            "user_id": "operator-user-13a",
            "integration_officer_identity": "Operator Integration Officer",
        }
    )

    assert redeemed["ok"] is True
    case = redeemed["onboarding_case"]
    assert case["source"] == "integration_claim_key"
    assert case["status"] == "onboarding_in_progress"
    assert case["runtime_enabled"] is False
    assert case["production_allowed"] is False
    assert case["external_http_enabled"] is False
    assert case["raw_secret_visible"] is False
    assert "operator_api_documentation_reference" in case["required_inputs"]

    second_redeem = claim_keys.redeem_integration_claim_key(
        {
            "claim_key": issued["claim_key_once"],
            "client_id": "operator-client-13a",
            "user_id": "operator-user-13a",
        }
    )

    assert second_redeem["ok"] is False
    assert second_redeem["error"] == "claim_key_already_used"

    status = claim_keys.get_client_integration_onboarding_status(
        client_id="operator-client-13a",
        user_id="operator-user-13a",
    )

    assert status["status"] == "onboarding_available"
    assert status["onboarding_case_count"] == 1
    assert status["guardrails"]["production_allowed"] is False


def test_revoke_claim_key_blocks_redeem(tmp_path, monkeypatch):
    _setup_paths(tmp_path, monkeypatch)

    issued = claim_keys.issue_integration_claim_key(
        {
            "client_id": "operator-client-13a",
            "issued_to": "integration.officer@example.invalid",
        },
        issued_by="supervisor-proof",
    )

    revoked = claim_keys.revoke_integration_claim_key(
        issued["claim_key"]["claim_key_id"],
        revoked_by="supervisor-proof",
        reason="pilot cancelled",
    )

    assert revoked["ok"] is True
    assert revoked["claim_key"]["revoked"] is True
    assert revoked["claim_key"]["status"] == "revoked"

    redeemed = claim_keys.redeem_integration_claim_key(
        {
            "claim_key": issued["claim_key_once"],
            "client_id": "operator-client-13a",
            "user_id": "operator-user-13a",
        }
    )

    assert redeemed["ok"] is False
    assert redeemed["error"] == "claim_key_revoked"


def test_routes_require_supervisor_for_admin_write_and_allow_client_redeem(
    tmp_path,
    monkeypatch,
):
    _setup_paths(tmp_path, monkeypatch)

    supervisor_store = tmp_path / "supervisor_session_keys.json"
    insufficient_session = _issue_supervisor_session_13a(
        supervisor_store,
        scopes=["admin:billing:read"],
    )
    write_session = _issue_supervisor_session_13a(
        supervisor_store,
        scopes=["admin:integration_readiness:write"],
    )

    client = TestClient(app)

    no_session = client.post(
        "/settings/admin/integration-claim-keys",
        json={
            "client_id": "operator-client-route-13a",
            "issued_to": "integration.officer@example.invalid",
        },
    )

    assert no_session.status_code == 403
    assert no_session.json()["detail"]["production_allowed"] is False

    wrong_scope = client.post(
        "/settings/admin/integration-claim-keys",
        headers={
            "X-Admin-Supervisor-Session": str(
                insufficient_session["raw_key"]
            ),
            "X-Admin-Supervisor-Scope": (
                "admin:integration_readiness:write"
            ),
        },
        json={
            "client_id": "operator-client-route-13a",
            "issued_to": "integration.officer@example.invalid",
        },
    )

    assert wrong_scope.status_code == 403
    wrong_detail = wrong_scope.json()["detail"]
    assert wrong_detail["error"] == "supervisor_scope_required"
    assert wrong_detail["supervisor_session_validated"] is True
    assert (
        wrong_detail["session_key_id"]
        == insufficient_session["record"]["session_key_id"]
    )
    assert "admin:billing:read" in wrong_detail["provided_scopes"]
    assert (
        "admin:integration_readiness:write"
        not in wrong_detail["provided_scopes"]
    )

    issued_response = client.post(
        "/settings/admin/integration-claim-keys",
        headers={
            "X-Admin-Supervisor-Session": str(write_session["raw_key"]),
            "X-Admin-Supervisor-Scope": "admin:billing:read",
        },
        json={
            "client_id": "operator-client-route-13a",
            "issued_to": "integration.officer@example.invalid",
            "operator_org_id": "operator-org-route-13a",
        },
    )

    assert issued_response.status_code == 200
    issued = issued_response.json()
    assert issued["claim_key"]["production_allowed"] is False
    assert issued["claim_key"]["runtime_enabled"] is False
    assert (
        issued["claim_key"]["issued_by"]
        == write_session["record"]["session_key_id"]
    )
    assert str(write_session["raw_key"]) not in issued_response.text

    listed_response = client.get("/settings/admin/integration-claim-keys")
    assert listed_response.status_code == 200
    listed = listed_response.json()
    listed_text = json.dumps(listed)
    assert issued["claim_key_once"] not in listed_text
    assert str(write_session["raw_key"]) not in listed_text
    assert listed["claim_key_count"] == 1

    redeemed_response = client.post(
        "/settings/client/integration-claim-keys/redeem",
        json={
            "claim_key": issued["claim_key_once"],
            "client_id": "operator-client-route-13a",
            "user_id": "operator-user-route-13a",
        },
    )

    assert redeemed_response.status_code == 200
    redeemed = redeemed_response.json()
    assert redeemed["ok"] is True
    assert redeemed["onboarding_case"]["status"] == "onboarding_in_progress"
    assert redeemed["guardrails"]["external_http_enabled"] is False

    status_response = client.get(
        "/settings/client/integration-onboarding/status",
        params={
            "client_id": "operator-client-route-13a",
            "user_id": "operator-user-route-13a",
        },
    )

    assert status_response.status_code == 200
    status = status_response.json()
    assert status["onboarding_case_count"] == 1
    assert status["guardrails"]["raw_secret_visible"] is False

    audit_path = Path(tmp_path / "admin_audit_events.jsonl")
    audit_text = audit_path.read_text(encoding="utf-8")
    assert "integration_claim_key_issued" in audit_text
    assert "integration_claim_key_redeemed" in audit_text
    assert str(write_session["raw_key"]) not in audit_text
    assert str(write_session["record"]["session_key_id"]) in audit_text
