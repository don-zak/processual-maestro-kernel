from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from processual_api.main import app

ADMIN_BASE = "/settings/admin/external-connectivity/cases"
CLIENT_REDEEM_PATH = (
    "/settings/client/external-connectivity/qualification/redeem"
)

EXPECTED_PATHS = {
    f"{ADMIN_BASE}/{{case_id}}/qualification-key",
    (
        f"{ADMIN_BASE}/{{case_id}}/qualification-key/"
        "{qualification_key_id}/revoke"
    ),
    f"{ADMIN_BASE}/{{case_id}}/sandbox-api-key",
    (
        f"{ADMIN_BASE}/{{case_id}}/sandbox-api-key/"
        "{sandbox_api_key_id}/suspend"
    ),
    (
        f"{ADMIN_BASE}/{{case_id}}/sandbox-api-key/"
        "{sandbox_api_key_id}/revoke"
    ),
    CLIENT_REDEEM_PATH,
}

EXPECTED_SCHEMAS = {
    "ExternalConnectivityQualificationKeyIssueRequest",
    "ExternalConnectivityQualificationKeyResponse",
    "ExternalConnectivityQualificationKeyIssueResponse",
    "ExternalConnectivityQualificationRedeemRequest",
    "ExternalConnectivitySandboxApiKeyIssueRequest",
    "ExternalConnectivitySandboxApiKeyResponse",
    "ExternalConnectivitySandboxApiKeyIssueResponse",
    "ExternalConnectivityKeyMutationRequest",
    "ExternalConnectivityKeyMutationResponse",
}


def test_r10_openapi_exposes_exact_key_lifecycle_paths() -> None:
    schema = app.openapi()

    assert EXPECTED_PATHS.issubset(schema["paths"])

    for path in EXPECTED_PATHS:
        assert set(schema["paths"][path]) == {"post"}


def test_r10_openapi_exposes_safe_key_models_without_hashes() -> None:
    schema = app.openapi()
    schemas = schema["components"]["schemas"]

    assert EXPECTED_SCHEMAS.issubset(schemas)

    serialized = str(
        {
            name: schemas[name]
            for name in EXPECTED_SCHEMAS
        }
    ).lower()

    assert "key_hash" not in serialized
    assert "qualification_key_once" in serialized
    assert "sandbox_api_key_once" in serialized


@pytest.mark.parametrize(
    ("path", "payload"),
    (
        (
            f"{ADMIN_BASE}/case_r10/qualification-key",
            {
                "expected_revision": 5,
                "expires_at": "2099-07-15T10:00:00+00:00",
            },
        ),
        (
            (
                f"{ADMIN_BASE}/case_r10/qualification-key/"
                "qk_r10/revoke"
            ),
            {"expected_revision": 6},
        ),
        (
            f"{ADMIN_BASE}/case_r10/sandbox-api-key",
            {
                "expected_revision": 7,
                "allowed_scope_ids": ["ticketing:read"],
                "expires_at": "2099-07-15T10:00:00+00:00",
            },
        ),
        (
            (
                f"{ADMIN_BASE}/case_r10/sandbox-api-key/"
                "sbk_r10/suspend"
            ),
            {"expected_revision": 8},
        ),
        (
            (
                f"{ADMIN_BASE}/case_r10/sandbox-api-key/"
                "sbk_r10/revoke"
            ),
            {"expected_revision": 8},
        ),
    ),
)
def test_r10_admin_key_mutations_require_supervisor_session(
    path: str,
    payload: dict[str, object],
) -> None:
    with TestClient(app) as client:
        response = client.post(path, json=payload)

    assert response.status_code == 403
    detail = response.json()
    assert detail["error"] == "supervisor_session_required"
    assert detail["supervisor_session_present"] is False
    assert detail["supervisor_session_validated"] is False


def test_r10_client_redeem_route_exists_and_rejects_missing_key() -> None:
    with TestClient(app) as client:
        response = client.post(
            CLIENT_REDEEM_PATH,
            json={
                "client_id": "client_r10",
                "redeemed_by": "client_user_r10",
                "expected_revision": 6,
            },
        )

    assert response.status_code == 422
def test_r10_valid_session_completes_route_key_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    import json

    from processual_api.integrations.connector_bindings import (
        get_connector_secret_reference,
        list_connector_environment_bindings,
    )
    from processual_api.integrations.connector_registry import (
        get_runtime_connector_contract,
    )
    from processual_api.integrations.scope_catalog import (
        list_integration_scopes,
    )
    from processual_api.services.external_connectivity_case_store import (
        load_external_connectivity_case_store,
    )
    from processual_api.supervision_rbac import (
        OPERATIONS_SUPERVISOR,
        OWNER_SUPERVISOR,
    )
    from processual_api.supervisor_session_keys import (
        issue_supervisor_session_key,
    )

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

    issued_session = issue_supervisor_session_key(
        session_store,
        {
            "email": "owner-r10@example.test",
            "supervision_level": OWNER_SUPERVISOR,
        },
        {
            "issued_to": "operator-r10@example.test",
            "level": OPERATIONS_SUPERVISOR,
            "session_label": "R10 route lifecycle",
            "reason": "Verify governed key lifecycle.",
            "expires_at": "2099-12-31T23:59:59+00:00",
        },
    )

    raw_session_store = json.loads(
        session_store.read_text(encoding="utf-8")
    )
    session_records = raw_session_store[
        "supervisor_session_keys"
    ]

    for record in session_records:
        if (
            record["session_key_id"]
            == issued_session["record"]["session_key_id"]
        ):
            record["scopes"] = [
                "admin:integration_readiness:write"
            ]

    session_store.write_text(
        json.dumps(
            raw_session_store,
            ensure_ascii=False,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    raw_session_key = str(issued_session["raw_key"])
    headers = {
        "X-Supervisor-Session-Key": raw_session_key,
    }

    binding = next(
        item
        for item in list_connector_environment_bindings()
        if item.environment == "sandbox"
    )
    secret_reference = get_connector_secret_reference(
        binding.secret_reference_ids[0]
    )
    contract = get_runtime_connector_contract(
        binding.connector_id
    )
    allowed_scope_id = contract.capabilities[0].scope_id
    connector_scope_ids = {
        capability.scope_id
        for capability in contract.capabilities
    }
    foreign_scope_id = next(
        scope.scope_id
        for scope in list_integration_scopes()
        if scope.scope_id not in connector_scope_ids
    )

    client_id = "client_r10_route_lifecycle"

    create_payload = {
        "client_id": client_id,
        "readiness_case_id": (
            "readiness_case_r10_route_lifecycle"
        ),
        "connector_id": binding.connector_id,
        "credential_profile_id": (
            secret_reference.credential_profile_id
        ),
        "target_environment": "sandbox",
        "integration_task_id": "",
    }

    submission_payload = {
        "package_id": "package_r10_route_lifecycle",
        "client_id": client_id,
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
        "dns_reference": "dns_reference_r10_route",
        "tls_policy_reference": "tls_policy_reference_r10_route",
        "certificate_reference": "certificate_reference_r10_route",
        "outbound_allowlist_reference": (
            "outbound_allowlist_reference_r10_route"
        ),
        "submitted_at": "2026-07-14T12:01:00+00:00",
    }

    with TestClient(app) as client:
        created_response = client.post(
            ADMIN_BASE,
            json=create_payload,
            headers=headers,
        )
        assert created_response.status_code == 201
        created = created_response.json()
        case_id = created["case_id"]
        assert created["revision"] == 1

        submitted_response = client.post(
            (
                f"{ADMIN_BASE}/{case_id}/reference-package"
                "?expected_revision=1"
            ),
            json=submission_payload,
            headers=headers,
        )
        assert submitted_response.status_code == 200
        submitted = submitted_response.json()
        assert submitted["revision"] == 2

        review_response = client.post(
            f"{ADMIN_BASE}/{case_id}/readiness-review",
            json={"expected_revision": 2},
            headers=headers,
        )
        assert review_response.status_code == 200
        reviewed = review_response.json()
        assert reviewed["case"]["revision"] == 4

        decision_response = client.post(
            f"{ADMIN_BASE}/{case_id}/supervisor-decision",
            json={
                "expected_revision": 4,
                "expected_package_fingerprint": (
                    reviewed["case"][
                        "customer_package_fingerprint"
                    ]
                ),
                "decision": "approved",
                "reason_code": "readiness_review_completed",
                "expires_at": "2099-12-31T23:59:59+00:00",
            },
            headers=headers,
        )
        assert decision_response.status_code == 200
        decision = decision_response.json()
        assert decision["case"]["revision"] == 5
        assert decision["case"]["state"] == "readiness_approved"

        qualification_response = client.post(
            f"{ADMIN_BASE}/{case_id}/qualification-key",
            json={
                "expected_revision": 5,
                "expires_at": "2099-01-01T00:00:00+00:00",
            },
            headers=headers,
        )
        assert qualification_response.status_code == 201
        qualification = qualification_response.json()
        raw_qualification_key = str(
            qualification["qualification_key_once"]
        )
        qualification_key_id = qualification[
            "qualification_key"
        ]["qualification_key_id"]

        assert qualification["case"]["revision"] == 6
        assert qualification["case"]["state"] == (
            "qualification_key_issued"
        )
        assert qualification_response.text.count(
            raw_qualification_key
        ) == 1
        assert "key_hash" not in qualification_response.text

        redeem_response = client.post(
            CLIENT_REDEEM_PATH,
            json={
                "qualification_key": raw_qualification_key,
                "client_id": client_id,
                "redeemed_by": "client-user-r10",
                "expected_revision": 6,
            },
        )
        assert redeem_response.status_code == 200
        redeemed = redeem_response.json()
        assert redeemed["case"]["revision"] == 7
        assert redeemed["case"]["state"] == (
            "qualification_redeemed"
        )
        assert raw_qualification_key not in redeem_response.text

        before_foreign_scope = case_store.read_bytes()

        foreign_scope_response = client.post(
            f"{ADMIN_BASE}/{case_id}/sandbox-api-key",
            json={
                "expected_revision": 7,
                "allowed_scope_ids": [foreign_scope_id],
                "expires_at": "2099-01-01T00:00:00+00:00",
            },
            headers=headers,
        )
        assert foreign_scope_response.status_code == 422
        assert foreign_scope_response.json()["error"] == (
            "sandbox_scope_not_allowed_for_connector"
        )
        assert case_store.read_bytes() == before_foreign_scope

        sandbox_response = client.post(
            f"{ADMIN_BASE}/{case_id}/sandbox-api-key",
            json={
                "expected_revision": 7,
                "allowed_scope_ids": [allowed_scope_id],
                "expires_at": "2099-01-01T00:00:00+00:00",
            },
            headers=headers,
        )
        assert sandbox_response.status_code == 201
        sandbox = sandbox_response.json()
        raw_sandbox_key = str(
            sandbox["sandbox_api_key_once"]
        )
        sandbox_key_id = sandbox[
            "sandbox_api_key"
        ]["sandbox_api_key_id"]

        assert sandbox["case"]["revision"] == 8
        assert sandbox["case"]["state"] == (
            "sandbox_api_key_issued"
        )
        assert sandbox["sandbox_api_key"][
            "allowed_scope_ids"
        ] == [allowed_scope_id]
        assert sandbox_response.text.count(raw_sandbox_key) == 1
        assert "key_hash" not in sandbox_response.text

        before_wrong_case = case_store.read_bytes()

        wrong_case_response = client.post(
            (
                f"{ADMIN_BASE}/different_case_r10/"
                f"sandbox-api-key/{sandbox_key_id}/suspend"
            ),
            json={"expected_revision": 8},
            headers=headers,
        )
        assert wrong_case_response.status_code == 422
        assert wrong_case_response.json()["error"] == (
            "external_connectivity_case_mismatch"
        )
        assert case_store.read_bytes() == before_wrong_case

        suspended_response = client.post(
            (
                f"{ADMIN_BASE}/{case_id}/sandbox-api-key/"
                f"{sandbox_key_id}/suspend"
            ),
            json={"expected_revision": 8},
            headers=headers,
        )
        assert suspended_response.status_code == 200
        suspended = suspended_response.json()
        assert suspended["case"]["revision"] == 9
        assert suspended["sandbox_api_key"]["status"] == (
            "suspended"
        )

        revoked_response = client.post(
            (
                f"{ADMIN_BASE}/{case_id}/sandbox-api-key/"
                f"{sandbox_key_id}/revoke"
            ),
            json={"expected_revision": 9},
            headers=headers,
        )
        assert revoked_response.status_code == 200
        revoked = revoked_response.json()
        assert revoked["case"]["revision"] == 10
        assert revoked["case"]["state"] == "sandbox_revoked"
        assert revoked["sandbox_api_key"]["status"] == "revoked"

    persisted_case_store = case_store.read_text(
        encoding="utf-8"
    )
    snapshot = load_external_connectivity_case_store(
        case_store
    )

    assert len(snapshot.qualification_keys) == 1
    assert len(snapshot.sandbox_api_keys) == 1
    assert snapshot.qualification_keys[0].qualification_key_id == (
        qualification_key_id
    )
    assert snapshot.sandbox_api_keys[0].sandbox_api_key_id == (
        sandbox_key_id
    )

    for raw_value in (
        raw_session_key,
        raw_qualification_key,
        raw_sandbox_key,
    ):
        assert raw_value not in persisted_case_store

    later_responses = (
        redeem_response.text
        + foreign_scope_response.text
        + suspended_response.text
        + revoked_response.text
    )
    assert raw_qualification_key not in later_responses
    assert raw_sandbox_key not in later_responses
    assert raw_session_key not in later_responses
