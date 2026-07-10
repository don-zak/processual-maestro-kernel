"""Read-only supervisor readiness actions for operator pilot handoff 14D."""

from __future__ import annotations

from typing import Final

from processual_api.services.operator_pilot_handoff import (
    build_operator_pilot_handoff_package,
)

ACTION_PLAN_PHASE_ID: Final[str] = "operator-pilot-handoff-actions-14d"
ACTION_PLAN_STATUS: Final[str] = "draft_review"
ACTION_STATUS_PENDING: Final[str] = "pending_operator_input"
ACTION_EXECUTION_MODE: Final[str] = "copy_only"


READINESS_ACTIONS_14D: Final[tuple[dict[str, object], ...]] = (
    {
        "action_id": "request_api_documentation",
        "label": "Request API documentation",
        "description": "Prepare a request for the operator API documentation set.",
        "required_from": "operator_integration_team",
        "supervisor_note": "Copy the request note for supervisor-reviewed delivery.",
    },
    {
        "action_id": "request_sandbox_base_url",
        "label": "Request sandbox base URL",
        "description": "Prepare a request for a non-production sandbox base URL.",
        "required_from": "operator_integration_team",
        "supervisor_note": "Sandbox information only; no connection is attempted.",
    },
    {
        "action_id": "request_authentication_method",
        "label": "Request authentication method",
        "description": "Request the documented authentication method without secret material.",
        "required_from": "operator_security_team",
        "supervisor_note": "Do not request or store tokens, passwords, or private keys.",
    },
    {
        "action_id": "request_scope_matrix",
        "label": "Request scope matrix",
        "description": "Request the documented read and optional write scope matrix.",
        "required_from": "operator_integration_team",
        "supervisor_note": "Scope review does not grant runtime or production access.",
    },
    {
        "action_id": "request_sample_payloads",
        "label": "Request sample payloads",
        "description": "Request sanitized request and response examples for review.",
        "required_from": "operator_integration_team",
        "supervisor_note": "Examples must exclude customer and secret data.",
    },
    {
        "action_id": "request_rate_limits",
        "label": "Request rate limits",
        "description": "Request documented sandbox limits and throttling behavior.",
        "required_from": "operator_integration_team",
        "supervisor_note": "Documentation review only; no traffic is generated.",
    },
    {
        "action_id": "request_error_contracts",
        "label": "Request error contracts",
        "description": "Request documented error codes and retry guidance.",
        "required_from": "operator_integration_team",
        "supervisor_note": "No automatic retry or external request is enabled.",
    },
    {
        "action_id": "request_security_contact",
        "label": "Request security contact",
        "description": "Request the approved security coordination role or mailbox.",
        "required_from": "operator_security_team",
        "supervisor_note": "Contact metadata remains an operator-provided input.",
    },
    {
        "action_id": "request_privacy_contact",
        "label": "Request privacy contact",
        "description": "Request the approved privacy or data protection contact.",
        "required_from": "operator_privacy_team",
        "supervisor_note": "No personal data exchange is initiated.",
    },
    {
        "action_id": "request_pilot_success_criteria",
        "label": "Request pilot success criteria",
        "description": "Request measurable sandbox pilot acceptance criteria.",
        "required_from": "operator_program_owner",
        "supervisor_note": "Criteria remain draft until supervisor review.",
    },
    {
        "action_id": "request_test_window",
        "label": "Request test window",
        "description": "Request a proposed sandbox test window and constraints.",
        "required_from": "operator_program_owner",
        "supervisor_note": "This action does not schedule or activate a connector.",
    },
    {
        "action_id": "request_support_escalation_path",
        "label": "Request support escalation path",
        "description": "Request the documented pilot support and escalation path.",
        "required_from": "operator_support_team",
        "supervisor_note": "Copy-only preparation; no message is sent automatically.",
    },
)


def _build_action(definition: dict[str, object]) -> dict[str, object]:
    """Return one normalized, read-only readiness action."""

    return {
        **definition,
        "status": ACTION_STATUS_PENDING,
        "execution_mode": ACTION_EXECUTION_MODE,
        "safe_to_execute": True,
        "requires_credentials": False,
        "requires_production": False,
        "runtime_connector_approved": False,
        "external_http_allowed": False,
        "persistent_write_allowed": False,
    }


def build_operator_pilot_handoff_actions_preview() -> dict[str, object]:
    """Build the safe 14D supervisor readiness actions preview."""

    handoff_package = build_operator_pilot_handoff_package()
    actions = [_build_action(definition) for definition in READINESS_ACTIONS_14D]

    return {
        "phase_id": ACTION_PLAN_PHASE_ID,
        "package_id": handoff_package.get(
            "package_id",
            "operator-pilot-handoff-14a",
        ),
        "action_plan_status": ACTION_PLAN_STATUS,
        "handoff_status": handoff_package.get(
            "handoff_status",
            "pending_operator_inputs",
        ),
        "pilot_ready": False,
        "read_only": True,
        "preview_only": True,
        "action_count": len(actions),
        "actions": actions,
        "guardrails": {
            "production_allowed": False,
            "runtime_connector_approved": False,
            "customer_credentials_present": False,
            "external_http_allowed": False,
            "persistent_write_allowed": False,
            "automatic_activation_allowed": False,
        },
    }
