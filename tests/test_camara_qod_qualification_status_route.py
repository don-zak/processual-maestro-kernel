from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from processual_api.auth.security import get_current_user
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


def test_camara_qod_status_route_is_safe_and_fail_closed_by_default() -> None:
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
    assert payload["existing_network_assurance_reused"] is False
    assert payload["live_source_acquisition_proven"] is False
    assert payload["provider_credentials_present"] is False
    assert payload["provider_network_proof"] is False
    assert payload["provider_sandbox_proven"] is False
    assert payload["runtime_task_registered"] is False
    assert payload["runtime_connector_approved"] is False
    assert payload["production_allowed"] is False
    assert payload["raw_secret_visible"] is False

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
