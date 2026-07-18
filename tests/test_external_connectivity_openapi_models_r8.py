from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType

import pytest
from pydantic import ValidationError

PROHIBITED_PROPERTIES = {
    "password",
    "secret",
    "secret_value",
    "raw_secret",
    "raw_key",
    "api_key",
    "access_token",
    "refresh_token",
    "client_secret",
    "private_key",
    "certificate_pem",
    "authorization",
    "cookie",
}


def _schema_module() -> ModuleType:
    return importlib.import_module(
        "processual_api.schemas.external_connectivity"
    )


def _submission_values() -> dict[str, object]:
    return {
        "package_id": "ecpkg_case001_v1",
        "client_id": "client_001",
        "schema_version": "external-connectivity-customer-package/v1",
        "connector_id": "telecom_crm_reference",
        "credential_profile_id": "oauth2_client_credentials_reference",
        "target_environment": "sandbox",
        "target_reference_id": "target_ref_crm_sandbox_001",
        "secret_reference_ids": ("secret_ref_crm_oauth_001",),
        "dns_reference": "dns_ref_customer_crm_001",
        "tls_policy_reference": "tls_policy_ref_12_plus_001",
        "certificate_reference": "certificate_ref_customer_001",
        "outbound_allowlist_reference": "allowlist_ref_customer_001",
        "submitted_at": "2026-07-14T10:00:00Z",
    }


def test_r8_integrations_package_exports_case_contracts() -> None:
    package = importlib.import_module("processual_api.integrations")

    required = {
        "ExternalConnectivityCaseState",
        "ExternalConnectivityAuditEventType",
        "CustomerReferencePackage",
        "ExternalConnectivityReadinessAssessment",
        "ExternalConnectivityCase",
        "customer_reference_package_fingerprint",
        "find_prohibited_customer_fields",
        "is_external_connectivity_transition_allowed",
        "advance_external_connectivity_case",
    }

    assert required.issubset(set(dir(package)))


def test_r8_schema_module_exports_required_symbols() -> None:
    module = _schema_module()

    required = {
        "ExternalConnectivityCaseCreateRequest",
        "CustomerReferencePackageSubmissionRequest",
        "ExternalConnectivityCaseResponse",
        "ExternalConnectivityReadinessAssessmentResponse",
        "customer_reference_package_from_submission",
        "external_connectivity_case_response_from_contract",
        "external_connectivity_assessment_response_from_contract",
    }

    assert required.issubset(set(dir(module)))


def test_r8_schemas_package_exports_openapi_models() -> None:
    package = importlib.import_module("processual_api.schemas")

    required = {
        "ExternalConnectivityCaseCreateRequest",
        "CustomerReferencePackageSubmissionRequest",
        "ExternalConnectivityCaseResponse",
        "ExternalConnectivityReadinessAssessmentResponse",
    }

    assert required.issubset(set(dir(package)))


def test_r8_create_request_is_frozen_and_forbids_extra() -> None:
    module = _schema_module()
    model = module.ExternalConnectivityCaseCreateRequest

    assert model.model_config.get("frozen") is True
    assert model.model_config.get("extra") == "forbid"

    request = model(
        client_id="client_001",
        readiness_case_id="readiness_case_001",
        connector_id="telecom_crm_reference",
        credential_profile_id="oauth2_client_credentials_reference",
    )

    assert request.target_environment == "sandbox"
    assert request.integration_task_id == ""

    with pytest.raises(ValidationError):
        model(
            client_id="client_001",
            readiness_case_id="readiness_case_001",
            connector_id="telecom_crm_reference",
            credential_profile_id="oauth2_client_credentials_reference",
            unexpected="forbidden",
        )


def test_r8_create_request_rejects_production_environment() -> None:
    module = _schema_module()

    with pytest.raises(ValidationError):
        module.ExternalConnectivityCaseCreateRequest(
            client_id="client_001",
            readiness_case_id="readiness_case_001",
            connector_id="telecom_crm_reference",
            credential_profile_id="oauth2_client_credentials_reference",
            target_environment="production",
        )


def test_r8_submission_request_accepts_references_only() -> None:
    module = _schema_module()
    request = module.CustomerReferencePackageSubmissionRequest(
        **_submission_values()
    )

    assert request.target_environment == "sandbox"
    assert request.target_reference_id.startswith("target_ref_")
    assert request.secret_reference_ids == (
        "secret_ref_crm_oauth_001",
    )


@pytest.mark.parametrize(
    "prohibited_field",
    [
        "password",
        "raw_secret",
        "api_key",
        "client_secret",
        "private_key",
    ],
)
def test_r8_submission_request_rejects_raw_secret_fields(
    prohibited_field: str,
) -> None:
    module = _schema_module()
    payload = _submission_values()
    payload[prohibited_field] = "must-not-be-accepted"

    with pytest.raises(ValidationError):
        module.CustomerReferencePackageSubmissionRequest(
            **payload
        )


def test_r8_submission_json_schema_exposes_no_prohibited_properties() -> None:
    module = _schema_module()
    schema = (
        module.CustomerReferencePackageSubmissionRequest
        .model_json_schema()
    )
    properties = set(schema.get("properties", {}))

    assert properties.isdisjoint(PROHIBITED_PROPERTIES)


def test_r8_case_response_is_default_deny() -> None:
    module = _schema_module()
    response = module.ExternalConnectivityCaseResponse(
        case_id="eccase_001",
        client_id="client_001",
        readiness_case_id="readiness_case_001",
        integration_task_id="",
        connector_id="telecom_crm_reference",
        credential_profile_id="oauth2_client_credentials_reference",
        target_environment="sandbox",
        state="draft",
        customer_package_fingerprint="",
        readiness_assessment_id="",
        revision=1,
        created_at="2026-07-14T10:00:00Z",
        updated_at="2026-07-14T10:00:00Z",
    )

    assert response.production_allowed is False
    assert response.runtime_connector_allowed is False
    assert response.external_http_allowed is False
    assert response.secret_resolution_allowed is False
    assert response.automatic_activation_allowed is False
    assert response.raw_secret_visible is False

    with pytest.raises(ValidationError):
        response.model_copy(
            update={"production_allowed": True}
        ).__class__.model_validate(
            response.model_dump()
            | {"production_allowed": True}
        )


def test_r8_assessment_response_is_default_deny() -> None:
    module = _schema_module()
    response = module.ExternalConnectivityReadinessAssessmentResponse(
        assessment_id="ecassessment_001",
        case_id="eccase_001",
        customer_package_fingerprint="a" * 64,
        assessment_schema_version=(
            "external-connectivity-readiness-assessment/v1"
        ),
        readiness_status="needs_remediation",
        missing_input_codes=("customer_crm_scope_reference",),
        missing_control_codes=("tls_policy_review",),
        blocker_codes=("tls_policy_review_required",),
        remediation_codes=("submit_tls_policy_reference",),
        evidence_completeness=0.75,
        ready_for_supervisor_approval=False,
        assessed_at="2026-07-14T10:05:00Z",
    )

    assert response.network_access_performed is False
    assert response.secrets_read is False
    assert response.provider_sdk_initialized is False
    assert response.certificate_loaded is False
    assert response.sandbox_launched is False
    assert response.production_allowed is False


def test_r8_submission_conversion_binds_server_case_id() -> None:
    module = _schema_module()
    request = module.CustomerReferencePackageSubmissionRequest(
        **_submission_values()
    )

    package = module.customer_reference_package_from_submission(
        case_id="eccase_001",
        request=request,
    )

    assert package.case_id == "eccase_001"
    assert package.client_id == request.client_id
    assert package.target_reference_id == request.target_reference_id
    assert package.secret_reference_ids == request.secret_reference_ids


def test_r8_schema_module_has_no_network_or_secret_provider_sdk() -> None:
    module = _schema_module()
    source = Path(module.__file__).read_text(encoding="utf-8")

    prohibited = (
        "import requests",
        "import httpx",
        "import socket",
        "from requests",
        "from httpx",
        "from socket",
        "boto3",
        "google.cloud.secretmanager",
        "azure.keyvault",
        "hvac.Client",
        "urlopen(",
        "requests.",
        "httpx.",
    )

    for marker in prohibited:
        assert marker not in source
