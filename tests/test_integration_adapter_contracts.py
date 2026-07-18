from pathlib import Path

from processual_api.integrations.adapter_contracts import (
    INTEGRATION_ADAPTER_CONTRACTS,
    SUPPORTED_ADAPTER_CONTRACTS,
    get_adapter_contract,
    list_adapter_contracts,
    list_adapter_contracts_for_scope,
    list_adapter_contracts_for_sector,
)
from processual_api.integrations.scope_catalog import get_integration_scope

DOC = Path("docs/integrations/INTEGRATION_ADAPTERS_11C.md")


def _doc_text():
    return " ".join(DOC.read_text(encoding="utf-8").lower().split())


def test_integration_adapters_11c_document_exists():
    assert DOC.exists()


def test_adapter_contract_catalog_is_populated():
    expected_contracts = {
        "crm",
        "billing",
        "ticketing",
        "order_management",
        "network_assurance",
        "document",
        "banking_kyc",
        "government_case",
        "research_dataset",
        "university_student",
        "enterprise_helpdesk",
    }

    assert set(SUPPORTED_ADAPTER_CONTRACTS) == expected_contracts
    assert set(INTEGRATION_ADAPTER_CONTRACTS) == expected_contracts
    assert {
        contract.contract_id for contract in list_adapter_contracts()
    } == expected_contracts


def test_every_adapter_contract_references_existing_scopes():
    for contract in list_adapter_contracts():
        assert contract.required_scopes
        assert contract.customer_prerequisites
        assert contract.requires_enterprise_review is True
        assert contract.requires_sandbox_before_production is True
        assert contract.production_write_requires_supervisor is True
        assert contract.runtime_connector_approved is False

        for scope_id in contract.all_scopes:
            scope = get_integration_scope(scope_id)
            assert scope.scope_id == scope_id


def test_contracts_cover_core_telecom_domains():
    crm = get_adapter_contract("crm")
    billing = get_adapter_contract("billing")
    network = get_adapter_contract("network-assurance")

    assert "telecom" in crm.sectors
    assert "crm:read" in crm.required_scopes
    assert "customer:update" in crm.restricted_scopes

    assert billing.sectors == ("telecom",)
    assert "billing:read" in billing.required_scopes
    assert "billing:adjust" in billing.restricted_scopes

    assert "network:diagnostics_read" in network.required_scopes
    assert "network:write" in network.restricted_scopes


def test_contracts_cover_banking_government_research_and_university():
    banking = get_adapter_contract("banking_kyc")
    government = get_adapter_contract("government_case")
    research = get_adapter_contract("research_dataset")
    university = get_adapter_contract("university_student")

    assert "kyc_document:read" in banking.required_scopes
    assert "transaction:execute" in banking.restricted_scopes
    assert "credit_decision:approve" in banking.prohibited_operations

    assert "case:read" in government.required_scopes
    assert "permit:approve" in government.restricted_scopes

    assert "dataset:read" in research.required_scopes
    assert "embargoed_result:publish" in research.restricted_scopes

    assert "student_request:read" in university.required_scopes
    assert "grade:update" in university.restricted_scopes


def test_contracts_can_be_listed_by_sector_and_scope():
    telecom_contracts = {
        contract.contract_id
        for contract in list_adapter_contracts_for_sector("telecom")
    }
    crm_contracts = {
        contract.contract_id
        for contract in list_adapter_contracts_for_scope("crm:read")
    }

    assert {
        "crm",
        "billing",
        "ticketing",
        "order_management",
        "network_assurance",
    }.issubset(telecom_contracts)
    assert crm_contracts == {"crm"}


def test_adapter_contracts_enforce_customer_prerequisites():
    required = {
        "api_documentation",
        "sandbox_access",
        "test_credentials_policy",
        "scope_matrix",
        "technical_contact",
        "acceptance_criteria",
        "security_requirements",
    }

    for contract in list_adapter_contracts():
        assert required.issubset(contract.customer_prerequisites)


def test_adapter_contracts_have_no_runtime_connector_markers():
    source = Path("processual_api/integrations/adapter_contracts.py").read_text(
        encoding="utf-8"
    )
    lowered_source = source.lower()

    forbidden_runtime_markers = [
        "requests.",
        "httpx.",
        "aiohttp.",
        "urllib.request",
        "socket.",
        "os.environ",
        "subprocess.",
        "secret =",
        "password =",
    ]

    for marker in forbidden_runtime_markers:
        assert marker not in lowered_source


def test_integration_adapters_11c_document_guardrails_are_present():
    text = _doc_text()

    expected_markers = [
        "integration-adapters-11c",
        "status: `draft_review`",
        "runtime connector approved: `false`",
        "real credentials approved: `false`",
        "external http calls approved: `false`",
        "customer-specific connector approved: `false`",
        "every adapter contract must reference scopes from the 11b",
        "must not invent a scope outside the catalog",
        "non-runtime guardrails",
        "real customer endpoints",
        "real customer credentials",
        "external http calls",
        "customer-specific connector runtime",
        "direct customer database access",
        "`external_partner`",
        "`service_integration`",
        "must not create a second key lifecycle",
        "proof that a customer-specific connector exists",
    ]

    for marker in expected_markers:
        assert marker in text
