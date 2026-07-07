from pathlib import Path

from processual_api.integrations import get_sector_profile
from processual_api.integrations.scope_catalog import (
    CRITICAL_RISK,
    HIGH_RISK,
    INTEGRATION_SCOPE_CATALOG,
    LOW_RISK,
    READ_ACCESS,
    RESTRICTED_ACCESS,
    SUPPORTED_INTEGRATION_SCOPES,
    WRITE_ACCESS,
    get_integration_scope,
    is_scope_allowed_in_read_only_pilot,
    list_integration_scopes,
    list_scopes_by_access_level,
    list_scopes_for_sector,
    scope_requires_supervisor_approval,
)

DOC = Path("docs/integrations/INTEGRATION_SCOPES_11B.md")


def _doc_text():
    return " ".join(DOC.read_text(encoding="utf-8").lower().split())


def test_integration_scopes_11b_document_exists():
    assert DOC.exists()


def test_scope_catalog_is_populated_from_sector_profiles():
    scopes = list_integration_scopes()

    assert scopes
    assert len(scopes) == len(SUPPORTED_INTEGRATION_SCOPES)
    assert set(INTEGRATION_SCOPE_CATALOG) == set(SUPPORTED_INTEGRATION_SCOPES)

    for sector_id in (
        "telecom",
        "banking",
        "government",
        "research",
        "university",
        "enterprise",
    ):
        sector_profile = get_sector_profile(sector_id)
        sector_scopes = {
            scope.scope_id for scope in list_scopes_for_sector(sector_id)
        }
        assert set(sector_profile.read_scopes).issubset(sector_scopes)
        assert set(sector_profile.write_scopes).issubset(sector_scopes)
        assert set(sector_profile.restricted_scopes).issubset(sector_scopes)


def test_read_write_and_restricted_scopes_have_expected_posture():
    read_scope = get_integration_scope("crm:read")
    write_scope = get_integration_scope("ticket:create")
    restricted_scope = get_integration_scope("billing:adjust")

    assert read_scope.access_level == READ_ACCESS
    assert read_scope.risk_level == LOW_RISK
    assert read_scope.allowed_in_read_only_pilot is True
    assert read_scope.requires_supervisor_approval is False
    assert read_scope.supported_key_profiles == (
        "external_partner",
        "service_integration",
    )

    assert write_scope.access_level == WRITE_ACCESS
    assert write_scope.risk_level == HIGH_RISK
    assert write_scope.allowed_in_read_only_pilot is False
    assert write_scope.requires_supervisor_approval is True
    assert write_scope.supported_key_profiles == ("service_integration",)

    assert restricted_scope.access_level == RESTRICTED_ACCESS
    assert restricted_scope.risk_level == CRITICAL_RISK
    assert restricted_scope.allowed_in_read_only_pilot is False
    assert restricted_scope.requires_supervisor_approval is True
    assert restricted_scope.supported_key_profiles == ()


def test_duplicate_scope_records_merge_sector_membership():
    scope = get_integration_scope("crm:read")

    assert "telecom" in scope.sectors
    assert "enterprise" in scope.sectors
    assert scope.domain == "crm"
    assert scope.action == "read"


def test_sector_scope_listing_supports_hyphenated_names():
    research_scopes = list_scopes_for_sector("research")
    telecom_scopes = list_scopes_for_sector("telecom")

    assert any(scope.scope_id == "dataset:read" for scope in research_scopes)
    assert any(scope.scope_id == "network:write" for scope in telecom_scopes)


def test_scope_access_level_queries_are_stable():
    read_scopes = list_scopes_by_access_level("read")
    write_scopes = list_scopes_by_access_level("write")
    restricted_scopes = list_scopes_by_access_level("restricted")

    assert read_scopes
    assert write_scopes
    assert restricted_scopes
    assert all(scope.access_level == READ_ACCESS for scope in read_scopes)
    assert all(scope.access_level == WRITE_ACCESS for scope in write_scopes)
    assert all(
        scope.access_level == RESTRICTED_ACCESS
        for scope in restricted_scopes
    )


def test_scope_helpers_preserve_read_only_and_supervisor_rules():
    assert is_scope_allowed_in_read_only_pilot("crm:read") is True
    assert is_scope_allowed_in_read_only_pilot("ticket:create") is False
    assert is_scope_allowed_in_read_only_pilot("billing:adjust") is False

    assert scope_requires_supervisor_approval("crm:read") is False
    assert scope_requires_supervisor_approval("ticket:create") is True
    assert scope_requires_supervisor_approval("billing:adjust") is True


def test_all_scopes_require_enterprise_review_and_sandbox():
    for scope in list_integration_scopes():
        assert scope.requires_enterprise_review is True
        assert scope.requires_sandbox_before_production is True
        assert scope.production_allowed_without_approval is False


def test_unknown_scope_raises_helpful_error():
    try:
        get_integration_scope("unknown:scope")
    except KeyError as exc:
        assert "unsupported integration scope" in str(exc).lower()
    else:
        raise AssertionError("Expected KeyError for unknown scope")


def test_scope_catalog_has_no_runtime_connector_markers():
    source = Path("processual_api/integrations/scope_catalog.py").read_text(
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


def test_integration_scopes_11b_document_guardrails_are_present():
    text = _doc_text()

    expected_markers = [
        "integration-scopes-11b",
        "status: `draft_review`",
        "production connector approved: `false`",
        "real credentials approved: `false`",
        "external http calls approved: `false`",
        "customer-specific integration approved: `false`",
        "read scopes can align with",
        "`external_partner`",
        "`service_integration`",
        "write scopes can align with",
        "restricted scopes have no default key profile",
        "read-only pilots may use read scopes only",
        "write scopes require supervisor approval",
        "restricted scopes represent high-risk operations",
        "new key lifecycle separate from existing",
        "proof that a customer-sector adapter exists",
    ]

    for marker in expected_markers:
        assert marker in text
