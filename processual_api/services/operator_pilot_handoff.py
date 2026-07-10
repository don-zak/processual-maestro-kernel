from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

PACKAGE_ID = "operator-pilot-handoff-14a"
PACKAGE_STATUS = "draft_review"

GUARDRAILS = {
    "sandbox_only": True,
    "production_allowed": False,
    "runtime_connector_approved": False,
    "customer_credentials_present": False,
    "external_http_allowed": False,
    "production_writes_allowed": False,
    "automatic_activation_allowed": False,
}

REQUIRED_OPERATOR_INPUTS = [
    {
        "key": "api_documentation",
        "label": "API documentation",
        "required": True,
        "status": "pending_operator",
    },
    {
        "key": "sandbox_base_url",
        "label": "Sandbox base URL",
        "required": True,
        "status": "pending_operator",
    },
    {
        "key": "authentication_method",
        "label": "Authentication method",
        "required": True,
        "status": "pending_operator",
    },
    {
        "key": "allowed_scopes_matrix",
        "label": "Allowed scopes matrix",
        "required": True,
        "status": "pending_operator",
    },
    {
        "key": "restricted_scopes_matrix",
        "label": "Restricted scopes matrix",
        "required": True,
        "status": "pending_operator",
    },
    {
        "key": "rate_limits",
        "label": "Rate limits and throttling policy",
        "required": True,
        "status": "pending_operator",
    },
    {
        "key": "sandbox_tenant",
        "label": "Test account or sandbox tenant",
        "required": True,
        "status": "pending_operator",
    },
    {
        "key": "sample_payloads",
        "label": "Sample request and response payloads",
        "required": True,
        "status": "pending_operator",
    },
    {
        "key": "error_catalog",
        "label": "Error code catalog",
        "required": True,
        "status": "pending_operator",
    },
    {
        "key": "webhook_policy",
        "label": "Callback or webhook policy",
        "required": False,
        "status": "pending_operator",
    },
    {
        "key": "data_retention",
        "label": "Data retention and masking constraints",
        "required": True,
        "status": "pending_operator",
    },
    {
        "key": "security_contact",
        "label": "Security review contact",
        "required": True,
        "status": "pending_operator",
    },
    {
        "key": "escalation_contact",
        "label": "Incident escalation contact",
        "required": True,
        "status": "pending_operator",
    },
    {
        "key": "production_approval_path",
        "label": "Production approval path",
        "required": True,
        "status": "pending_operator",
    },
]

ENTITY_SPECIALIZATIONS = [
    {
        "entity_type": "telecom_operator",
        "label": "Telecom operators",
        "domains": [
            "crm",
            "billing",
            "ticketing",
            "order_management",
            "network_assurance",
            "document_kyc",
            "enterprise_helpdesk",
        ],
    },
    {
        "entity_type": "banking_fintech",
        "label": "Banks and fintech institutions",
        "domains": [
            "kyc",
            "account_support",
            "payments_support",
            "case_management",
            "risk_review",
            "document_review",
        ],
    },
    {
        "entity_type": "government_public_services",
        "label": "Government and public services",
        "domains": [
            "citizen_case",
            "service_request",
            "permits",
            "document_verification",
            "appointment_support",
        ],
    },
    {
        "entity_type": "university_research",
        "label": "Universities and research organizations",
        "domains": [
            "student_services",
            "admissions",
            "learning_support",
            "research_dataset",
            "digital_library",
        ],
    },
    {
        "entity_type": "healthcare_admin",
        "label": "Healthcare administration",
        "domains": [
            "patient_admin",
            "appointments",
            "claims_admin",
            "document_intake",
            "non_clinical_support",
        ],
    },
    {
        "entity_type": "insurance",
        "label": "Insurance providers",
        "domains": [
            "policy_admin",
            "claims_intake",
            "broker_support",
            "document_review",
            "customer_case",
        ],
    },
    {
        "entity_type": "utilities_energy",
        "label": "Utilities and energy providers",
        "domains": [
            "customer_service",
            "metering_case",
            "billing_support",
            "field_ops_case",
            "outage_support",
        ],
    },
    {
        "entity_type": "logistics_transport",
        "label": "Logistics and transport operators",
        "domains": [
            "shipment_tracking",
            "ticketing",
            "fleet_support",
            "customs_documents",
            "customer_case",
        ],
    },
    {
        "entity_type": "enterprise_helpdesk",
        "label": "Enterprise helpdesk and service desks",
        "domains": [
            "crm",
            "ticketing",
            "asset_support",
            "it_service_management",
            "knowledge_base",
        ],
    },
    {
        "entity_type": "legal_compliance",
        "label": "Legal and compliance teams",
        "domains": [
            "case_intake",
            "document_review",
            "policy_exception",
            "audit_evidence",
            "compliance_tracking",
        ],
    },
]

REPLAY_TOOLS = [
    {
        "key": "rebuild_package",
        "label": "Rebuild safe handoff package",
        "safe_operation": True,
    },
    {
        "key": "copy_operator_checklist",
        "label": "Copy operator input checklist",
        "safe_operation": True,
    },
    {
        "key": "export_markdown",
        "label": "Export Markdown handoff",
        "safe_operation": True,
    },
    {
        "key": "review_guardrails",
        "label": "Review sandbox guardrails",
        "safe_operation": True,
    },
    {
        "key": "generate_next_actions",
        "label": "Generate supervisor next actions",
        "safe_operation": True,
    },
]

PILOT_SUCCESS_CRITERIA = [
    "Sandbox API documentation reviewed",
    "Allowed read scopes mapped",
    "Restricted write scopes documented",
    "Sample sandbox flow described",
    "Rate limits captured",
    "Audit expectations documented",
    "Rollback and stop criteria defined",
    "Supervisor sign-off required before production",
]


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def build_operator_pilot_handoff_package(
    *,
    case_id: str = "operator-pilot-handoff-case",
    operator_name: str = "Generic external organization",
    supervisor_id: str = "admin",
    requested_specializations: list[str] | None = None,
) -> dict[str, Any]:
    requested = set(requested_specializations or [])
    specializations = deepcopy(ENTITY_SPECIALIZATIONS)

    if requested:
        selected = [
            item for item in specializations if item["entity_type"] in requested
        ]
        specializations = selected or specializations

    required_inputs = deepcopy(REQUIRED_OPERATOR_INPUTS)
    required_total = sum(1 for item in required_inputs if item["required"])
    required_completed = sum(
        1
        for item in required_inputs
        if item["required"] and item["status"] == "completed"
    )

    return {
        "package_id": PACKAGE_ID,
        "package_status": PACKAGE_STATUS,
        "case_id": case_id,
        "operator_name": operator_name,
        "supervisor_id": supervisor_id,
        "handoff_status": "pending_operator_inputs",
        "pilot_ready": False,
        "production_gate_status": "blocked_pending_separate_approval",
        "guardrails": deepcopy(GUARDRAILS),
        "required_operator_inputs": required_inputs,
        "required_inputs_total": required_total,
        "required_inputs_completed": required_completed,
        "entity_specializations": specializations,
        "replay_tools": deepcopy(REPLAY_TOOLS),
        "pilot_success_criteria": deepcopy(PILOT_SUCCESS_CRITERIA),
        "supervisor_next_actions": [
            "Select the external organization type",
            "Map requested domains to adapter contracts",
            "Request sandbox documentation and test tenant",
            "Review allowed and restricted scopes",
            "Export the Markdown handoff package",
            "Block production until a separate approval phase",
        ],
        "created_at": _utc_now(),
        "updated_at": _utc_now(),
    }


def render_operator_pilot_handoff_markdown(
    package: dict[str, Any] | None = None,
) -> str:
    handoff = package or build_operator_pilot_handoff_package()
    guardrails = handoff["guardrails"]

    lines = [
        "# Operator Pilot Handoff",
        "",
        f"- Package: `{handoff['package_id']}`",
        f"- Status: `{handoff['handoff_status']}`",
        f"- Case: `{handoff['case_id']}`",
        f"- Organization: `{handoff['operator_name']}`",
        f"- Pilot ready: `{handoff['pilot_ready']}`",
        f"- Production gate: `{handoff['production_gate_status']}`",
        "",
        "## Sandbox Guardrails",
        "",
    ]

    for key, value in guardrails.items():
        lines.append(f"- `{key}`: `{value}`")

    lines.extend(["", "## Required Operator Inputs", ""])

    for item in handoff["required_operator_inputs"]:
        required = "required" if item["required"] else "optional"
        lines.append(f"- {item['label']} — {required} — `{item['status']}`")

    lines.extend(["", "## Supported Organization Types", ""])

    for item in handoff["entity_specializations"]:
        domains = ", ".join(item["domains"])
        lines.append(f"- {item['label']}: {domains}")

    lines.extend(["", "## Pilot Success Criteria", ""])

    for criterion in handoff["pilot_success_criteria"]:
        lines.append(f"- {criterion}")

    lines.extend(["", "## Supervisor Next Actions", ""])

    for action in handoff["supervisor_next_actions"]:
        lines.append(f"- {action}")

    lines.extend(
        [
            "",
            "## Explicit Blockers",
            "",
            "- No production endpoint is approved in this package.",
            "- No customer credentials are accepted in this package.",
            "- No runtime connector is approved in this package.",
            "- No external HTTP call is executed by this package.",
            "- Production requires a separate supervisor-approved phase.",
            "",
        ]
    )

    return "\n".join(lines)
