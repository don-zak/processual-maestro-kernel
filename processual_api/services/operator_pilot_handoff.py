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


def _handoff_14b_markdown_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "pending"
    text = str(value).strip()
    return text or "pending"


def _handoff_14b_item_label(item: object) -> str:
    if isinstance(item, dict):
        return str(
            item.get("label")
            or item.get("name")
            or item.get("input_key")
            or item.get("key")
            or "Required input"
        )
    return str(item)


def render_operator_pilot_handoff_markdown(package: dict[str, object] | None = None) -> str:
    """Render a supervisor-safe Markdown handoff package."""
    if package is None:
        package = build_operator_pilot_handoff_package()

    guardrails = dict(package.get("guardrails") or {})
    required_inputs = list(package.get("required_operator_inputs") or [])
    specializations = list(package.get("entity_specializations") or [])
    success_criteria = list(package.get("pilot_success_criteria") or [])

    lines: list[str] = [
        "# Operator Pilot Handoff",
        "",
        f"Package ID: {_handoff_14b_markdown_value(package.get('package_id'))}",
        f"Package status: {_handoff_14b_markdown_value(package.get('package_status'))}",
        f"Handoff status: {_handoff_14b_markdown_value(package.get('handoff_status'))}",
        f"Pilot ready: {_handoff_14b_markdown_value(package.get('pilot_ready'))}",
        "",
        "## Machine-readable guardrail keys",
        "",
        f"- production_allowed: {_handoff_14b_markdown_value(guardrails.get('production_allowed'))}",
        (
            "- runtime_connector_approved: "
            f"{_handoff_14b_markdown_value(guardrails.get('runtime_connector_approved'))}"
        ),
        (
            "- customer_credentials_present: "
            f"{_handoff_14b_markdown_value(guardrails.get('customer_credentials_present'))}"
        ),
        f"- external_http_allowed: {_handoff_14b_markdown_value(guardrails.get('external_http_allowed'))}",
        (
            "- production_writes_allowed: "
            f"{_handoff_14b_markdown_value(guardrails.get('production_writes_allowed'))}"
        ),
        (
            "- automatic_activation_allowed: "
            f"{_handoff_14b_markdown_value(guardrails.get('automatic_activation_allowed'))}"
        ),
        "",
        "## Supervisor meaning",
        "",
        (
            "This package prepares a sandbox-only handoff for an external "
            "organization. It does not approve production, does not store "
            "credentials, does not enable runtime connectors, and does not "
            "execute external HTTP calls."
        ),
        "",
        "## Legacy safety summary",
        "",
        "- Sandbox only.",
        "- No production endpoint is approved.",
        "- No customer credentials are accepted.",
        "- No runtime connector is approved.",
        "- No external HTTP call is executed.",
        "- Production requires a separate supervisor-approved phase.",
        "",
        "## Required organization inputs",
        "",
    ]

    for item in required_inputs:
        lines.append(f"- {_handoff_14b_item_label(item)}")

    lines.extend(["", "## Supported organization types", ""])

    for item in specializations:
        lines.append(f"- {_handoff_14b_item_label(item)}")

    lines.extend(["", "## Pilot success criteria", ""])

    if success_criteria:
        for item in success_criteria:
            lines.append(f"- {_handoff_14b_item_label(item)}")
    else:
        lines.append("- Sandbox prerequisites reviewed by supervisor.")
        lines.append("- No production approval granted by this package.")

    lines.extend(
        [
            "",
            "## Next supervisor action",
            "",
            (
                "Collect the missing organization inputs, review the sandbox "
                "contract, and keep production/runtime approval blocked until "
                "a separate supervisor-approved phase exists."
            ),
            "",
        ]
    )

    return "\n".join(lines)
