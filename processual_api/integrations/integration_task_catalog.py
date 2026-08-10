"""Canonical task capabilities for Enterprise Integration endpoint bindings.

This catalog turns every currently advertised safe adapter operation into a
stable Maestro task contract. It remains connector-agnostic: customer APIs map
into these canonical task inputs instead of leaking provider-specific schemas
into workflow logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from processual_api.integrations.adapter_contracts import get_adapter_contract
from processual_api.integrations.scope_catalog import get_integration_scope

READ = "read"
DRAFT = "draft"
APPROVAL_GATED_WRITE = "approval_gated_write"


@dataclass(frozen=True)
class IntegrationTaskCapability:
    task_id: str
    adapter_contract_id: str
    safe_operation: str
    operation_class: str
    required_scope_ids: tuple[str, ...]
    required_input_fields: tuple[str, ...]
    optional_input_fields: tuple[str, ...] = ()
    output_slot: str = "integration_context"
    sandbox_allowed: bool = True
    production_requires_approval: bool = True
    auto_execute_production: bool = False


def _task(
    task_id: str,
    contract_id: str,
    safe_operation: str,
    operation_class: str,
    scopes: tuple[str, ...],
    required: tuple[str, ...],
    optional: tuple[str, ...] = (),
    output_slot: str = "integration_context",
) -> IntegrationTaskCapability:
    task = IntegrationTaskCapability(
        task_id=task_id,
        adapter_contract_id=contract_id,
        safe_operation=safe_operation,
        operation_class=operation_class,
        required_scope_ids=scopes,
        required_input_fields=required,
        optional_input_fields=optional,
        output_slot=output_slot,
    )
    contract = get_adapter_contract(contract_id)
    if safe_operation not in contract.safe_operations:
        raise ValueError(
            f"Task {task_id} references undeclared safe operation {safe_operation!r}."
        )
    if not scopes:
        raise ValueError(f"Task {task_id} must require at least one scope.")
    unsupported = set(scopes) - set(contract.all_scopes)
    if unsupported:
        raise ValueError(
            f"Task {task_id} references scopes outside {contract_id}: "
            + ", ".join(sorted(unsupported))
        )
    for scope_id in scopes:
        get_integration_scope(scope_id)
    if operation_class == READ and any(
        get_integration_scope(scope_id).access_level != READ
        for scope_id in scopes
    ):
        raise ValueError(f"Read task {task_id} requires a non-read scope.")
    return task


_TASKS = {
    # CRM
    "crm.customer_context": _task(
        "crm.customer_context", "crm", "read customer context", READ,
        ("crm:read",), ("customer_id",),
        ("customer_name", "account_status", "segment", "attributes"),
        "crm_context",
    ),
    "crm.customer_state_summary": _task(
        "crm.customer_state_summary", "crm", "summarize customer state", READ,
        ("crm:read",), ("customer_id", "account_status"),
        ("customer_name", "segment", "attributes"), "crm_context",
    ),
    "crm.customer_update_draft": _task(
        "crm.customer_update_draft", "crm",
        "prepare supervisor-reviewed customer update", DRAFT,
        ("crm:read", "customer:update"),
        ("customer_id", "proposed_changes"), ("reason",), "crm_update_draft",
    ),

    # External customer billing system, distinct from Maestro commercial billing.
    "billing.account_context": _task(
        "billing.account_context", "billing", "read billing state", READ,
        ("billing:read",), ("account_id",),
        ("balance", "currency", "invoice_status", "payment_status"),
        "billing_context",
    ),
    "billing.issue_summary": _task(
        "billing.issue_summary", "billing", "summarize billing issue", READ,
        ("billing:read",), ("account_id", "issue_context"),
        ("invoice_id", "payment_id", "balance", "currency"),
        "billing_context",
    ),
    "billing.review_note": _task(
        "billing.review_note", "billing", "prepare billing review note", DRAFT,
        ("billing:read",), ("account_id", "issue_context"),
        ("invoice_id", "payment_id", "recommended_next_step"),
        "billing_review_note",
    ),

    # Ticketing / helpdesk.
    "support.ticket_history": _task(
        "support.ticket_history", "ticketing", "read ticket history", READ,
        ("ticket:read", "helpdesk:read"), ("ticket_id",),
        ("status", "messages", "requester", "assignee"), "support_context",
    ),
    "support.response_draft": _task(
        "support.response_draft", "ticketing", "draft support response", DRAFT,
        ("ticket:read", "helpdesk:read"), ("ticket_id", "issue_context"),
        ("messages", "customer_context"), "support_response_draft",
    ),
    "support.ticket_create": _task(
        "support.ticket_create", "ticketing", "create ticket with governed scope",
        APPROVAL_GATED_WRITE, ("ticket:create",),
        ("subject", "description"), ("customer_id", "priority"),
        "support_ticket_request",
    ),

    # Order management.
    "order.preview": _task(
        "order.preview", "order_management", "preview order impact", READ,
        ("order:preview",), ("customer_id", "requested_change"),
        ("current_subscription", "pricing_context"), "order_preview",
    ),
    "order.request_draft": _task(
        "order.request_draft", "order_management", "draft order request", DRAFT,
        ("order:preview",), ("customer_id", "requested_change"),
        ("impact", "pricing_context"), "order_request_draft",
    ),
    "order.approval_gated_create": _task(
        "order.approval_gated_create", "order_management",
        "prepare approval-gated order creation", APPROVAL_GATED_WRITE,
        ("order:create_with_approval",), ("customer_id", "order_payload"),
        ("approval_reference",), "order_create_request",
    ),

    # Network assurance.
    "network.health_context": _task(
        "network.health_context", "network_assurance", "read network health", READ,
        ("network:read",), ("resource_id",),
        ("status", "alarms", "metrics"), "network_context",
    ),
    "network.diagnostics_summary": _task(
        "network.diagnostics_summary", "network_assurance", "summarize diagnostics",
        READ, ("network:diagnostics_read",), ("resource_id", "diagnostics"),
        ("alarms", "metrics", "topology_context"), "network_diagnostics",
    ),
    "network.incident_context": _task(
        "network.incident_context", "network_assurance", "prepare incident context",
        READ, ("network:read", "network:diagnostics_read"),
        ("resource_id", "incident_id"),
        ("status", "diagnostics", "alarms", "metrics"), "incident_context",
    ),

    # Cross-sector document workflows.
    "document.approved_content": _task(
        "document.approved_content", "document", "read approved documents", READ,
        ("document:read",), ("document_id",),
        ("title", "content", "metadata"), "document_context",
    ),
    "document.classification": _task(
        "document.classification", "document", "classify document", READ,
        ("document:classify",), ("document_id", "content"),
        ("metadata",), "document_classification_input",
    ),
    "document.response_draft": _task(
        "document.response_draft", "document", "draft document-based response", DRAFT,
        ("document:read", "response:draft"), ("document_id", "content"),
        ("request_context", "metadata"), "document_response_draft",
    ),

    # Banking / KYC / compliance.
    "banking.kyc_materials": _task(
        "banking.kyc_materials", "banking_kyc", "read KYC materials", READ,
        ("customer_case:read", "kyc_document:read", "compliance_document:read"),
        ("case_id", "customer_id"),
        ("documents", "kyc_status", "compliance_context"), "kyc_context",
    ),
    "banking.risk_summary": _task(
        "banking.risk_summary", "banking_kyc", "summarize risk case", READ,
        ("risk_case:read", "risk_case:summarize"), ("case_id", "risk_indicators"),
        ("customer_id", "documents", "risk_status"), "risk_context",
    ),
    "banking.compliance_note_draft": _task(
        "banking.compliance_note_draft", "banking_kyc", "draft compliance note", DRAFT,
        ("customer_case:read", "internal_note:draft"),
        ("case_id", "compliance_context"), ("risk_summary", "documents"),
        "compliance_note_draft",
    ),

    # Government / public administration.
    "government.case_context": _task(
        "government.case_context", "government_case", "read public service case", READ,
        ("case:read", "audit_record:read"), ("case_id",),
        ("citizen_id", "status", "history", "audit_records"), "government_case_context",
    ),
    "government.request_summary": _task(
        "government.request_summary", "government_case", "summarize citizen request",
        READ, ("case:read", "case:summarize"), ("case_id", "request_text"),
        ("citizen_id", "history", "attachments"), "citizen_request_context",
    ),
    "government.response_draft": _task(
        "government.response_draft", "government_case", "draft response for review",
        DRAFT, ("case:read", "response:draft"), ("case_id", "request_text"),
        ("case_summary", "policy_context"), "government_response_draft",
    ),

    # Research.
    "research.dataset_context": _task(
        "research.dataset_context", "research_dataset", "read dataset metadata", READ,
        ("dataset:read",), ("dataset_id",),
        ("schema", "provenance", "access_posture"), "research_dataset_context",
    ),
    "research.experiment_context": _task(
        "research.experiment_context", "research_dataset",
        "summarize experiment state", READ,
        ("experiment:read", "project_status:read"), ("experiment_id",),
        ("project_id", "status", "metrics", "notes"), "experiment_context",
    ),
    "research.analysis_report_draft": _task(
        "research.analysis_report_draft", "research_dataset",
        "draft analysis report", DRAFT,
        ("dataset:read", "analysis_report:draft"),
        ("dataset_id", "analysis_context"), ("experiment_id", "project_id"),
        "analysis_report_draft",
    ),

    # University / student services.
    "university.student_request": _task(
        "university.student_request", "university_student", "read student request", READ,
        ("student_request:read",), ("request_id",),
        ("student_id", "request_text", "status"), "student_request_context",
    ),
    "university.course_catalog": _task(
        "university.course_catalog", "university_student", "read course catalog", READ,
        ("course_catalog:read",), ("course_id",),
        ("title", "description", "requirements", "schedule"), "course_context",
    ),
    "university.admission_response_draft": _task(
        "university.admission_response_draft", "university_student",
        "draft admissions response", DRAFT,
        ("admission_case:read", "admission_case:draft_response"),
        ("case_id", "applicant_context"), ("documents", "status"),
        "admission_response_draft",
    ),

    # Generic enterprise helpdesk/project/knowledge workflows.
    "enterprise.helpdesk_issue": _task(
        "enterprise.helpdesk_issue", "enterprise_helpdesk", "read helpdesk issue", READ,
        ("helpdesk:read",), ("issue_id",),
        ("status", "messages", "requester"), "enterprise_helpdesk_context",
    ),
    "enterprise.project_context": _task(
        "enterprise.project_context", "enterprise_helpdesk",
        "summarize project context", READ,
        ("project:read", "knowledge_base:read"), ("project_id",),
        ("status", "milestones", "knowledge_context"), "project_context",
    ),
    "enterprise.internal_response_draft": _task(
        "enterprise.internal_response_draft", "enterprise_helpdesk",
        "draft internal response", DRAFT,
        ("helpdesk:read", "email_response:draft"),
        ("issue_id", "issue_context"), ("project_context", "knowledge_context"),
        "internal_response_draft",
    ),
}

INTEGRATION_TASK_CATALOG = MappingProxyType(_TASKS)
SUPPORTED_INTEGRATION_TASKS: tuple[str, ...] = tuple(_TASKS)


def get_integration_task(task_id: str) -> IntegrationTaskCapability:
    normalized = str(task_id or "").strip().lower()
    try:
        return INTEGRATION_TASK_CATALOG[normalized]
    except KeyError as exc:
        raise KeyError(f"Unsupported integration task '{task_id}'.") from exc


def list_integration_tasks() -> tuple[IntegrationTaskCapability, ...]:
    return tuple(INTEGRATION_TASK_CATALOG[key] for key in SUPPORTED_INTEGRATION_TASKS)


def list_tasks_for_contract(contract_id: str) -> tuple[IntegrationTaskCapability, ...]:
    normalized = str(contract_id or "").strip().lower().replace("-", "_")
    get_adapter_contract(normalized)
    return tuple(
        task for task in list_integration_tasks()
        if task.adapter_contract_id == normalized
    )


def task_catalog_payload() -> dict[str, object]:
    return {
        "source": "integration_task_catalog",
        "task_count": len(INTEGRATION_TASK_CATALOG),
        "tasks": [
            {
                "task_id": task.task_id,
                "adapter_contract_id": task.adapter_contract_id,
                "safe_operation": task.safe_operation,
                "operation_class": task.operation_class,
                "required_scope_ids": list(task.required_scope_ids),
                "required_input_fields": list(task.required_input_fields),
                "optional_input_fields": list(task.optional_input_fields),
                "output_slot": task.output_slot,
                "sandbox_allowed": task.sandbox_allowed,
                "production_requires_approval": task.production_requires_approval,
                "auto_execute_production": task.auto_execute_production,
            }
            for task in list_integration_tasks()
        ],
        "production_allowed": False,
        "runtime_connector_approved": False,
    }


__all__ = [
    "APPROVAL_GATED_WRITE",
    "DRAFT",
    "INTEGRATION_TASK_CATALOG",
    "IntegrationTaskCapability",
    "READ",
    "SUPPORTED_INTEGRATION_TASKS",
    "get_integration_task",
    "list_integration_tasks",
    "list_tasks_for_contract",
    "task_catalog_payload",
]
