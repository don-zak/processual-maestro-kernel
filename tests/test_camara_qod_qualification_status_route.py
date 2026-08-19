from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from processual_api.auth.security import get_current_user
from processual_api.integrations.camara_qod_governance_approval import (
    CAMARA_QOD_APPROVED_GOVERNANCE_VERSION,
)
from processual_api.integrations.trusted_endpoint_source_acquisition import (
    CAMARA_QOD_R32_COMMIT,
)
from processual_api.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _restore_dependency_overrides(monkeypatch):
    original = dict(app.dependency_overrides)
    monkeypatch.delenv("PMK_TRUSTED_GITHUB_ENDPOINT_SOURCES", raising=False)
    try:
        yield
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original)


def _override_user(payload: dict) -> None:
    app.dependency_overrides[get_current_user] = lambda: payload


def _admin_user() -> dict:
    return {
        "sub": "admin_demo",
        "role": "admin",
        "scopes": ["admin:integration:qualification:read"],
    }


def _exact_catalog_entry() -> dict[str, object]:
    return {
        "source_identity_id": "camara.quality_on_demand.r3_2",
        "repository": "camaraproject/QualityOnDemand",
        "contract_family": "camara",
        "allowed_path_prefixes": ["code/API_definitions"],
        "allowed_reference_prefixes": ["code/common"],
        "allowed_revisions": [CAMARA_QOD_R32_COMMIT],
        "policy_version": "camara-public-release-review-r1",
    }


def test_camara_qod_status_route_requires_authentication() -> None:
    app.dependency_overrides.clear()
    response = client.get("/settings/admin/integration-center/camara-qod-qualification")
    assert response.status_code == 401


def test_camara_qod_status_route_requires_admin_read_scope() -> None:
    _override_user(
        {
            "sub": "client_demo",
            "role": "client",
            "scopes": ["settings:read"],
        }
    )
    response = client.get("/settings/admin/integration-center/camara-qod-qualification")
    assert response.status_code == 403


def test_camara_qod_status_route_projects_approved_registration_but_stays_fail_closed() -> None:
    _override_user(_admin_user())
    response = client.get("/settings/admin/integration-center/camara-qod-qualification")
    assert response.status_code == 200
    payload = response.json()

    assert payload["status"] == "reviewed_qualification_contract"
    assert payload["source_identity_id"] == "camara.quality_on_demand.r3_2"
    assert payload["source_revision"] == CAMARA_QOD_R32_COMMIT
    assert payload["api_version"] == "1.1.0"
    assert payload["server_trusted_source_enabled"] is False
    assert payload["semantic_mapping_state"] == "proposal_only"
    assert len(payload["callable_operations"]) == 5
    assert payload["callback_operations_excluded_from_outbound_binding"] == [
        "postNotification"
    ]

    # The immutable candidate remains review metadata; the separate approval
    # record is the authoritative decision for this exact candidate version.
    assert payload["governance_candidate_state"] == "review_required"
    assert payload["governance_candidate_valid"] is True
    assert payload["governance_blocker_codes"] == []
    assert payload["candidate_task_ids"] == [
        "camara.qod.session_create",
        "camara.qod.session_get",
        "camara.qod.session_delete",
        "camara.qod.session_extend",
        "camara.qod.sessions_retrieve_by_device",
    ]
    assert payload["candidate_entitlement_ids"] == [
        "camara_qod_session_manage",
        "camara_qod_session_read",
    ]
    assert payload["candidate_quota_meters"] == [
        "camara_qod_session_create",
        "camara_qod_session_delete",
        "camara_qod_session_read",
        "camara_qod_session_retrieve_by_device",
        "camara_qod_session_update",
    ]
    assert payload["governance_decision"] == "approved_with_conditions"
    assert payload["governance_approved"] is True
    assert payload["approved_governance_version"] == (
        CAMARA_QOD_APPROVED_GOVERNANCE_VERSION
    )
    assert payload["approved_contract_blob_sha"] == (
        "70d57dd3d8c9632c7e45260646c71049cbbc1cee"
    )

    assert payload["runtime_task_registered"] is True
    assert payload["registered_task_ids"] == payload["candidate_task_ids"]
    assert payload["registered_entitlement_ids"] == [
        "camara_qod_session_manage",
        "camara_qod_session_read",
    ]
    assert payload["registered_quota_meters"] == [
        "camara_qod_session_create",
        "camara_qod_session_delete",
        "camara_qod_session_read",
        "camara_qod_session_retrieve_by_device",
        "camara_qod_session_update",
    ]
    assert payload["runtime_default_deny"] is True

    assert payload["existing_network_assurance_reused"] is False
    assert payload["live_source_acquisition_proven"] is False
    assert payload["provider_credentials_present"] is False
    assert payload["provider_network_proof"] is False
    assert payload["provider_sandbox_proven"] is False
    assert payload["runtime_connector_approved"] is False
    assert payload["production_allowed"] is False
    assert payload["raw_secret_visible"] is False

    external = payload["external_sandbox_evidence"]
    assert (
        external["evidence_class"]
        == "external_mock_interoperability_with_divergence"
    )
    assert external["authenticated_sandbox_reachability_proven"] is True
    assert external["external_mock_sandbox_proven"] is True
    assert external["external_mock_extend_proven"] is True
    assert external["provider_sandbox_proven"] is False
    assert external["runtime_connector_approved"] is False
    assert external["production_allowed"] is False
    assert external["missing_session_documented_expectation_met"] is False
    assert external["mock_documentation_divergence_observed"] is True

    compatibility = payload["telefonica_compatibility"]
    assert compatibility["compatibility_state"] == (
        "partial_interoperability_with_negative_path_divergence"
    )
    assert compatibility["provider_sandbox_proven"] is False
    assert compatibility["runtime_connector_approved"] is False
    assert compatibility["production_allowed"] is False
    assert (
        "telefonica_missing_session_returns_200_instead_of_documented_404"
        in compatibility["blocker_codes"]
    )
    assert (
        "telefonica_retrieve_sessions_by_device_unproven"
        in compatibility["blocker_codes"]
    )

    serialized = json.dumps(payload).lower()
    assert "access_token" not in serialized
    assert "client_secret" not in serialized
    assert "raw_key" not in serialized


def test_camara_qod_status_route_reports_exact_server_catalog_enablement(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "PMK_TRUSTED_GITHUB_ENDPOINT_SOURCES",
        json.dumps([_exact_catalog_entry()]),
    )
    _override_user(_admin_user())
    response = client.get("/settings/admin/integration-center/camara-qod-qualification")
    assert response.status_code == 200
    assert response.json()["server_trusted_source_enabled"] is True


@pytest.mark.parametrize(
    "override",
    [
        {"contract_family": "generic_enterprise"},
        {"policy_version": "different-review-policy"},
        {"allowed_reference_prefixes": ["code/common", "documentation"]},
    ],
)
def test_camara_qod_status_route_never_labels_near_match_catalog_as_enabled(
    monkeypatch,
    override: dict[str, object],
) -> None:
    entry = {**_exact_catalog_entry(), **override}
    monkeypatch.setenv("PMK_TRUSTED_GITHUB_ENDPOINT_SOURCES", json.dumps([entry]))
    _override_user(_admin_user())

    response = client.get("/settings/admin/integration-center/camara-qod-qualification")

    assert response.status_code == 200
    assert response.json()["server_trusted_source_enabled"] is False


def test_camara_qod_status_route_rejects_invalid_server_catalog(monkeypatch) -> None:
    monkeypatch.setenv("PMK_TRUSTED_GITHUB_ENDPOINT_SOURCES", "{not-json")
    _override_user(_admin_user())
    response = client.get("/settings/admin/integration-center/camara-qod-qualification")
    assert response.status_code == 503
    assert response.json()["detail"] == "trusted_source_catalog_invalid"
