"""Immutable registry of disabled future Telecom connector contracts.

The registry contains architecture references only. It does not contain
endpoints, target aliases, secret references, transports, dispatch logic, or
executable connector behavior.
"""

from __future__ import annotations

from types import MappingProxyType

from processual_api.integrations.runtime_contracts import (
    ConnectorCapability,
    ConnectorCapabilityAccess,
    ConnectorRuntimeContract,
    normalize_runtime_connector_id,
)

_TELECOM_AUTHENTICATION_PROFILE = "telecom_operations_api_reference"

_DECLARED_ENVIRONMENTS: tuple[str, ...] = (
    "sandbox",
    "production",
)

_PENDING_EXTERNAL_API_VERSION = "pending_operator_input"


def _capability(
    capability_id: str,
    scope_id: str,
    access_mode: ConnectorCapabilityAccess,
) -> ConnectorCapability:
    """Build a disabled capability with scope-consistent approval posture."""

    return ConnectorCapability(
        capability_id=capability_id,
        scope_id=scope_id,
        access_mode=access_mode,
        approval_required=access_mode != "read",
        sandbox_only=access_mode != "read",
    )


_RUNTIME_CONNECTOR_CONTRACTS: dict[
    str,
    ConnectorRuntimeContract,
] = {
    "telecom_crm_reference": ConnectorRuntimeContract(
        connector_id="telecom_crm_reference",
        display_name="Telecom CRM Runtime Reference",
        connector_version="1.0.0-draft",
        adapter_contract_id="crm",
        contract_family="proprietary",
        supported_environments=_DECLARED_ENVIRONMENTS,
        capabilities=(
            _capability(
                "customer.read.minimal",
                "crm:read",
                "read",
            ),
            _capability(
                "customer.update.restricted",
                "customer:update",
                "restricted",
            ),
            _capability(
                "customer.record.update.restricted",
                "customer_record:update",
                "restricted",
            ),
        ),
        authentication_profile_ids=(
            _TELECOM_AUTHENTICATION_PROFILE,
        ),
        data_classifications=(
            "customer_confidential",
            "subscriber_personal",
        ),
        mapping_version="telecom-crm-map-1",
        external_api_version=_PENDING_EXTERNAL_API_VERSION,
    ),
    "telecom_billing_reference": ConnectorRuntimeContract(
        connector_id="telecom_billing_reference",
        display_name="Telecom Billing Runtime Reference",
        connector_version="1.0.0-draft",
        adapter_contract_id="billing",
        contract_family="legacy",
        supported_environments=_DECLARED_ENVIRONMENTS,
        capabilities=(
            _capability(
                "billing.read.summary",
                "billing:read",
                "read",
            ),
            _capability(
                "billing.adjust.restricted",
                "billing:adjust",
                "restricted",
            ),
        ),
        authentication_profile_ids=(
            _TELECOM_AUTHENTICATION_PROFILE,
        ),
        data_classifications=(
            "customer_confidential",
            "subscriber_personal",
            "billing_sensitive",
        ),
        mapping_version="telecom-billing-map-1",
        external_api_version=_PENDING_EXTERNAL_API_VERSION,
    ),
    "telecom_ticketing_reference": ConnectorRuntimeContract(
        connector_id="telecom_ticketing_reference",
        display_name="Telecom Ticketing Runtime Reference",
        connector_version="1.0.0-draft",
        adapter_contract_id="ticketing",
        contract_family="tm_forum",
        supported_environments=_DECLARED_ENVIRONMENTS,
        capabilities=(
            _capability(
                "ticket.read",
                "ticket:read",
                "read",
            ),
            _capability(
                "helpdesk.read",
                "helpdesk:read",
                "read",
            ),
            _capability(
                "ticket.create.sandbox",
                "ticket:create",
                "write",
            ),
            _capability(
                "ticket.update.sandbox",
                "ticket:update",
                "write",
            ),
            _capability(
                "helpdesk.create.sandbox",
                "helpdesk:create",
                "write",
            ),
        ),
        authentication_profile_ids=(
            _TELECOM_AUTHENTICATION_PROFILE,
        ),
        data_classifications=(
            "internal",
            "customer_confidential",
            "subscriber_personal",
        ),
        mapping_version="telecom-ticketing-map-1",
        external_api_version=_PENDING_EXTERNAL_API_VERSION,
    ),
    "telecom_order_management_reference": ConnectorRuntimeContract(
        connector_id="telecom_order_management_reference",
        display_name="Telecom Order Management Runtime Reference",
        connector_version="1.0.0-draft",
        adapter_contract_id="order_management",
        contract_family="tm_forum",
        supported_environments=_DECLARED_ENVIRONMENTS,
        capabilities=(
            _capability(
                "service.order.plan",
                "order:preview",
                "read",
            ),
            _capability(
                "service.order.create.sandbox",
                "order:create_with_approval",
                "write",
            ),
            _capability(
                "service.order.execute.restricted",
                "order:execute",
                "restricted",
            ),
        ),
        authentication_profile_ids=(
            _TELECOM_AUTHENTICATION_PROFILE,
        ),
        data_classifications=(
            "internal",
            "customer_confidential",
            "subscriber_personal",
        ),
        mapping_version="telecom-order-map-1",
        external_api_version=_PENDING_EXTERNAL_API_VERSION,
    ),
    "telecom_network_assurance_reference": ConnectorRuntimeContract(
        connector_id="telecom_network_assurance_reference",
        display_name="Telecom Network Assurance Runtime Reference",
        connector_version="1.0.0-draft",
        adapter_contract_id="network_assurance",
        contract_family="proprietary",
        supported_environments=_DECLARED_ENVIRONMENTS,
        capabilities=(
            _capability(
                "network.read",
                "network:read",
                "read",
            ),
            _capability(
                "network.diagnostics.read",
                "network:diagnostics_read",
                "read",
            ),
            _capability(
                "network.write.restricted",
                "network:write",
                "restricted",
            ),
        ),
        authentication_profile_ids=(
            _TELECOM_AUTHENTICATION_PROFILE,
        ),
        data_classifications=(
            "internal",
            "customer_confidential",
            "network_operational",
        ),
        mapping_version="telecom-network-assurance-map-1",
        external_api_version=_PENDING_EXTERNAL_API_VERSION,
    ),
    "enterprise_document_reference": ConnectorRuntimeContract(
        connector_id="enterprise_document_reference",
        display_name="Enterprise Document Runtime Reference",
        connector_version="1.0.0-draft",
        adapter_contract_id="document",
        contract_family="generic_enterprise",
        supported_environments=_DECLARED_ENVIRONMENTS,
        capabilities=(
            _capability(
                "document.read",
                "document:read",
                "read",
            ),
            _capability(
                "document.classify",
                "document:classify",
                "read",
            ),
            _capability(
                "compliance.document.read",
                "compliance_document:read",
                "read",
            ),
            _capability(
                "paper.read",
                "paper:read",
                "read",
            ),
            _capability(
                "response.draft.sandbox",
                "response:draft",
                "write",
            ),
            _capability(
                "analysis.report.draft.sandbox",
                "analysis_report:draft",
                "write",
            ),
            _capability(
                "dataset.export.sensitive.restricted",
                "dataset:export_sensitive",
                "restricted",
            ),
        ),
        authentication_profile_ids=(
            "document_repository_reference",
        ),
        data_classifications=(
            "internal",
            "customer_confidential",
        ),
        mapping_version="enterprise-document-map-1",
        external_api_version=_PENDING_EXTERNAL_API_VERSION,
    ),
    "enterprise_helpdesk_reference": ConnectorRuntimeContract(
        connector_id="enterprise_helpdesk_reference",
        display_name="Enterprise Helpdesk Runtime Reference",
        connector_version="1.0.0-draft",
        adapter_contract_id="enterprise_helpdesk",
        contract_family="generic_enterprise",
        supported_environments=_DECLARED_ENVIRONMENTS,
        capabilities=(
            _capability(
                "helpdesk.read",
                "helpdesk:read",
                "read",
            ),
            _capability(
                "project.read",
                "project:read",
                "read",
            ),
            _capability(
                "knowledge.base.read",
                "knowledge_base:read",
                "read",
            ),
            _capability(
                "helpdesk.create.sandbox",
                "helpdesk:create",
                "write",
            ),
            _capability(
                "project.update.draft.sandbox",
                "project_update:draft",
                "write",
            ),
            _capability(
                "email.response.draft.sandbox",
                "email_response:draft",
                "write",
            ),
            _capability(
                "hr.record.update.restricted",
                "hr_record:update",
                "restricted",
            ),
            _capability(
                "procurement.approve.restricted",
                "procurement:approve",
                "restricted",
            ),
            _capability(
                "contract.sign.restricted",
                "contract:sign",
                "restricted",
            ),
        ),
        authentication_profile_ids=(
            "enterprise_core_api_reference",
        ),
        data_classifications=(
            "internal",
            "customer_confidential",
        ),
        mapping_version="enterprise-helpdesk-map-1",
        external_api_version=_PENDING_EXTERNAL_API_VERSION,
    ),
    "banking_kyc_reference": ConnectorRuntimeContract(
        connector_id="banking_kyc_reference",
        display_name="Banking KYC Runtime Reference",
        connector_version="1.0.0-draft",
        adapter_contract_id="banking_kyc",
        contract_family="proprietary",
        supported_environments=_DECLARED_ENVIRONMENTS,
        capabilities=(
            _capability(
                "customer.case.read",
                "customer_case:read",
                "read",
            ),
            _capability(
                "kyc.document.read",
                "kyc_document:read",
                "read",
            ),
            _capability(
                "risk.case.read",
                "risk_case:read",
                "read",
            ),
            _capability(
                "risk.case.summarize",
                "risk_case:summarize",
                "read",
            ),
            _capability(
                "compliance.document.read",
                "compliance_document:read",
                "read",
            ),
            _capability(
                "compliance.ticket.create.sandbox",
                "compliance_ticket:create",
                "write",
            ),
            _capability(
                "internal.note.draft.sandbox",
                "internal_note:draft",
                "write",
            ),
            _capability(
                "account.update.restricted",
                "account:update",
                "restricted",
            ),
            _capability(
                "transaction.execute.restricted",
                "transaction:execute",
                "restricted",
            ),
            _capability(
                "credit.decision.approve.restricted",
                "credit_decision:approve",
                "restricted",
            ),
            _capability(
                "kyc.status.finalize.restricted",
                "kyc_status:finalize",
                "restricted",
            ),
        ),
        authentication_profile_ids=(
            "banking_kyc_api_reference",
        ),
        data_classifications=(
            "customer_confidential",
            "subscriber_personal",
            "billing_sensitive",
        ),
        mapping_version="banking-kyc-map-1",
        external_api_version=_PENDING_EXTERNAL_API_VERSION,
    ),
    "government_case_reference": ConnectorRuntimeContract(
        connector_id="government_case_reference",
        display_name="Government Case Runtime Reference",
        connector_version="1.0.0-draft",
        adapter_contract_id="government_case",
        contract_family="proprietary",
        supported_environments=_DECLARED_ENVIRONMENTS,
        capabilities=(
            _capability(
                "case.read",
                "case:read",
                "read",
            ),
            _capability(
                "case.summarize",
                "case:summarize",
                "read",
            ),
            _capability(
                "audit.record.read",
                "audit_record:read",
                "read",
            ),
            _capability(
                "response.draft.sandbox",
                "response:draft",
                "write",
            ),
            _capability(
                "workflow.route.sandbox",
                "workflow:route",
                "write",
            ),
            _capability(
                "status.update.with.approval.sandbox",
                "status:update_with_approval",
                "write",
            ),
            _capability(
                "permit.approve.restricted",
                "permit:approve",
                "restricted",
            ),
            _capability(
                "benefit.approve.restricted",
                "benefit:approve",
                "restricted",
            ),
            _capability(
                "citizen.record.update.restricted",
                "citizen_record:update",
                "restricted",
            ),
            _capability(
                "case.close.final.restricted",
                "case:close_final",
                "restricted",
            ),
        ),
        authentication_profile_ids=(
            "government_case_api_reference",
        ),
        data_classifications=(
            "internal",
            "customer_confidential",
            "subscriber_personal",
        ),
        mapping_version="government-case-map-1",
        external_api_version=_PENDING_EXTERNAL_API_VERSION,
    ),
    "research_dataset_reference": ConnectorRuntimeContract(
        connector_id="research_dataset_reference",
        display_name="Research Dataset Runtime Reference",
        connector_version="1.0.0-draft",
        adapter_contract_id="research_dataset",
        contract_family="generic_enterprise",
        supported_environments=_DECLARED_ENVIRONMENTS,
        capabilities=(
            _capability(
                "dataset.read",
                "dataset:read",
                "read",
            ),
            _capability(
                "experiment.read",
                "experiment:read",
                "read",
            ),
            _capability(
                "project.status.read",
                "project_status:read",
                "read",
            ),
            _capability(
                "experiment.note.draft.sandbox",
                "experiment_note:draft",
                "write",
            ),
            _capability(
                "analysis.report.draft.sandbox",
                "analysis_report:draft",
                "write",
            ),
            _capability(
                "project.update.draft.sandbox",
                "project_update:draft",
                "write",
            ),
            _capability(
                "dataset.export.sensitive.restricted",
                "dataset:export_sensitive",
                "restricted",
            ),
            _capability(
                "embargoed.result.publish.restricted",
                "embargoed_result:publish",
                "restricted",
            ),
            _capability(
                "access.grant.approve.restricted",
                "access_grant:approve",
                "restricted",
            ),
            _capability(
                "experiment.record.finalize.restricted",
                "experiment_record:finalize",
                "restricted",
            ),
        ),
        authentication_profile_ids=(
            "research_dataset_api_reference",
        ),
        data_classifications=(
            "internal",
            "customer_confidential",
        ),
        mapping_version="research-dataset-map-1",
        external_api_version=_PENDING_EXTERNAL_API_VERSION,
    ),
    "university_student_reference": ConnectorRuntimeContract(
        connector_id="university_student_reference",
        display_name="University Student Runtime Reference",
        connector_version="1.0.0-draft",
        adapter_contract_id="university_student",
        contract_family="proprietary",
        supported_environments=_DECLARED_ENVIRONMENTS,
        capabilities=(
            _capability(
                "student.request.read",
                "student_request:read",
                "read",
            ),
            _capability(
                "course.catalog.read",
                "course_catalog:read",
                "read",
            ),
            _capability(
                "admission.case.read",
                "admission_case:read",
                "read",
            ),
            _capability(
                "department.ticket.create.sandbox",
                "department_ticket:create",
                "write",
            ),
            _capability(
                "admission.case.draft.response.sandbox",
                "admission_case:draft_response",
                "write",
            ),
            _capability(
                "student.request.draft.response.sandbox",
                "student_request:draft_response",
                "write",
            ),
            _capability(
                "grade.update.restricted",
                "grade:update",
                "restricted",
            ),
            _capability(
                "student.record.update.restricted",
                "student_record:update",
                "restricted",
            ),
            _capability(
                "admission.decision.approve.restricted",
                "admission_decision:approve",
                "restricted",
            ),
            _capability(
                "disciplinary.case.update.restricted",
                "disciplinary_case:update",
                "restricted",
            ),
        ),
        authentication_profile_ids=(
            "university_student_api_reference",
        ),
        data_classifications=(
            "internal",
            "customer_confidential",
            "subscriber_personal",
        ),
        mapping_version="university-student-map-1",
        external_api_version=_PENDING_EXTERNAL_API_VERSION,
    ),
}


for _connector_id, _contract in _RUNTIME_CONNECTOR_CONTRACTS.items():
    if _connector_id != _contract.connector_id:
        raise ValueError(
            f"Registry id '{_connector_id}' does not match "
            f"contract id '{_contract.connector_id}'."
        )


RUNTIME_CONNECTOR_CONTRACTS = MappingProxyType(
    _RUNTIME_CONNECTOR_CONTRACTS
)

SUPPORTED_RUNTIME_CONNECTORS: tuple[str, ...] = tuple(
    RUNTIME_CONNECTOR_CONTRACTS
)


def list_runtime_connector_contracts() -> tuple[
    ConnectorRuntimeContract,
    ...,
]:
    """Return all runtime contracts in stable registry order."""

    return tuple(
        RUNTIME_CONNECTOR_CONTRACTS[connector_id]
        for connector_id in SUPPORTED_RUNTIME_CONNECTORS
    )


def get_runtime_connector_contract(
    connector_id: str,
) -> ConnectorRuntimeContract:
    """Return a runtime connector contract by normalized identifier."""

    normalized_id = normalize_runtime_connector_id(connector_id)

    try:
        return RUNTIME_CONNECTOR_CONTRACTS[normalized_id]
    except KeyError as exc:
        supported = ", ".join(SUPPORTED_RUNTIME_CONNECTORS)

        raise KeyError(
            f"Unsupported runtime connector '{connector_id}'. "
            f"Supported connectors: {supported}."
        ) from exc


def list_runtime_connectors_for_adapter(
    adapter_contract_id: str,
) -> tuple[ConnectorRuntimeContract, ...]:
    """Return contracts linked to one declarative adapter contract."""

    normalized_adapter_id = (
        adapter_contract_id.strip().lower().replace("-", "_")
    )

    return tuple(
        contract
        for contract in list_runtime_connector_contracts()
        if contract.adapter_contract_id == normalized_adapter_id
    )


def list_runtime_connectors_for_family(
    contract_family: str,
) -> tuple[ConnectorRuntimeContract, ...]:
    """Return contracts that declare one contract family."""

    normalized_family = (
        contract_family.strip().lower().replace("-", "_")
    )

    return tuple(
        contract
        for contract in list_runtime_connector_contracts()
        if contract.contract_family == normalized_family
    )


def validate_runtime_connector_registry() -> tuple[str, ...]:
    """Return deterministic registry integrity issues."""

    issues: list[str] = []

    if set(RUNTIME_CONNECTOR_CONTRACTS) != set(
        SUPPORTED_RUNTIME_CONNECTORS
    ):
        issues.append(
            "Supported runtime connector ids do not match the registry."
        )

    for connector_id, contract in RUNTIME_CONNECTOR_CONTRACTS.items():
        if connector_id != contract.connector_id:
            issues.append(
                f"Registry id '{connector_id}' does not match contract id."
            )

        if contract.runtime_enabled:
            issues.append(
                f"Connector '{connector_id}' enables runtime."
            )

        if contract.external_http_enabled:
            issues.append(
                f"Connector '{connector_id}' enables external HTTP."
            )

        if contract.production_allowed:
            issues.append(
                f"Connector '{connector_id}' allows production."
            )

        if contract.read_allowed or contract.write_allowed:
            issues.append(
                f"Connector '{connector_id}' allows operations."
            )

    return tuple(issues)


__all__ = [
    "RUNTIME_CONNECTOR_CONTRACTS",
    "SUPPORTED_RUNTIME_CONNECTORS",
    "get_runtime_connector_contract",
    "list_runtime_connector_contracts",
    "list_runtime_connectors_for_adapter",
    "list_runtime_connectors_for_family",
    "validate_runtime_connector_registry",
]
