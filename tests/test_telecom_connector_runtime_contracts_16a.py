from dataclasses import fields, replace
from pathlib import Path
from types import MappingProxyType

import pytest

import processual_api.integrations as integrations
from processual_api.integrations import (
    RUNTIME_CONNECTOR_CONTRACTS,
    SUPPORTED_CONNECTOR_CONTRACT_FAMILIES,
    SUPPORTED_CONNECTOR_DATA_CLASSIFICATIONS,
    SUPPORTED_CONNECTOR_ENVIRONMENTS,
    SUPPORTED_RUNTIME_CONNECTORS,
    ConnectorCapability,
    ConnectorRuntimeContract,
    get_runtime_connector_contract,
    list_runtime_connector_contracts,
    list_runtime_connectors_for_adapter,
    list_runtime_connectors_for_family,
    validate_runtime_connector_registry,
)
from processual_api.integrations.adapter_contracts import (
    get_adapter_contract,
)
from processual_api.integrations.credential_profiles import (
    get_credential_profile,
)
from processual_api.integrations.scope_catalog import (
    get_integration_scope,
)

DOC = Path("docs/integrations/TELECOM_CONNECTIVITY_16A.md")
RUNTIME_SOURCE = Path(
    "processual_api/integrations/runtime_contracts.py"
)
REGISTRY_SOURCE = Path(
    "processual_api/integrations/connector_registry.py"
)


def _document_text() -> str:
    return " ".join(
        DOC.read_text(encoding="utf-8").lower().split()
    )


def test_telecom_connectivity_16a_document_guardrails() -> None:
    assert DOC.exists()

    text = _document_text()
    expected_markers = (
        "telecom-connectivity-16a",
        "status: `draft_review`",
        "runtime_enabled = false",
        "external_http_enabled = false",
        "production_allowed = false",
        "read_allowed = false",
        "write_allowed = false",
        "automatic_activation_allowed = false",
        "credentials_storage_allowed = false",
        "raw_secret_visible = false",
        "control plane",
        "connector data plane",
        "tm_forum",
        "camara",
        "proprietary",
        "legacy",
        "generic_enterprise",
        "pending_operator_input",
        "target aliases and secret references are deferred to 16b",
        "governed operation planning",
        "deferred to 16c",
        "disabled worker and mock dispatcher",
        "deferred to 16d",
        "production connector approval",
        "full test suite passes",
        "enterprise_document_reference",
        "enterprise_helpdesk_reference",
        "banking_kyc_reference",
        "government_case_reference",
        "research_dataset_reference",
        "university_student_reference",
        "eleven total connector references",
        "57 capability instances",
        "52 unique existing scopes",
        "r1 adds no endpoint",
    )

    for marker in expected_markers:
        assert marker in text


def test_university_document_alignment_guardrail_is_stable() -> None:
    text = _document_text()
    expected_markers = (
        "external-connectivity-16a-r2a",
        "external-connectivity-16a-r2b",
        "narrows `university_student_api_reference` to the "
        "`university_student` adapter contract only",
        "no longer references the shared `document` adapter contract",
        "does not declare the university sector",
        "`enterprise_document_reference` is not approved for "
        "university document traffic",
        "does not add the university sector to the shared document adapter",
        "does not create a `university_document` adapter",
        "creates no new integration scope, connector, endpoint, "
        "credential value, external http path, runtime permission, "
        "or production approval",
        "separately governed adapter-contract review covering data "
        "classification",
        "student privacy",
        "retention",
        "document ownership",
        "customer acceptance criteria",
        "dedicated tests",
        "r2b applies the separately reviewed profile-boundary change",
    )
    for marker in expected_markers:
        assert marker in text


def test_runtime_connector_registry_is_populated_and_immutable() -> None:
    expected_connectors = {
        "telecom_crm_reference",
        "telecom_billing_reference",
        "telecom_ticketing_reference",
        "telecom_order_management_reference",
        "telecom_network_assurance_reference",
        "enterprise_document_reference",
        "enterprise_helpdesk_reference",
        "banking_kyc_reference",
        "government_case_reference",
        "research_dataset_reference",
        "university_student_reference",
    }

    assert set(SUPPORTED_RUNTIME_CONNECTORS) == expected_connectors
    assert set(RUNTIME_CONNECTOR_CONTRACTS) == expected_connectors
    assert {
        contract.connector_id
        for contract in list_runtime_connector_contracts()
    } == expected_connectors
    assert isinstance(
        RUNTIME_CONNECTOR_CONTRACTS,
        MappingProxyType,
    )

    contract = get_runtime_connector_contract(
        "telecom_ticketing_reference"
    )

    with pytest.raises(TypeError):
        RUNTIME_CONNECTOR_CONTRACTS["forged"] = contract

    assert validate_runtime_connector_registry() == ()


def test_all_runtime_contracts_are_default_deny() -> None:
    for contract in list_runtime_connector_contracts():
        assert isinstance(contract, ConnectorRuntimeContract)
        assert contract.requires_enterprise_review is True
        assert contract.requires_sandbox_before_production is True
        assert contract.read_allowed is False
        assert contract.write_allowed is False
        assert contract.runtime_enabled is False
        assert contract.external_http_enabled is False
        assert contract.production_allowed is False
        assert contract.automatic_activation_allowed is False
        assert contract.credentials_storage_allowed is False
        assert contract.raw_secret_visible is False

        for capability in contract.capabilities:
            assert isinstance(capability, ConnectorCapability)
            assert capability.enabled is False
            assert capability.production_allowed is False


def test_runtime_contracts_reference_existing_objects() -> None:
    for contract in list_runtime_connector_contracts():
        adapter = get_adapter_contract(
            contract.adapter_contract_id
        )

        assert adapter.runtime_connector_approved is False

        for capability in contract.capabilities:
            scope = get_integration_scope(capability.scope_id)

            assert capability.scope_id in adapter.all_scopes
            assert capability.access_mode == scope.access_level
            assert (
                capability.approval_required
                is scope.requires_supervisor_approval
            )

            if capability.access_mode == "read":
                assert capability.scope_id in adapter.required_scopes
            elif capability.access_mode == "write":
                assert (
                    capability.scope_id
                    in adapter.optional_write_scopes
                )
            else:
                assert (
                    capability.scope_id
                    in adapter.restricted_scopes
                )

        for profile_id in contract.authentication_profile_ids:
            profile = get_credential_profile(profile_id)

            assert (
                contract.adapter_contract_id
                in profile.adapter_contract_ids
            )
            assert profile.approved_for_runtime is False
            assert profile.runtime_connector_approved is False


def test_capability_access_and_approval_posture() -> None:
    read_count = 0
    write_count = 0
    restricted_count = 0

    for contract in list_runtime_connector_contracts():
        for capability in contract.capabilities:
            if capability.access_mode == "read":
                read_count += 1
                assert capability.approval_required is False
                assert capability.sandbox_only is False
            elif capability.access_mode == "write":
                write_count += 1
                assert capability.approval_required is True
                assert capability.sandbox_only is True
            else:
                restricted_count += 1
                assert capability.approval_required is True
                assert capability.sandbox_only is True

    assert read_count >= 1
    assert write_count >= 1
    assert restricted_count >= 1


def test_contract_families_environments_and_data_are_bounded() -> None:
    assert set(SUPPORTED_CONNECTOR_CONTRACT_FAMILIES) == {
        "tm_forum",
        "camara",
        "proprietary",
        "legacy",
        "generic_enterprise",
    }
    assert set(SUPPORTED_CONNECTOR_ENVIRONMENTS) == {
        "sandbox",
        "production",
    }
    assert {
        "customer_confidential",
        "subscriber_personal",
        "billing_sensitive",
        "network_operational",
    }.issubset(SUPPORTED_CONNECTOR_DATA_CLASSIFICATIONS)

    for contract in list_runtime_connector_contracts():
        assert contract.contract_family in (
            SUPPORTED_CONNECTOR_CONTRACT_FAMILIES
        )
        assert set(contract.supported_environments).issubset(
            SUPPORTED_CONNECTOR_ENVIRONMENTS
        )
        assert "sandbox" in contract.supported_environments
        assert set(contract.data_classifications).issubset(
            SUPPORTED_CONNECTOR_DATA_CLASSIFICATIONS
        )
        assert (
            contract.external_api_version
            == "pending_operator_input"
        )


def test_registry_queries_are_stable_and_normalized() -> None:
    ticketing = get_runtime_connector_contract(
        "telecom-ticketing-reference"
    )

    assert ticketing.connector_id == (
        "telecom_ticketing_reference"
    )
    assert ticketing.adapter_contract_id == "ticketing"

    assert {
        contract.connector_id
        for contract in list_runtime_connectors_for_family(
            "tm-forum"
        )
    } == {
        "telecom_ticketing_reference",
        "telecom_order_management_reference",
    }

    assert {
        contract.connector_id
        for contract in list_runtime_connectors_for_adapter(
            "network-assurance"
        )
    } == {"telecom_network_assurance_reference"}

    with pytest.raises(KeyError) as exc_info:
        get_runtime_connector_contract("missing-connector")

    assert "unsupported runtime connector" in (
        str(exc_info.value).lower()
    )


def test_runtime_and_capability_flags_cannot_be_enabled() -> None:
    contract = get_runtime_connector_contract(
        "telecom_ticketing_reference"
    )

    forbidden_contract_flags = (
        "read_allowed",
        "write_allowed",
        "runtime_enabled",
        "external_http_enabled",
        "production_allowed",
        "automatic_activation_allowed",
        "credentials_storage_allowed",
        "raw_secret_visible",
    )

    for field_name in forbidden_contract_flags:
        with pytest.raises(ValueError):
            replace(contract, **{field_name: True})

    capability = contract.capabilities[0]

    with pytest.raises(ValueError):
        replace(capability, enabled=True)

    with pytest.raises(ValueError):
        replace(capability, production_allowed=True)


def test_models_exclude_targets_and_secret_material() -> None:
    contract_fields = {
        field.name for field in fields(ConnectorRuntimeContract)
    }
    capability_fields = {
        field.name for field in fields(ConnectorCapability)
    }

    forbidden_fields = {
        "url",
        "base_url",
        "endpoint",
        "endpoint_url",
        "target_alias",
        "target_host",
        "target_port",
        "secret",
        "secret_value",
        "secret_ref",
        "password",
        "api_key",
        "access_token",
        "private_key",
        "certificate_data",
    }

    assert forbidden_fields.isdisjoint(contract_fields)
    assert forbidden_fields.isdisjoint(capability_fields)


def test_runtime_modules_have_no_network_or_secret_assignments() -> None:
    combined_source = "\n".join(
        (
            RUNTIME_SOURCE.read_text(
                encoding="utf-8"
            ).lower(),
            REGISTRY_SOURCE.read_text(
                encoding="utf-8"
            ).lower(),
        )
    )

    forbidden_markers = (
        "requests.",
        "httpx.",
        "aiohttp",
        "urllib.request",
        "socket.",
        "urlopen",
        "asyncclient",
        "clientsession",
        "subprocess",
        "os.environ",
        "http://",
        "https://",
        "client_secret =",
        "secret =",
        "secret_value =",
        "password =",
        "api_key =",
        "access_token =",
        "private_key =",
        "certificate_data =",
        "connection_string =",
    )

    for marker in forbidden_markers:
        assert marker not in combined_source


def test_public_package_exports_preserve_existing_contracts() -> None:
    required_exports = {
        "RUNTIME_CONNECTOR_CONTRACTS",
        "SUPPORTED_CONNECTOR_CONTRACT_FAMILIES",
        "SUPPORTED_CONNECTOR_DATA_CLASSIFICATIONS",
        "SUPPORTED_CONNECTOR_ENVIRONMENTS",
        "SUPPORTED_RUNTIME_CONNECTORS",
        "ConnectorCapability",
        "ConnectorCapabilityAccess",
        "ConnectorContractFamily",
        "ConnectorRuntimeContract",
        "get_runtime_connector_contract",
        "list_runtime_connector_contracts",
        "list_runtime_connectors_for_adapter",
        "list_runtime_connectors_for_family",
        "normalize_runtime_connector_id",
        "validate_runtime_connector_registry",
    }

    assert required_exports.issubset(integrations.__all__)
    assert len(integrations.__all__) == len(
        set(integrations.__all__)
    )

    assert hasattr(integrations, "IntegrationAdapterContract")
    assert hasattr(integrations, "CredentialProfile")
    assert hasattr(integrations, "IntegrationReadinessCheck")
    assert hasattr(integrations, "get_integration_scope")
    assert hasattr(integrations, "get_sector_profile")

def test_shared_and_sector_runtime_references_are_registered() -> None:
    expected = {
        "enterprise_document_reference": (
            "document",
            "document_repository_reference",
            7,
        ),
        "enterprise_helpdesk_reference": (
            "enterprise_helpdesk",
            "enterprise_core_api_reference",
            9,
        ),
        "banking_kyc_reference": (
            "banking_kyc",
            "banking_kyc_api_reference",
            11,
        ),
        "government_case_reference": (
            "government_case",
            "government_case_api_reference",
            10,
        ),
        "research_dataset_reference": (
            "research_dataset",
            "research_dataset_api_reference",
            10,
        ),
        "university_student_reference": (
            "university_student",
            "university_student_api_reference",
            10,
        ),
    }

    contracts = {
        contract.connector_id: contract
        for contract in list_runtime_connector_contracts()
    }

    assert len(contracts) == 11
    assert set(expected).issubset(contracts)

    new_contracts = tuple(
        contracts[connector_id]
        for connector_id in expected
    )

    assert sum(
        len(contract.capabilities)
        for contract in new_contracts
    ) == 57

    assert len({
        capability.scope_id
        for contract in new_contracts
        for capability in contract.capabilities
    }) == 52

    for connector_id, values in expected.items():
        adapter_id, profile_id, capability_count = values
        contract = get_runtime_connector_contract(connector_id)

        assert contract.adapter_contract_id == adapter_id
        assert contract.authentication_profile_ids == (
            profile_id,
        )
        assert len(contract.capabilities) == capability_count
        assert contract.runtime_enabled is False
        assert contract.external_http_enabled is False
        assert contract.production_allowed is False
        assert contract.read_allowed is False
        assert contract.write_allowed is False
        assert contract.credentials_storage_allowed is False
        assert contract.raw_secret_visible is False

    assert {
        contract.connector_id
        for contract in list_runtime_connectors_for_family(
            "generic-enterprise"
        )
    } == {
        "enterprise_document_reference",
        "enterprise_helpdesk_reference",
        "research_dataset_reference",
    }
