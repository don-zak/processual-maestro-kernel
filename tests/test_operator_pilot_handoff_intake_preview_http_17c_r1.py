from __future__ import annotations

from fastapi.testclient import TestClient

from processual_api.auth.security import create_access_token
from processual_api.main import app

ENDPOINT = "/settings/admin/operator-pilot-handoff/intake-preview"


def _manifest() -> dict[str, object]:
    return {
        "manifest_version": "pilot-handoff-intake-17c-r1",
        "organization": {
            "organization_id": "org_http_route_reference",
            "display_name": "HTTP route pilot",
            "sector": "telecom",
            "technical_contact_ref": "contact://integration-team",
        },
        "integration": {
            "adapter_contract_id": "ticketing_adapter_reference",
            "credential_profile_id": "telecom_operations_api_reference",
            "target_environment": "sandbox",
            "api_documentation_ref": "document://api-guide-v1",
            "sandbox_base_url_ref": "target://telecom-sandbox",
            "authentication_method": "oauth2_client_credentials_reference",
            "requested_scopes": ["ticketing:read"],
            "sample_payload_refs": ["evidence://ticket-sample"],
        },
        "network_security": {
            "dns_names": ["sandbox.example.invalid"],
            "tls_min_version": "1.2",
            "outbound_allowlist_refs": ["allowlist://sandbox-v1"],
        },
        "operations": {
            "rate_limit_ref": "policy://rate-limit-v1",
            "support_contact_ref": "contact://pilot-support",
            "maintenance_window_ref": "window://pilot",
        },
        "governance": {
            "data_classification": "restricted_metadata_only",
            "retention_policy_ref": "policy://retention-v1",
            "incident_contact_ref": "contact://security-incident",
        },
        "evidence_refs": ["evidence://approval-request"],
    }


def _authorization(scopes: list[str], *, role: str = "admin") -> dict[str, str]:
    token = create_access_token(
        subject="handoff-http-test",
        role=role,
        client_id="handoff-http-test",
        session_type="test",
        scopes=scopes,
    )
    return {"Authorization": f"Bearer {token}"}


def test_intake_preview_requires_authentication() -> None:
    with TestClient(app) as client:
        response = client.post(ENDPOINT, json=_manifest())

    assert response.status_code == 401


def test_intake_preview_rejects_client_without_review_scope() -> None:
    with TestClient(app) as client:
        response = client.post(
            ENDPOINT,
            json=_manifest(),
            headers=_authorization(["evaluation"], role="client"),
        )

    assert response.status_code == 403
    assert "admin:integration_readiness:review" in response.text


def test_intake_preview_returns_safe_non_persistent_assessment() -> None:
    manifest = _manifest()

    with TestClient(app) as client:
        response = client.post(
            ENDPOINT,
            json=manifest,
            headers=_authorization(["*"]),
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready_for_supervisor_review"
    assert payload["completeness_percent"] == 100
    assert payload["persisted"] is False
    assert payload["review_only"] is True
    assert "manifest" not in payload
    assert "sandbox.example.invalid" not in response.text
    assert "contact://integration-team" not in response.text


def test_intake_preview_rejects_secret_without_echoing_value() -> None:
    manifest = _manifest()
    secret_sentinel = "must-not-appear-in-response"
    manifest["integration"]["client_secret"] = secret_sentinel  # type: ignore[index]

    with TestClient(app) as client:
        response = client.post(
            ENDPOINT,
            json=manifest,
            headers=_authorization(["*"]),
        )

    assert response.status_code == 422
    assert "prohibited secret-bearing field" in response.text
    assert secret_sentinel not in response.text


def test_intake_preview_rejects_production_environment() -> None:
    manifest = _manifest()
    manifest["integration"]["target_environment"] = "production"  # type: ignore[index]

    with TestClient(app) as client:
        response = client.post(
            ENDPOINT,
            json=manifest,
            headers=_authorization(["*"]),
        )

    assert response.status_code == 422
    assert "must remain sandbox" in response.text


def test_intake_preview_rejects_non_reference_api_documentation_value() -> None:
    manifest = _manifest()
    manifest["integration"]["api_documentation_ref"] = "2548545555dfg12"  # type: ignore[index]

    with TestClient(app) as client:
        response = client.post(
            ENDPOINT,
            json=manifest,
            headers=_authorization(["*"]),
        )

    assert response.status_code == 422
    assert "integration.api_documentation_ref" in response.text
    assert "2548545555dfg12" not in response.text
