from __future__ import annotations

from copy import deepcopy
from typing import Any

PACKAGE_VERSION_12C = "operator-readiness-package-12c"
PACKAGE_STATUS_12C = "draft_review"
HANDOFF_STATUS_12C = "pilot_handoff_pending_operator_inputs"


def _guardrails_12c() -> dict[str, bool]:
    return {
        "production_allowed": False,
        "runtime_connector_approved": False,
        "external_http_enabled": False,
        "raw_secret_visible": False,
    }


def _safe_text_12c(value: object, *, max_len: int = 160) -> str:
    text = str(value or "").strip()
    text = text.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    while "  " in text:
        text = text.replace("  ", " ")
    return text[:max_len]


def _operator_required_inputs_12c() -> list[dict[str, str]]:
    return [
        {
            "item_key": "operator_api_documentation_reference",
            "label": "Operator API documentation reference",
            "purpose": "Identify approved internal API documentation.",
            "required_before": "sandbox_pilot",
        },
        {
            "item_key": "sandbox_endpoint_reference",
            "label": "Sandbox endpoint reference",
            "purpose": "Identify non-production endpoint family by reference only.",
            "required_before": "sandbox_pilot",
        },
        {
            "item_key": "auth_method_reference",
            "label": "Authentication method reference",
            "purpose": "Confirm OAuth, mTLS, API key, or gateway policy.",
            "required_before": "sandbox_pilot",
        },
        {
            "item_key": "allowed_scopes_matrix",
            "label": "Allowed scopes matrix",
            "purpose": "Map read/write scopes to approved Maestro workflows.",
            "required_before": "sandbox_pilot",
        },
        {
            "item_key": "rate_limit_policy",
            "label": "Rate limit policy",
            "purpose": "Define quotas, bursts, retries, and backoff rules.",
            "required_before": "sandbox_pilot",
        },
        {
            "item_key": "test_account_reference",
            "label": "Test account reference",
            "purpose": "Reference approved synthetic accounts or fixtures.",
            "required_before": "sandbox_pilot",
        },
        {
            "item_key": "incident_escalation_path",
            "label": "Incident escalation path",
            "purpose": "Define technical, security, and pilot escalation owners.",
            "required_before": "pilot_launch",
        },
        {
            "item_key": "production_approval_path",
            "label": "Production approval path",
            "purpose": "Identify approval chain for any future production connector.",
            "required_before": "production_review",
        },
    ]


def _pilot_handoff_steps_12c() -> list[dict[str, str]]:
    return [
        {
            "step_key": "operator_intake_review",
            "label": "Operator intake review",
            "status": "pending_operator_input",
        },
        {
            "step_key": "sandbox_contract_review",
            "label": "Sandbox contract review",
            "status": "pending_operator_input",
        },
        {
            "step_key": "security_scope_mapping",
            "label": "Security and scope mapping",
            "status": "pending_supervisor_review",
        },
        {
            "step_key": "pilot_success_criteria",
            "label": "Pilot success criteria",
            "status": "draft_review",
        },
        {
            "step_key": "production_gate_review",
            "label": "Production gate review",
            "status": "blocked_until_operator_approval",
        },
    ]


def _production_blockers_12c() -> list[dict[str, str]]:
    return [
        {
            "blocker_key": "no_operator_production_approval",
            "label": "No operator production approval",
            "resolution": "Requires written operator production sign-off.",
        },
        {
            "blocker_key": "no_runtime_connector_approval",
            "label": "Runtime connector approval is disabled",
            "resolution": "Requires supervisor and enterprise review.",
        },
        {
            "blocker_key": "no_customer_endpoint_binding",
            "label": "No customer endpoint binding",
            "resolution": "Use references only until sandbox contract is approved.",
        },
        {
            "blocker_key": "no_customer_credentials",
            "label": "No customer credentials",
            "resolution": "Credentials must stay outside this package and masked.",
        },
    ]


def _case_rows_12c(cases_payload: dict[str, Any]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []

    for case in cases_payload.get("cases", []):
        if not isinstance(case, dict):
            continue

        rows.append(
            {
                "case_id": _safe_text_12c(case.get("case_id"), max_len=240),
                "client_id": _safe_text_12c(case.get("client_id")),
                "request_id": _safe_text_12c(case.get("request_id")),
                "adapter_id": _safe_text_12c(case.get("adapter_id")),
                "status": _safe_text_12c(case.get("status")),
                "provided_inputs": int(case.get("provided_inputs") or 0),
                "verified_items": int(case.get("verified_items") or 0),
                "rejected_items": int(case.get("rejected_items") or 0),
                "timeline_events": int(case.get("timeline_events") or 0),
                **_guardrails_12c(),
            }
        )

    return rows


def build_operator_readiness_package_12c() -> dict[str, object]:
    from processual_api.services.integration_readiness_tracking_store import (
        build_tracking_summary_12a_compat,
        list_tracking_cases_12a,
    )

    tracking_summary = build_tracking_summary_12a_compat()
    cases_payload = list_tracking_cases_12a()
    cases = _case_rows_12c(cases_payload)

    return {
        "package_version": PACKAGE_VERSION_12C,
        "package_status": PACKAGE_STATUS_12C,
        "handoff_status": HANDOFF_STATUS_12C,
        "audience": "operator_integration_supervisors",
        "purpose": "Prepare safe API integration review and pilot handoff.",
        "tracking_summary": deepcopy(tracking_summary),
        "cases": cases,
        "case_count": len(cases),
        "operator_required_inputs": _operator_required_inputs_12c(),
        "pilot_handoff_steps": _pilot_handoff_steps_12c(),
        "production_blockers": _production_blockers_12c(),
        "pilot_handoff_ready": False,
        "sandbox_ready": False,
        "production_ready": False,
        "requires_operator_inputs": True,
        "requires_supervisor_review": True,
        "safe_export_available": True,
        "external_connector_execution": False,
        "customer_credentials_required_in_package": False,
        "customer_endpoint_required_in_package": False,
        **_guardrails_12c(),
    }


def _bool_markdown_12c(value: object) -> str:
    return "true" if bool(value) else "false"


def render_operator_readiness_markdown_12c() -> str:
    package = build_operator_readiness_package_12c()

    lines = [
        "# Operator Readiness Package - 12C",
        "",
        f"Package version: {package['package_version']}",
        f"Package status: {package['package_status']}",
        f"Handoff status: {package['handoff_status']}",
        "",
        "## Purpose",
        "",
        str(package["purpose"]),
        "",
        "## Current guardrails",
        "",
        f"- production_allowed: {_bool_markdown_12c(package['production_allowed'])}",
        f"- runtime_connector_approved: {_bool_markdown_12c(package['runtime_connector_approved'])}",
        f"- external_http_enabled: {_bool_markdown_12c(package['external_http_enabled'])}",
        f"- raw_secret_visible: {_bool_markdown_12c(package['raw_secret_visible'])}",
        "",
        "## Readiness case summary",
        "",
        f"- case_count: {package['case_count']}",
        f"- pilot_handoff_ready: {_bool_markdown_12c(package['pilot_handoff_ready'])}",
        f"- sandbox_ready: {_bool_markdown_12c(package['sandbox_ready'])}",
        f"- production_ready: {_bool_markdown_12c(package['production_ready'])}",
        "",
        "## Operator required inputs",
        "",
    ]

    for item in package["operator_required_inputs"]:
        lines.append(
            "- {} - {} Required before {}.".format(
                item["item_key"],
                item["purpose"],
                item["required_before"],
            )
        )

    lines.extend(["", "## Pilot handoff steps", ""])

    for step in package["pilot_handoff_steps"]:
        lines.append(
            "- {} - {}: {}.".format(
                step["step_key"],
                step["label"],
                step["status"],
            )
        )

    lines.extend(["", "## Production blockers", ""])

    for blocker in package["production_blockers"]:
        lines.append(
            "- {} - {} Resolution: {}".format(
                blocker["blocker_key"],
                blocker["label"],
                blocker["resolution"],
            )
        )

    lines.extend(
        [
            "",
            "## Safety statement",
            "",
            "This package is a safe review and pilot handoff artifact only.",
            "It does not enable production connectors, external HTTP, live endpoints,",
            "or customer credential handling.",
            "",
        ]
    )

    return "\n".join(lines)
