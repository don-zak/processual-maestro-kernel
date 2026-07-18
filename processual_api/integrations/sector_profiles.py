"""Sector adapter profiles for external integration readiness.

This module defines a safe, declarative umbrella for future external integrations.
It intentionally contains no credentials, no customer endpoints, no HTTP clients,
and no production connector behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class SectorAdapterProfile:
    """Review-safe integration profile for a customer sector."""

    sector_id: str
    display_name: str
    description: str
    adapter_domains: tuple[str, ...]
    read_scopes: tuple[str, ...]
    write_scopes: tuple[str, ...]
    restricted_scopes: tuple[str, ...]
    customer_prerequisites: tuple[str, ...]
    requires_enterprise_review: bool = True
    production_write_requires_supervisor: bool = True
    requires_sandbox_before_production: bool = True
    supports_read_only_pilot: bool = True

    @property
    def all_scopes(self) -> tuple[str, ...]:
        """Return all declared scopes without changing their review posture."""

        return self.read_scopes + self.write_scopes + self.restricted_scopes


COMMON_CUSTOMER_PREREQUISITES: tuple[str, ...] = (
    "api_documentation",
    "sandbox_access",
    "test_credentials_policy",
    "scope_matrix",
    "technical_contact",
    "acceptance_criteria",
    "security_requirements",
)


_SECTOR_PROFILES: dict[str, SectorAdapterProfile] = {
    "telecom": SectorAdapterProfile(
        sector_id="telecom",
        display_name="Telecom",
        description=(
            "Telecom integration profile for CRM, billing, ticketing, "
            "orders, product catalog, network assurance, OSS/BSS, and "
            "API gateway workflows."
        ),
        adapter_domains=(
            "crm",
            "billing",
            "ticketing",
            "order_management",
            "product_catalog",
            "network_assurance",
            "oss_bss",
            "api_gateway",
        ),
        read_scopes=(
            "crm:read",
            "billing:read",
            "ticket:read",
            "order:preview",
            "product_catalog:read",
            "network:read",
            "network:diagnostics_read",
        ),
        write_scopes=(
            "ticket:create",
            "ticket:update",
            "order:create_with_approval",
        ),
        restricted_scopes=(
            "billing:adjust",
            "customer:update",
            "order:execute",
            "network:write",
        ),
        customer_prerequisites=COMMON_CUSTOMER_PREREQUISITES,
    ),
    "banking": SectorAdapterProfile(
        sector_id="banking",
        display_name="Banking",
        description=(
            "Banking integration profile for customer cases, KYC review, "
            "risk workflows, compliance documents, secure document exchange, "
            "and internal case management."
        ),
        adapter_domains=(
            "customer_cases",
            "kyc_workflow",
            "risk_review",
            "compliance",
            "secure_documents",
            "internal_ticketing",
            "product_eligibility",
        ),
        read_scopes=(
            "customer_case:read",
            "kyc_document:read",
            "risk_case:read",
            "risk_case:summarize",
            "compliance_document:read",
            "product_eligibility:read",
        ),
        write_scopes=(
            "compliance_ticket:create",
            "internal_note:draft",
        ),
        restricted_scopes=(
            "account:update",
            "transaction:execute",
            "credit_decision:approve",
            "kyc_status:finalize",
        ),
        customer_prerequisites=COMMON_CUSTOMER_PREREQUISITES,
    ),
    "government": SectorAdapterProfile(
        sector_id="government",
        display_name="Government",
        description=(
            "Government integration profile for citizen requests, public "
            "service cases, permits, document intake, correspondence, "
            "records retention, and audit-heavy workflows."
        ),
        adapter_domains=(
            "citizen_requests",
            "case_management",
            "permits",
            "document_intake",
            "internal_correspondence",
            "audit_records",
            "public_service_workflow",
        ),
        read_scopes=(
            "case:read",
            "case:summarize",
            "document:read",
            "document:classify",
            "audit_record:read",
        ),
        write_scopes=(
            "response:draft",
            "workflow:route",
            "status:update_with_approval",
        ),
        restricted_scopes=(
            "permit:approve",
            "benefit:approve",
            "citizen_record:update",
            "case:close_final",
        ),
        customer_prerequisites=COMMON_CUSTOMER_PREREQUISITES,
    ),
    "research": SectorAdapterProfile(
        sector_id="research",
        display_name="Research Center",
        description=(
            "Research integration profile for dataset catalogs, experiment "
            "records, literature workflows, lab notes, project tracking, "
            "model evaluation, and secure research document analysis."
        ),
        adapter_domains=(
            "dataset_catalog",
            "experiment_records",
            "literature_workflows",
            "project_tracking",
            "lab_notes",
            "model_evaluation",
            "secure_research_documents",
        ),
        read_scopes=(
            "dataset:read",
            "paper:read",
            "paper:summarize",
            "experiment:read",
            "project_status:read",
            "model_evaluation:read",
        ),
        write_scopes=(
            "experiment_note:draft",
            "analysis_report:draft",
            "project_update:draft",
        ),
        restricted_scopes=(
            "dataset:export_sensitive",
            "embargoed_result:publish",
            "access_grant:approve",
            "experiment_record:finalize",
        ),
        customer_prerequisites=COMMON_CUSTOMER_PREREQUISITES,
    ),
    "university": SectorAdapterProfile(
        sector_id="university",
        display_name="University",
        description=(
            "University integration profile for student services, course "
            "management, admissions support, research administration, "
            "department workflows, and academic helpdesk."
        ),
        adapter_domains=(
            "student_services",
            "course_management",
            "research_administration",
            "admissions",
            "department_workflows",
            "academic_helpdesk",
            "library_services",
        ),
        read_scopes=(
            "student_request:read",
            "course_catalog:read",
            "department_ticket:read",
            "admission_case:read",
            "research_project:read",
        ),
        write_scopes=(
            "department_ticket:create",
            "admission_case:draft_response",
            "student_request:draft_response",
        ),
        restricted_scopes=(
            "grade:update",
            "student_record:update",
            "admission_decision:approve",
            "disciplinary_case:update",
        ),
        customer_prerequisites=COMMON_CUSTOMER_PREREQUISITES,
    ),
    "enterprise": SectorAdapterProfile(
        sector_id="enterprise",
        display_name="Generic Enterprise",
        description=(
            "Generic enterprise integration profile for CRM, helpdesk, "
            "documents, HR requests, procurement, project management, "
            "knowledge bases, and internal operations workflows."
        ),
        adapter_domains=(
            "crm",
            "helpdesk",
            "documents",
            "hr_requests",
            "procurement",
            "project_management",
            "knowledge_base",
            "email_workflow",
        ),
        read_scopes=(
            "crm:read",
            "helpdesk:read",
            "document:read",
            "project:read",
            "knowledge_base:read",
            "procurement:read",
        ),
        write_scopes=(
            "helpdesk:create",
            "internal_note:draft",
            "project_update:draft",
            "email_response:draft",
        ),
        restricted_scopes=(
            "hr_record:update",
            "procurement:approve",
            "contract:sign",
            "customer_record:update",
        ),
        customer_prerequisites=COMMON_CUSTOMER_PREREQUISITES,
    ),
}

SUPPORTED_SECTORS: tuple[str, ...] = tuple(_SECTOR_PROFILES)
INTEGRATION_SECTOR_PROFILES = MappingProxyType(_SECTOR_PROFILES)


def list_sector_profiles() -> tuple[SectorAdapterProfile, ...]:
    """Return all review-safe sector adapter profiles."""

    return tuple(INTEGRATION_SECTOR_PROFILES[sector] for sector in SUPPORTED_SECTORS)


def get_sector_profile(sector_id: str) -> SectorAdapterProfile:
    """Return a sector adapter profile by id."""

    normalized_sector_id = sector_id.strip().lower().replace("_", "-")
    normalized_sector_id = normalized_sector_id.replace("-", "_")

    try:
        return INTEGRATION_SECTOR_PROFILES[normalized_sector_id]
    except KeyError as exc:
        supported = ", ".join(SUPPORTED_SECTORS)
        raise KeyError(
            f"Unsupported integration sector '{sector_id}'. "
            f"Supported sectors: {supported}."
        ) from exc
