from pathlib import Path

import pytest

from processual_api.integrations import (
    INTEGRATION_SECTOR_PROFILES,
    SUPPORTED_SECTORS,
    get_sector_profile,
    list_sector_profiles,
)

DOC = Path("docs/integrations/INTEGRATION_ADAPTERS_11A.md")


def _doc_text():
    return " ".join(DOC.read_text(encoding="utf-8").lower().split())


def test_integration_adapters_11a_document_exists():
    assert DOC.exists()


def test_supported_sector_profiles_are_declared():
    expected_sectors = {
        "telecom",
        "banking",
        "government",
        "research",
        "university",
        "enterprise",
    }

    assert set(SUPPORTED_SECTORS) == expected_sectors
    assert set(INTEGRATION_SECTOR_PROFILES) == expected_sectors
    assert {
        profile.sector_id for profile in list_sector_profiles()
    } == expected_sectors


def test_all_sector_profiles_require_review_and_sandbox_first():
    required_prerequisites = {
        "api_documentation",
        "sandbox_access",
        "test_credentials_policy",
        "scope_matrix",
        "technical_contact",
        "acceptance_criteria",
        "security_requirements",
    }

    for profile in list_sector_profiles():
        assert profile.requires_enterprise_review is True
        assert profile.production_write_requires_supervisor is True
        assert profile.requires_sandbox_before_production is True
        assert profile.supports_read_only_pilot is True
        assert required_prerequisites.issubset(profile.customer_prerequisites)
        assert profile.adapter_domains
        assert profile.read_scopes
        assert profile.restricted_scopes


def test_telecom_profile_covers_expected_domains_and_restricted_actions():
    profile = get_sector_profile("telecom")

    assert {
        "crm",
        "billing",
        "ticketing",
        "order_management",
        "product_catalog",
        "network_assurance",
        "oss_bss",
        "api_gateway",
    }.issubset(profile.adapter_domains)
    assert "billing:read" in profile.read_scopes
    assert "ticket:create" in profile.write_scopes
    assert "billing:adjust" in profile.restricted_scopes
    assert "network:write" in profile.restricted_scopes


def test_banking_profile_blocks_money_movement_by_default():
    profile = get_sector_profile("banking")

    assert "kyc_workflow" in profile.adapter_domains
    assert "customer_case:read" in profile.read_scopes
    assert "compliance_ticket:create" in profile.write_scopes
    assert "transaction:execute" in profile.restricted_scopes
    assert "credit_decision:approve" in profile.restricted_scopes


def test_government_research_university_profiles_cover_sensitive_workflows():
    government = get_sector_profile("government")
    research = get_sector_profile("research")
    university = get_sector_profile("university")

    assert "citizen_requests" in government.adapter_domains
    assert "permit:approve" in government.restricted_scopes
    assert "dataset_catalog" in research.adapter_domains
    assert "embargoed_result:publish" in research.restricted_scopes
    assert "student_services" in university.adapter_domains
    assert "grade:update" in university.restricted_scopes


def test_generic_enterprise_profile_supports_broad_business_workflows():
    profile = get_sector_profile("enterprise")

    assert "crm" in profile.adapter_domains
    assert "helpdesk" in profile.adapter_domains
    assert "knowledge_base" in profile.adapter_domains
    assert "helpdesk:create" in profile.write_scopes
    assert "contract:sign" in profile.restricted_scopes


def test_unknown_sector_raises_helpful_error():
    with pytest.raises(KeyError) as exc_info:
        get_sector_profile("unknown-sector")

    message = str(exc_info.value).lower()
    assert "unsupported integration sector" in message
    assert "telecom" in message
    assert "banking" in message
    assert "government" in message


def test_sector_profiles_are_declarative_only_without_runtime_connectors():
    source = Path("processual_api/integrations/sector_profiles.py").read_text(
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


def test_integration_adapters_11a_document_guardrails_are_present():
    text = _doc_text()

    expected_markers = [
        "integration-adapters-11a",
        "status: `draft_review`",
        "production integration approved: `false`",
        "real credentials approved: `false`",
        "external http calls approved: `false`",
        "customer-specific connectors approved: `false`",
        "non-implementation guardrails",
        "real customer credentials",
        "production http calls",
        "customer-specific connector code",
        "direct production write actions",
        "shared readiness model",
        "require enterprise review",
        "require supervisor approval for production write actions",
        "subscription pricing and integration pricing remain separate",
        "production integration approval",
        "customer-specific api compatibility guarantee",
    ]

    for marker in expected_markers:
        assert marker in text
