from pathlib import Path

import pytest

from processual_api.integrations import (
    CredentialProfile,
    get_credential_profile,
    list_credential_profiles,
    validate_credential_profiles,
)
from processual_api.integrations.credential_profiles import (
    COMMON_FORBIDDEN_SECRET_MATERIAL,
    COMMON_REQUIRED_CUSTOMER_INPUTS,
    COMMON_REQUIRED_SECURITY_CONTROLS,
)


def _adapter_contract_ids() -> set[str]:
    from processual_api.integrations import adapter_contracts

    if hasattr(adapter_contracts, "list_adapter_contracts"):
        return {
            contract.contract_id
            for contract in adapter_contracts.list_adapter_contracts()
        }

    registry = getattr(adapter_contracts, "ADAPTER_CONTRACTS", ())
    if isinstance(registry, dict):
        return {contract.contract_id for contract in registry.values()}

    return {contract.contract_id for contract in registry}


def test_credential_profiles_are_declared() -> None:
    profiles = list_credential_profiles()

    assert profiles
    assert all(isinstance(profile, CredentialProfile) for profile in profiles)
    assert {
        profile.credential_profile_id for profile in profiles
    } >= {
        "enterprise_core_api_reference",
        "telecom_operations_api_reference",
        "document_repository_reference",
        "banking_kyc_api_reference",
        "government_case_api_reference",
        "research_dataset_api_reference",
        "university_student_api_reference",
    }


def test_get_credential_profile_by_id() -> None:
    profile = get_credential_profile("telecom_operations_api_reference")

    assert profile.display_name == "Telecom Operations API Reference"

    with pytest.raises(KeyError):
        get_credential_profile("missing_profile")


def test_profiles_are_non_runtime_and_non_connector_approved() -> None:
    for profile in list_credential_profiles():
        assert profile.approved_for_runtime is False
        assert profile.runtime_connector_approved is False
        assert profile.readiness_status in {
            "draft_review",
            "blocked_pending_customer_inputs",
            "not_runtime_approved",
        }


def test_profiles_require_customer_and_security_readiness() -> None:
    for profile in list_credential_profiles():
        assert profile.sandbox_required is True
        assert profile.production_credential_approval_required is True
        assert profile.technical_contact_required is True
        assert profile.security_review_required is True
        assert profile.rotation_policy_required is True
        assert profile.customer_endpoint_inventory_required is True

        assert set(COMMON_REQUIRED_CUSTOMER_INPUTS).issubset(
            set(profile.required_customer_inputs)
        )
        assert set(COMMON_REQUIRED_SECURITY_CONTROLS).issubset(
            set(profile.required_security_controls)
        )
        assert set(COMMON_FORBIDDEN_SECRET_MATERIAL).issubset(
            set(profile.forbidden_secret_material)
        )


def test_supported_auth_methods_are_references_only() -> None:
    for profile in list_credential_profiles():
        assert profile.supported_auth_methods
        assert all(
            auth_method.endswith("_reference")
            for auth_method in profile.supported_auth_methods
        )


def test_profiles_reference_existing_adapter_contracts() -> None:
    adapter_contract_ids = _adapter_contract_ids()
    referenced_contract_ids: set[str] = set()

    for profile in list_credential_profiles():
        assert profile.adapter_contract_ids
        referenced_contract_ids.update(profile.adapter_contract_ids)

    assert referenced_contract_ids.issubset(adapter_contract_ids)


def test_all_adapter_contracts_are_covered_by_a_credential_profile() -> None:
    adapter_contract_ids = _adapter_contract_ids()
    referenced_contract_ids = {
        contract_id
        for profile in list_credential_profiles()
        for contract_id in profile.adapter_contract_ids
    }

    assert adapter_contract_ids.issubset(referenced_contract_ids)


def test_credential_profile_validation_has_no_issues() -> None:
    assert validate_credential_profiles() == ()


def test_credential_profiles_do_not_add_runtime_network_clients() -> None:
    source = Path(
        "processual_api/integrations/credential_profiles.py"
    ).read_text(encoding="utf-8")

    forbidden_runtime_markers = (
        "requests.",
        "httpx.",
        "aiohttp",
        "urllib.request",
        "socket.",
        "subprocess",
        "os.environ",
        "http://",
        "https://",
    )

    for marker in forbidden_runtime_markers:
        assert marker not in source


def test_credential_profiles_do_not_assign_secret_values() -> None:
    source = Path(
        "processual_api/integrations/credential_profiles.py"
    ).read_text(encoding="utf-8").lower()

    forbidden_assignments = (
        "client_secret =",
        "secret =",
        "password =",
        "api_key =",
        "token =",
        "private_key =",
        "connection_string =",
    )

    for marker in forbidden_assignments:
        assert marker not in source


def test_document_records_11d_guardrails() -> None:
    document = Path(
        "docs/integrations/INTEGRATION_CREDENTIALS_11D.md"
    ).read_text(encoding="utf-8")

    assert "approved_for_runtime = false" in document
    assert "runtime_connector_approved = false" in document
    assert "sandbox_required = true" in document
    assert "security_review_required = true" in document
    assert "external HTTP calls" in document
    assert "real credentials" in document
