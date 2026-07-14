from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from processual_api.integrations.connector_bindings import (
    ConnectorEnvironmentBinding,
    get_connector_secret_reference,
    list_connector_environment_bindings,
)
from processual_api.main import app
from processual_api.services.external_connectivity_case_store import (
    load_external_connectivity_case_store,
)
from processual_api.supervisor_session_keys import (
    issue_supervisor_session_key,
)

BASE_PATH = "/settings/admin/external-connectivity/cases"
WRITE_SCOPE = "admin:integration_readiness:write"


def _supervisor_helper_module():
    helper_path = Path(
        "tests/test_admin_supervisor_session_keys.py"
    ).resolve()

    spec = importlib.util.spec_from_file_location(
        "pmk_r9_supervisor_session_helpers",
        helper_path,
    )

    if spec is None or spec.loader is None:
        raise AssertionError(
            "Could not load supervisor session helpers"
        )

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _issue_session(
    store: Path,
    *,
    scopes: list[str],
) -> dict[str, object]:
    helper = _supervisor_helper_module()

    issued = issue_supervisor_session_key(
        store,
        dict(helper._owner()),
        {
            "label": "R9 external connectivity route tests",
            "level": "operations_supervisor",
            "scopes": scopes,
        },
    )

    raw_store = json.loads(
        store.read_text(encoding="utf-8")
    )
    records = raw_store.get(
        "supervisor_session_keys"
    ) or []

    for record in records:
        if (
            str(record.get("session_key_id") or "")
            == str(issued["record"]["session_key_id"])
        ):
            record["scopes"] = list(scopes)

    store.write_text(
        json.dumps(
            raw_store,
            ensure_ascii=False,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    issued["record"]["scopes"] = list(scopes)
    return issued


def _sandbox_binding() -> ConnectorEnvironmentBinding:
    return next(
        binding
        for binding in list_connector_environment_bindings()
        if binding.environment == "sandbox"
    )


def _create_payload() -> dict[str, object]:
    binding = _sandbox_binding()
    secret_reference = get_connector_secret_reference(
        binding.secret_reference_ids[0]
    )

    return {
        "client_id": "client_r9_routes",
        "readiness_case_id": "readiness_case_r9_routes",
        "connector_id": binding.connector_id,
        "credential_profile_id": (
            secret_reference.credential_profile_id
        ),
        "target_environment": "sandbox",
        "integration_task_id": "",
    }


def _submission_payload() -> dict[str, object]:
    binding = _sandbox_binding()
    secret_reference = get_connector_secret_reference(
        binding.secret_reference_ids[0]
    )

    return {
        "package_id": "package_r9_routes",
        "client_id": "client_r9_routes",
        "schema_version": "customer-reference-package/v1",
        "connector_id": binding.connector_id,
        "credential_profile_id": (
            secret_reference.credential_profile_id
        ),
        "target_environment": "sandbox",
        "target_reference_id": binding.target_reference_id,
        "secret_reference_ids": list(
            binding.secret_reference_ids
        ),
        "dns_reference": "dns_reference_r9_routes",
        "tls_policy_reference": (
            "tls_policy_reference_r9_routes"
        ),
        "certificate_reference": (
            "certificate_reference_r9_routes"
        ),
        "outbound_allowlist_reference": (
            "outbound_allowlist_reference_r9_routes"
        ),
        "submitted_at": "2026-07-14T12:01:00+00:00",
    }


def _configure_stores(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> tuple[Path, Path]:
    case_store = tmp_path / "external_connectivity.json"
    session_store = tmp_path / "supervisor_sessions.json"

    monkeypatch.setenv(
        "PMK_EXTERNAL_CONNECTIVITY_CASES_PATH",
        str(case_store),
    )
    monkeypatch.setenv(
        "PMK_SUPERVISOR_SESSION_KEYS_PATH",
        str(session_store),
    )

    return case_store, session_store


def _write_headers(
    issued: dict[str, object],
) -> dict[str, str]:
    return {
        "X-Supervisor-Session-Key": str(
            issued["raw_key"]
        )
    }


def test_r9_openapi_declares_exact_route_surface() -> None:
    client = TestClient(app)
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]

    required_operations = {
        BASE_PATH: {"get", "post"},
        f"{BASE_PATH}/{{case_id}}": {"get"},
        f"{BASE_PATH}/{{case_id}}/reference-package": {
            "post"
        },
        f"{BASE_PATH}/{{case_id}}/readiness-review": {
            "post"
        },
        f"{BASE_PATH}/{{case_id}}/supervisor-decision": {
            "post"
        },
    }

    for path, methods in required_operations.items():
        assert path in paths
        assert methods.issubset(set(paths[path]))


def test_r9_create_requires_supervisor_session(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_stores(monkeypatch, tmp_path)

    response = TestClient(app).post(
        BASE_PATH,
        json=_create_payload(),
    )

    assert response.status_code == 403
    payload = response.json()
    assert payload["error"] == "supervisor_session_required"
    assert payload["supervisor_session_present"] is False
    assert payload["supervisor_session_validated"] is False
    assert payload["production_allowed"] is False
    assert payload["external_http_allowed"] is False


def test_r9_fake_session_with_forged_scope_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_stores(monkeypatch, tmp_path)

    response = TestClient(app).post(
        BASE_PATH,
        json=_create_payload(),
        headers={
            "X-Supervisor-Session-Key": "fake-session",
            "X-Admin-Supervisor-Scope": WRITE_SCOPE,
        },
    )

    assert response.status_code == 403
    payload = response.json()
    assert payload["error"] == "invalid_supervisor_session"
    assert payload["supervisor_session_present"] is True
    assert payload["supervisor_session_validated"] is False


def test_r9_forged_scope_cannot_elevate_valid_session(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _, session_store = _configure_stores(
        monkeypatch,
        tmp_path,
    )

    issued = _issue_session(
        session_store,
        scopes=["admin:audit:read"],
    )

    response = TestClient(app).post(
        BASE_PATH,
        json=_create_payload(),
        headers={
            **_write_headers(issued),
            "X-Admin-Supervisor-Scope": WRITE_SCOPE,
        },
    )

    assert response.status_code == 403
    payload = response.json()
    assert payload["error"] == "supervisor_scope_required"
    assert payload["supervisor_session_validated"] is True
    assert payload["session_key_id"] == (
        issued["record"]["session_key_id"]
    )
    assert payload["provided_scopes"] == [
        "admin:audit:read"
    ]


def test_r9_valid_session_completes_intake_review_and_approval(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    case_store, session_store = _configure_stores(
        monkeypatch,
        tmp_path,
    )

    issued = _issue_session(
        session_store,
        scopes=[WRITE_SCOPE],
    )
    headers = _write_headers(issued)
    client = TestClient(app)

    created_response = client.post(
        BASE_PATH,
        json=_create_payload(),
        headers=headers,
    )

    assert created_response.status_code == 201
    created = created_response.json()
    case_id = created["case_id"]

    assert created["state"] == "draft"
    assert created["revision"] == 1
    assert created["production_allowed"] is False
    assert created["external_http_allowed"] is False

    list_response = client.get(BASE_PATH)
    assert list_response.status_code == 200
    assert list_response.json() == [created]

    detail_response = client.get(
        f"{BASE_PATH}/{case_id}"
    )
    assert detail_response.status_code == 200
    assert detail_response.json() == created

    submitted_response = client.post(
        (
            f"{BASE_PATH}/{case_id}/reference-package"
            "?expected_revision=1"
        ),
        json=_submission_payload(),
        headers=headers,
    )

    assert submitted_response.status_code == 200
    submitted = submitted_response.json()
    assert submitted["state"] == "customer_package_submitted"
    assert submitted["revision"] == 2
    assert len(submitted["customer_package_fingerprint"]) == 64

    review_response = client.post(
        f"{BASE_PATH}/{case_id}/readiness-review",
        json={"expected_revision": 2},
        headers=headers,
    )

    assert review_response.status_code == 200
    review = review_response.json()
    assert review["case"]["state"] == (
        "ready_for_supervisor_approval"
    )
    assert review["case"]["revision"] == 4
    assert review["assessment"][
        "ready_for_supervisor_approval"
    ] is True
    assert review["assessment"]["blocker_codes"] == []
    assert review["assessment"][
        "network_access_performed"
    ] is False
    assert review["assessment"]["secrets_read"] is False

    decision_response = client.post(
        f"{BASE_PATH}/{case_id}/supervisor-decision",
        json={
            "expected_revision": 4,
            "expected_package_fingerprint": (
                review["case"][
                    "customer_package_fingerprint"
                ]
            ),
            "decision": "approved",
            "reason_code": "readiness_review_completed",
            "expires_at": "2099-07-15T12:03:00+00:00",
        },
        headers=headers,
    )

    assert decision_response.status_code == 200
    decision = decision_response.json()
    assert decision["case"]["state"] == "readiness_approved"
    assert decision["case"]["revision"] == 5
    assert decision["attestation"]["decision"] == "approved"
    assert decision["attestation"][
        "production_allowed"
    ] is False
    assert decision["attestation"][
        "qualification_key_issuance_allowed"
    ] is False
    assert decision["attestation"][
        "sandbox_activation_allowed"
    ] is False

    snapshot = load_external_connectivity_case_store(
        case_store
    )
    assert len(
        snapshot.supervisor_readiness_attestations
    ) == 1

    attestation = (
        snapshot.supervisor_readiness_attestations[0]
    )
    assert attestation.supervisor_actor == (
        issued["record"]["session_key_id"]
    )
    assert str(issued["raw_key"]) not in (
        case_store.read_text(encoding="utf-8")
    )
    assert str(issued["raw_key"]) not in str(decision)


def test_r9_submission_rejects_raw_secret_property(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _, session_store = _configure_stores(
        monkeypatch,
        tmp_path,
    )

    issued = _issue_session(
        session_store,
        scopes=[WRITE_SCOPE],
    )
    headers = _write_headers(issued)
    client = TestClient(app)

    created = client.post(
        BASE_PATH,
        json=_create_payload(),
        headers=headers,
    ).json()

    payload = _submission_payload()
    payload["api_key"] = "must-not-be-accepted"

    response = client.post(
        (
            f"{BASE_PATH}/{created['case_id']}"
            "/reference-package?expected_revision=1"
        ),
        json=payload,
        headers=headers,
    )

    assert response.status_code == 422
    assert "must-not-be-accepted" not in response.text

    case_store = tmp_path / "external_connectivity.json"
    stored = case_store.read_text(encoding="utf-8")
    assert "must-not-be-accepted" not in stored


def test_r9_stale_revision_returns_conflict(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _, session_store = _configure_stores(
        monkeypatch,
        tmp_path,
    )

    issued = _issue_session(
        session_store,
        scopes=[WRITE_SCOPE],
    )
    headers = _write_headers(issued)
    client = TestClient(app)

    created = client.post(
        BASE_PATH,
        json=_create_payload(),
        headers=headers,
    ).json()

    response = client.post(
        (
            f"{BASE_PATH}/{created['case_id']}"
            "/reference-package?expected_revision=99"
        ),
        json=_submission_payload(),
        headers=headers,
    )

    assert response.status_code == 409
    payload = response.json()
    assert payload["error"] == "case_revision_conflict"
    assert payload["production_allowed"] is False
    assert payload["external_http_allowed"] is False


def test_r9_unknown_case_returns_not_found(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_stores(monkeypatch, tmp_path)

    response = TestClient(app).get(
        f"{BASE_PATH}/unknown_case"
    )

    assert response.status_code == 404
    payload = response.json()
    assert payload["error"] == (
        "external_connectivity_case_not_found"
    )
    assert payload["production_allowed"] is False
