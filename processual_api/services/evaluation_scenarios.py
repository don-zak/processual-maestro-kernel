from __future__ import annotations

from typing import Any

from processual_api.integrations.enterprise_endpoint_bindings import BINDING_STORAGE_KEY
from processual_api.services.evaluation_grants import EVALUATION_TASK_EXECUTE_ENDPOINT

_SCENARIOS: tuple[dict[str, Any], ...] = (
    {
        "scenario_id": "CRM-CONTEXT-01",
        "title": "CRM Customer Context Review",
        "task_id": "crm.customer_context",
        "kind": "safe_read",
        "customer_value": (
            "Read and normalize a sandbox customer context through a governed Maestro task."
        ),
        "success_signal": (
            "The task is admitted, executed through the prepared sandbox binding, "
            "and durable evidence is persisted."
        ),
        "sample_input": {"customer_id": "sandbox-customer-001"},
    },
    {
        "scenario_id": "CRM-SUMMARY-01",
        "title": "CRM Customer State Summary",
        "task_id": "crm.customer_state_summary",
        "kind": "safe_read",
        "customer_value": (
            "Summarize the current sandbox customer state without production access."
        ),
        "success_signal": (
            "A bounded summary execution completes and produces persisted safe evidence."
        ),
        "sample_input": {
            "customer_id": "sandbox-customer-001",
            "account_status": "active",
        },
    },
    {
        "scenario_id": "CRM-DRAFT-01",
        "title": "Draft Customer Update",
        "task_id": "crm.customer_update_draft",
        "kind": "governed_draft",
        "customer_value": (
            "Prepare a supervisor-reviewable CRM update draft without applying it "
            "to production."
        ),
        "success_signal": (
            "A draft is produced inside the sandbox boundary and recorded as "
            "evaluation evidence."
        ),
        "sample_input": {
            "customer_id": "sandbox-customer-001",
            "proposed_changes": {
                "segment": "evaluation-review",
            },
            "reason": "Synthetic External Evaluation draft only",
        },
    },
    {
        "scenario_id": "INT-BILLING-01",
        "title": "Integration Billing Account Context",
        "task_id": "billing.account_context",
        "kind": "integration_safe_read",
        "customer_value": (
            "Prove a second adapter contract by reading and normalizing a synthetic "
            "billing account through the governed Evaluation runtime."
        ),
        "success_signal": (
            "The billing task is admitted through its prepared binding and safe durable "
            "evidence is persisted without production access."
        ),
        "sample_input": {"account_id": "sandbox-account-001"},
    },
)


def _binding_task_map(raw: dict[str, Any]) -> dict[str, str]:
    values = raw.get(BINDING_STORAGE_KEY, [])
    if not isinstance(values, list):
        return {}
    result: dict[str, str] = {}
    for item in values:
        if not isinstance(item, dict):
            continue
        binding_id = str(item.get("binding_id") or "").strip()
        task_id = str(item.get("task_id") or "").strip().lower()
        if binding_id and task_id:
            result[binding_id] = task_id
    return result


def customer_evaluation_scenarios(
    raw: dict[str, Any],
    grant: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return customer-safe scenario metadata derived only from sealed grant authority."""

    allowed_tasks = {
        str(value).strip().lower()
        for value in grant.get("allowed_task_ids") or []
        if str(value).strip()
    }
    allowed_bindings = {
        str(value).strip()
        for value in grant.get("allowed_binding_ids") or []
        if str(value).strip()
    }
    allowed_endpoints = {
        (
            str(item.get("method") or "").strip().upper(),
            str(item.get("path") or "").strip(),
        )
        for item in grant.get("allowed_endpoints") or []
        if isinstance(item, dict)
    }
    runtime_enabled = EVALUATION_TASK_EXECUTE_ENDPOINT in allowed_endpoints
    binding_tasks = _binding_task_map(raw)

    scenarios: list[dict[str, Any]] = []
    for definition in _SCENARIOS:
        task_id = str(definition["task_id"]).lower()
        if task_id not in allowed_tasks:
            continue
        matching_bindings = sorted(
            binding_id
            for binding_id in allowed_bindings
            if binding_tasks.get(binding_id) == task_id
        )
        if not runtime_enabled:
            readiness = "runtime_endpoint_required"
        elif not matching_bindings:
            readiness = "prepared_binding_required"
        else:
            readiness = "ready"
        scenarios.append(
            {
                **definition,
                "runnable": readiness == "ready",
                "readiness": readiness,
                "binding_ids": matching_bindings,
                "production_allowed": False,
                "quota_cost_new_execution": 1,
                "quota_cost_replay": 0,
                "raw_secret_visible": False,
            }
        )
    return scenarios


__all__ = ["customer_evaluation_scenarios"]
