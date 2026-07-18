"""Declarative adapter contracts for external integration readiness.

These contracts bind sector adapter domains to the 11B scope catalog. They are
intentionally non-runtime: no credentials, no endpoints, no HTTP clients, and no
customer-specific connector behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from processual_api.integrations.scope_catalog import (
    IntegrationScope,
    get_integration_scope,
)


@dataclass(frozen=True)
class IntegrationAdapterContract:
    """Review-safe adapter contract for a future customer connector."""

    contract_id: str
    display_name: str
    description: str
    sectors: tuple[str, ...]
    domains: tuple[str, ...]
    required_scopes: tuple[str, ...]
    optional_write_scopes: tuple[str, ...]
    restricted_scopes: tuple[str, ...]
    safe_operations: tuple[str, ...]
    prohibited_operations: tuple[str, ...]
    customer_prerequisites: tuple[str, ...]
    requires_enterprise_review: bool = True
    requires_sandbox_before_production: bool = True
    production_write_requires_supervisor: bool = True
    runtime_connector_approved: bool = False

    @property
    def all_scopes(self) -> tuple[str, ...]:
        """Return all scopes referenced by this contract."""

        return (
            self.required_scopes
            + self.optional_write_scopes
            + self.restricted_scopes
        )


COMMON_ADAPTER_PREREQUISITES: tuple[str, ...] = (
    "api_documentation",
    "sandbox_access",
    "test_credentials_policy",
    "scope_matrix",
    "technical_contact",
    "acceptance_criteria",
    "security_requirements",
)


def _scope(scope_id: str) -> IntegrationScope:
    return get_integration_scope(scope_id)


def _validate_contract(contract: IntegrationAdapterContract) -> None:
    if not contract.contract_id:
        raise ValueError("Adapter contract id is required.")
    if not contract.sectors:
        raise ValueError(f"{contract.contract_id} must declare sectors.")
    if not contract.domains:
        raise ValueError(f"{contract.contract_id} must declare domains.")
    if not contract.required_scopes:
        raise ValueError(
            f"{contract.contract_id} must declare required scopes."
        )

    required = set(COMMON_ADAPTER_PREREQUISITES)
    missing = required.difference(contract.customer_prerequisites)
    if missing:
        raise ValueError(
            f"{contract.contract_id} is missing prerequisites: "
            f"{', '.join(sorted(missing))}."
        )

    for scope_id in contract.all_scopes:
        _scope(scope_id)


_ADAPTER_CONTRACTS: dict[str, IntegrationAdapterContract] = {
    "crm": IntegrationAdapterContract(
        contract_id="crm",
        display_name="CRM Adapter Contract",
        description=(
            "Customer relationship and account-state adapter contract for "
            "read-only customer context and carefully scoped profile updates."
        ),
        sectors=("telecom", "enterprise"),
        domains=("crm",),
        required_scopes=("crm:read",),
        optional_write_scopes=(),
        restricted_scopes=("customer:update", "customer_record:update"),
        safe_operations=(
            "read customer context",
            "summarize customer state",
            "prepare supervisor-reviewed customer update",
        ),
        prohibited_operations=(
            "update customer data without approval",
            "write directly to production CRM",
        ),
        customer_prerequisites=COMMON_ADAPTER_PREREQUISITES,
    ),
    "billing": IntegrationAdapterContract(
        contract_id="billing",
        display_name="Billing Adapter Contract",
        description=(
            "Billing visibility adapter contract for invoice and account "
            "state review without adjustment authority."
        ),
        sectors=("telecom",),
        domains=("billing",),
        required_scopes=("billing:read",),
        optional_write_scopes=(),
        restricted_scopes=("billing:adjust",),
        safe_operations=(
            "read billing state",
            "summarize billing issue",
            "prepare billing review note",
        ),
        prohibited_operations=(
            "adjust billing without approval",
            "refund or mutate billing state",
        ),
        customer_prerequisites=COMMON_ADAPTER_PREREQUISITES,
    ),
    "ticketing": IntegrationAdapterContract(
        contract_id="ticketing",
        display_name="Ticketing Adapter Contract",
        description=(
            "Ticketing and helpdesk adapter contract for reading, drafting, "
            "creating, and updating support records under governed scopes."
        ),
        sectors=("telecom", "enterprise"),
        domains=("ticketing", "helpdesk"),
        required_scopes=("ticket:read", "helpdesk:read"),
        optional_write_scopes=(
            "ticket:create",
            "ticket:update",
            "helpdesk:create",
        ),
        restricted_scopes=(),
        safe_operations=(
            "read ticket history",
            "draft support response",
            "create ticket with governed scope",
        ),
        prohibited_operations=(
            "close regulated case without approval",
            "override ticket audit history",
        ),
        customer_prerequisites=COMMON_ADAPTER_PREREQUISITES,
    ),
    "order_management": IntegrationAdapterContract(
        contract_id="order_management",
        display_name="Order Management Adapter Contract",
        description=(
            "Order management adapter contract for previews and "
            "approval-gated order creation."
        ),
        sectors=("telecom",),
        domains=("order_management",),
        required_scopes=("order:preview",),
        optional_write_scopes=("order:create_with_approval",),
        restricted_scopes=("order:execute",),
        safe_operations=(
            "preview order impact",
            "draft order request",
            "prepare approval-gated order creation",
        ),
        prohibited_operations=(
            "execute production order without approval",
            "change customer subscription directly",
        ),
        customer_prerequisites=COMMON_ADAPTER_PREREQUISITES,
    ),
    "network_assurance": IntegrationAdapterContract(
        contract_id="network_assurance",
        display_name="Network Assurance Adapter Contract",
        description=(
            "Telecom network assurance adapter contract for diagnostics "
            "and read-only operational state."
        ),
        sectors=("telecom",),
        domains=("network_assurance", "oss_bss"),
        required_scopes=("network:read", "network:diagnostics_read"),
        optional_write_scopes=(),
        restricted_scopes=("network:write",),
        safe_operations=(
            "read network health",
            "summarize diagnostics",
            "prepare incident context",
        ),
        prohibited_operations=(
            "write to network system",
            "trigger production network changes",
        ),
        customer_prerequisites=COMMON_ADAPTER_PREREQUISITES,
    ),
    "document": IntegrationAdapterContract(
        contract_id="document",
        display_name="Document Adapter Contract",
        description=(
            "Cross-sector document adapter contract for classification, "
            "summarization, secure review, and draft responses."
        ),
        sectors=("banking", "government", "research", "enterprise"),
        domains=("documents", "secure_documents", "document_intake"),
        required_scopes=(
            "document:read",
            "document:classify",
            "compliance_document:read",
            "paper:read",
        ),
        optional_write_scopes=("response:draft", "analysis_report:draft"),
        restricted_scopes=("dataset:export_sensitive",),
        safe_operations=(
            "read approved documents",
            "classify document",
            "draft document-based response",
        ),
        prohibited_operations=(
            "export sensitive dataset without approval",
            "publish embargoed material",
        ),
        customer_prerequisites=COMMON_ADAPTER_PREREQUISITES,
    ),
    "banking_kyc": IntegrationAdapterContract(
        contract_id="banking_kyc",
        display_name="Banking KYC Adapter Contract",
        description=(
            "Banking KYC and compliance adapter contract for read-only "
            "case review, risk summaries, and governed compliance tickets."
        ),
        sectors=("banking",),
        domains=("kyc_workflow", "risk_review", "compliance"),
        required_scopes=(
            "customer_case:read",
            "kyc_document:read",
            "risk_case:read",
            "risk_case:summarize",
            "compliance_document:read",
        ),
        optional_write_scopes=(
            "compliance_ticket:create",
            "internal_note:draft",
        ),
        restricted_scopes=(
            "account:update",
            "transaction:execute",
            "credit_decision:approve",
            "kyc_status:finalize",
        ),
        safe_operations=(
            "read KYC materials",
            "summarize risk case",
            "draft compliance note",
        ),
        prohibited_operations=(
                "transaction:execute",
                "credit_decision:approve",
                "kyc_status:finalize",
                "execute transaction",
                "approve credit decision",
                "finalize KYC status",
            ),
        customer_prerequisites=COMMON_ADAPTER_PREREQUISITES,
    ),
    "government_case": IntegrationAdapterContract(
        contract_id="government_case",
        display_name="Government Case Adapter Contract",
        description=(
            "Government case management adapter contract for citizen "
            "requests, document intake, audit-heavy routing, and draft replies."
        ),
        sectors=("government",),
        domains=("case_management", "citizen_requests"),
        required_scopes=("case:read", "case:summarize", "audit_record:read"),
        optional_write_scopes=(
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
        safe_operations=(
            "read public service case",
            "summarize citizen request",
            "draft response for review",
        ),
        prohibited_operations=(
            "approve permit without review",
            "finalize benefit decision",
            "close public case without approval",
        ),
        customer_prerequisites=COMMON_ADAPTER_PREREQUISITES,
    ),
    "research_dataset": IntegrationAdapterContract(
        contract_id="research_dataset",
        display_name="Research Dataset Adapter Contract",
        description=(
            "Research dataset and experiment adapter contract for read-only "
            "dataset discovery, experiment context, and draft analysis."
        ),
        sectors=("research",),
        domains=("dataset_catalog", "experiment_records"),
        required_scopes=(
            "dataset:read",
            "experiment:read",
            "project_status:read",
        ),
        optional_write_scopes=(
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
        safe_operations=(
            "read dataset metadata",
            "summarize experiment state",
            "draft analysis report",
        ),
        prohibited_operations=(
            "export sensitive dataset",
            "publish embargoed result",
            "approve access grant",
        ),
        customer_prerequisites=COMMON_ADAPTER_PREREQUISITES,
    ),
    "university_student": IntegrationAdapterContract(
        contract_id="university_student",
        display_name="University Student Adapter Contract",
        description=(
            "University student services adapter contract for requests, "
            "course catalog, department tickets, and admissions drafting."
        ),
        sectors=("university",),
        domains=("student_services", "course_management", "admissions"),
        required_scopes=(
            "student_request:read",
            "course_catalog:read",
            "admission_case:read",
        ),
        optional_write_scopes=(
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
        safe_operations=(
            "read student request",
            "read course catalog",
            "draft admissions response",
        ),
        prohibited_operations=(
            "update grade",
            "approve admission decision",
            "update disciplinary case",
        ),
        customer_prerequisites=COMMON_ADAPTER_PREREQUISITES,
    ),
    "enterprise_helpdesk": IntegrationAdapterContract(
        contract_id="enterprise_helpdesk",
        display_name="Generic Enterprise Helpdesk Adapter Contract",
        description=(
            "Generic enterprise helpdesk and project workflow adapter "
            "contract for broad non-sector-specific business integrations."
        ),
        sectors=("enterprise",),
        domains=("helpdesk", "project_management", "knowledge_base"),
        required_scopes=(
            "helpdesk:read",
            "project:read",
            "knowledge_base:read",
        ),
        optional_write_scopes=(
            "helpdesk:create",
            "project_update:draft",
            "email_response:draft",
        ),
        restricted_scopes=(
            "hr_record:update",
            "procurement:approve",
            "contract:sign",
        ),
        safe_operations=(
            "read helpdesk issue",
            "summarize project context",
            "draft internal response",
        ),
        prohibited_operations=(
            "sign contract",
            "approve procurement",
            "update HR record",
        ),
        customer_prerequisites=COMMON_ADAPTER_PREREQUISITES,
    ),
}

for _contract in _ADAPTER_CONTRACTS.values():
    _validate_contract(_contract)

INTEGRATION_ADAPTER_CONTRACTS = MappingProxyType(_ADAPTER_CONTRACTS)
SUPPORTED_ADAPTER_CONTRACTS: tuple[str, ...] = tuple(
    INTEGRATION_ADAPTER_CONTRACTS
)


def list_adapter_contracts() -> tuple[IntegrationAdapterContract, ...]:
    """Return all adapter contracts in stable order."""

    return tuple(
        INTEGRATION_ADAPTER_CONTRACTS[contract_id]
        for contract_id in SUPPORTED_ADAPTER_CONTRACTS
    )


def get_adapter_contract(contract_id: str) -> IntegrationAdapterContract:
    """Return an adapter contract by id."""

    normalized_contract_id = contract_id.strip().lower().replace("-", "_")

    try:
        return INTEGRATION_ADAPTER_CONTRACTS[normalized_contract_id]
    except KeyError as exc:
        raise KeyError(
            f"Unsupported integration adapter contract '{contract_id}'."
        ) from exc


def list_adapter_contracts_for_sector(
    sector_id: str,
) -> tuple[IntegrationAdapterContract, ...]:
    """Return adapter contracts that support a sector."""

    normalized_sector_id = sector_id.strip().lower().replace("-", "_")

    return tuple(
        contract
        for contract in list_adapter_contracts()
        if normalized_sector_id in contract.sectors
    )


def list_adapter_contracts_for_scope(
    scope_id: str,
) -> tuple[IntegrationAdapterContract, ...]:
    """Return adapter contracts that reference a scope."""

    normalized_scope_id = scope_id.strip().lower()

    return tuple(
        contract
        for contract in list_adapter_contracts()
        if normalized_scope_id in contract.all_scopes
    )
