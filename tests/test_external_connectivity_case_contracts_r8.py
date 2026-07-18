from __future__ import annotations

import dataclasses
import importlib
import re
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from types import ModuleType

import pytest

EXPECTED_STATES = {
    "draft",
    "customer_package_submitted",
    "under_automated_review",
    "needs_remediation",
    "ready_for_supervisor_approval",
    "readiness_approved",
    "qualification_key_issued",
    "qualification_redeemed",
    "sandbox_api_key_issued",
    "sandbox_authorized",
    "sandbox_suspended",
    "sandbox_revoked",
    "closed",
}

EXPECTED_AUDIT_EVENT_TYPES = {
    "case_created",
    "customer_package_submitted",
    "automated_review_started",
    "remediation_required",
    "ready_for_supervisor_approval",
    "readiness_approved",
    "qualification_key_issued",
    "qualification_redeemed",
    "sandbox_api_key_issued",
    "sandbox_authorized",
    "sandbox_suspended",
    "sandbox_revoked",
    "case_closed",
    "transition_rejected",
    "prohibited_field_rejected",
}


def _contracts_module() -> ModuleType:
    return importlib.import_module(
        "processual_api.integrations.external_connectivity_cases"
    )


def _enum_values(enum_type: object) -> set[str]:
    return {str(item.value) for item in enum_type}


def _package(module: ModuleType, **overrides: object) -> object:
    values: dict[str, object] = {
        "package_id": "ecpkg_case001_v1",
        "case_id": "eccase_001",
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
    values.update(overrides)
    return module.CustomerReferencePackage(**values)


def _case(module: ModuleType, **overrides: object) -> object:
    state = module.ExternalConnectivityCaseState.DRAFT
    values: dict[str, object] = {
        "case_id": "eccase_001",
        "client_id": "client_001",
        "readiness_case_id": "readiness_case_001",
        "integration_task_id": "",
        "connector_id": "telecom_crm_reference",
        "credential_profile_id": "oauth2_client_credentials_reference",
        "target_environment": "sandbox",
        "state": state,
        "customer_package_fingerprint": "",
        "readiness_assessment_id": "",
        "revision": 1,
        "created_at": "2026-07-14T10:00:00Z",
        "updated_at": "2026-07-14T10:00:00Z",
    }
    values.update(overrides)
    return module.ExternalConnectivityCase(**values)


def _assessment(
    module: ModuleType,
    *,
    package_fingerprint: str,
    **overrides: object,
) -> object:
    values: dict[str, object] = {
        "assessment_id": "ecassessment_001",
        "case_id": "eccase_001",
        "customer_package_fingerprint": package_fingerprint,
        "assessment_schema_version": (
            "external-connectivity-readiness-assessment/v1"
        ),
        "readiness_status": "needs_remediation",
        "missing_input_codes": ("customer_crm_scope_reference",),
        "missing_control_codes": ("tls_policy_review",),
        "blocker_codes": ("tls_policy_review_required",),
        "remediation_codes": ("submit_tls_policy_reference",),
        "evidence_completeness": 0.75,
        "ready_for_supervisor_approval": False,
        "assessed_at": "2026-07-14T10:05:00Z",
    }
    values.update(overrides)
    return module.ExternalConnectivityReadinessAssessment(**values)


def test_r8_exports_required_contract_symbols() -> None:
    module = _contracts_module()

    required = {
        "EXTERNAL_CONNECTIVITY_CASE_SCHEMA_VERSION",
        "ExternalConnectivityCaseState",
        "ExternalConnectivityAuditEventType",
        "CustomerReferencePackage",
        "ExternalConnectivityReadinessAssessment",
        "ExternalConnectivityCase",
        "PROHIBITED_CUSTOMER_FIELD_NAMES",
        "ALLOWED_EXTERNAL_CONNECTIVITY_TRANSITIONS",
        "find_prohibited_customer_fields",
        "customer_reference_package_fingerprint",
        "is_external_connectivity_transition_allowed",
        "advance_external_connectivity_case",
    }

    assert required.issubset(set(dir(module)))
    assert (
        module.EXTERNAL_CONNECTIVITY_CASE_SCHEMA_VERSION
        == "external-connectivity-case/v1"
    )


def test_r8_contract_dataclasses_are_frozen() -> None:
    module = _contracts_module()

    contract_types = (
        module.CustomerReferencePackage,
        module.ExternalConnectivityReadinessAssessment,
        module.ExternalConnectivityCase,
    )

    for contract_type in contract_types:
        assert dataclasses.is_dataclass(contract_type)
        assert contract_type.__dataclass_params__.frozen is True


def test_r8_state_catalog_is_exact_and_closed() -> None:
    module = _contracts_module()

    assert _enum_values(module.ExternalConnectivityCaseState) == EXPECTED_STATES


def test_r8_audit_taxonomy_is_exact_and_safe() -> None:
    module = _contracts_module()

    assert (
        _enum_values(module.ExternalConnectivityAuditEventType)
        == EXPECTED_AUDIT_EVENT_TYPES
    )


def test_r8_customer_package_is_reference_only() -> None:
    module = _contracts_module()
    package = _package(module)

    assert package.target_environment == "sandbox"
    assert package.target_reference_id.startswith("target_ref_")
    assert package.secret_reference_ids == ("secret_ref_crm_oauth_001",)
    assert package.dns_reference.startswith("dns_ref_")
    assert package.tls_policy_reference.startswith("tls_policy_ref_")
    assert package.certificate_reference.startswith("certificate_ref_")
    assert package.outbound_allowlist_reference.startswith("allowlist_ref_")

    forbidden_attributes = {
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

    assert forbidden_attributes.isdisjoint(
        {field.name for field in dataclasses.fields(package)}
    )


def test_r8_prohibited_field_detection_is_recursive_and_exact() -> None:
    module = _contracts_module()

    payload = {
        "client_id": "client_001",
        "credentials": {
            "api_key": "must-not-be-accepted",
            "nested": {
                "client_secret": "must-not-be-accepted",
                "password": "must-not-be-accepted",
            },
        },
        "target": {
            "private_key": "must-not-be-accepted",
        },
    }

    assert set(module.find_prohibited_customer_fields(payload)) == {
        "credentials.api_key",
        "credentials.nested.client_secret",
        "credentials.nested.password",
        "target.private_key",
    }


def test_r8_safe_reference_names_are_not_prohibited() -> None:
    module = _contracts_module()

    payload = {
        "target_reference_id": "target_ref_001",
        "secret_reference_ids": ["secret_ref_001"],
        "certificate_reference": "certificate_ref_001",
        "tls_policy_reference": "tls_ref_001",
        "safe_reference": "safe_ref_001",
    }

    assert module.find_prohibited_customer_fields(payload) == ()


def test_r8_package_fingerprint_is_deterministic_and_sha256() -> None:
    module = _contracts_module()
    package = _package(module)

    first = module.customer_reference_package_fingerprint(package)
    second = module.customer_reference_package_fingerprint(package)

    assert first == second
    assert re.fullmatch(r"[0-9a-f]{64}", first)


def test_r8_package_fingerprint_changes_with_reference_content() -> None:
    module = _contracts_module()
    package = _package(module)

    original = module.customer_reference_package_fingerprint(package)
    changed = module.customer_reference_package_fingerprint(
        replace(
            package,
            tls_policy_reference="tls_policy_ref_12_plus_002",
        )
    )

    assert original != changed


def test_r8_case_is_default_deny_and_immutable() -> None:
    module = _contracts_module()
    case = _case(module)

    assert case.state is module.ExternalConnectivityCaseState.DRAFT
    assert case.production_allowed is False
    assert case.runtime_connector_allowed is False
    assert case.external_http_allowed is False
    assert case.secret_resolution_allowed is False
    assert case.automatic_activation_allowed is False
    assert case.raw_secret_visible is False

    with pytest.raises(FrozenInstanceError):
        case.state = (
            module.ExternalConnectivityCaseState.READINESS_APPROVED
        )


def test_r8_assessment_is_default_deny_and_package_bound() -> None:
    module = _contracts_module()
    package = _package(module)
    fingerprint = module.customer_reference_package_fingerprint(package)
    assessment = _assessment(
        module,
        package_fingerprint=fingerprint,
    )

    assert assessment.customer_package_fingerprint == fingerprint
    assert assessment.ready_for_supervisor_approval is False
    assert assessment.network_access_performed is False
    assert assessment.secrets_read is False
    assert assessment.provider_sdk_initialized is False
    assert assessment.certificate_loaded is False
    assert assessment.sandbox_launched is False
    assert assessment.production_allowed is False

    with pytest.raises(FrozenInstanceError):
        assessment.readiness_status = "readiness_approved"


@pytest.mark.parametrize(
    ("current", "target"),
    [
        ("draft", "customer_package_submitted"),
        ("draft", "closed"),
        ("customer_package_submitted", "under_automated_review"),
        ("under_automated_review", "needs_remediation"),
        (
            "under_automated_review",
            "ready_for_supervisor_approval",
        ),
        ("needs_remediation", "customer_package_submitted"),
        (
            "ready_for_supervisor_approval",
            "readiness_approved",
        ),
        (
            "ready_for_supervisor_approval",
            "needs_remediation",
        ),
        ("readiness_approved", "qualification_key_issued"),
        ("qualification_key_issued", "qualification_redeemed"),
        (
            "qualification_redeemed",
            "sandbox_api_key_issued",
        ),
        (
            "sandbox_api_key_issued",
            "sandbox_authorized",
        ),
        ("sandbox_authorized", "sandbox_suspended"),
        ("sandbox_authorized", "sandbox_revoked"),
        ("sandbox_suspended", "sandbox_authorized"),
        ("sandbox_suspended", "sandbox_revoked"),
        ("sandbox_revoked", "closed"),
    ],
)
def test_r8_allowlisted_transitions(
    current: str,
    target: str,
) -> None:
    module = _contracts_module()

    assert module.is_external_connectivity_transition_allowed(
        module.ExternalConnectivityCaseState(current),
        module.ExternalConnectivityCaseState(target),
    )


@pytest.mark.parametrize(
    ("current", "target"),
    [
        ("draft", "readiness_approved"),
        ("customer_package_submitted", "sandbox_authorized"),
        ("under_automated_review", "qualification_key_issued"),
        ("needs_remediation", "readiness_approved"),
        ("readiness_approved", "sandbox_authorized"),
        ("sandbox_revoked", "sandbox_authorized"),
        ("closed", "draft"),
        ("closed", "customer_package_submitted"),
    ],
)
def test_r8_non_allowlisted_transitions_are_rejected(
    current: str,
    target: str,
) -> None:
    module = _contracts_module()

    assert not module.is_external_connectivity_transition_allowed(
        module.ExternalConnectivityCaseState(current),
        module.ExternalConnectivityCaseState(target),
    )


def test_r8_advance_returns_new_revision_without_mutating_source() -> None:
    module = _contracts_module()
    source = _case(module)

    advanced = module.advance_external_connectivity_case(
        source,
        target_state=(
            module.ExternalConnectivityCaseState.CUSTOMER_PACKAGE_SUBMITTED
        ),
        updated_at="2026-07-14T10:10:00Z",
        customer_package_fingerprint="a" * 64,
    )

    assert source.state is module.ExternalConnectivityCaseState.DRAFT
    assert source.revision == 1
    assert source.customer_package_fingerprint == ""

    assert (
        advanced.state
        is module.ExternalConnectivityCaseState.CUSTOMER_PACKAGE_SUBMITTED
    )
    assert advanced.revision == 2
    assert advanced.customer_package_fingerprint == "a" * 64
    assert advanced.updated_at == "2026-07-14T10:10:00Z"


def test_r8_advance_rejects_non_allowlisted_transition() -> None:
    module = _contracts_module()
    source = _case(module)

    with pytest.raises(
        ValueError,
        match="external_connectivity_transition_not_allowed",
    ):
        module.advance_external_connectivity_case(
            source,
            target_state=(
                module.ExternalConnectivityCaseState.READINESS_APPROVED
            ),
            updated_at="2026-07-14T10:10:00Z",
        )


def test_r8_contract_module_has_no_network_runtime_or_secret_sdk() -> None:
    module = _contracts_module()
    source = Path(module.__file__).read_text(encoding="utf-8")

    prohibited_source_markers = (
        "import requests",
        "import httpx",
        "import socket",
        "import subprocess",
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

    for marker in prohibited_source_markers:
        assert marker not in source
