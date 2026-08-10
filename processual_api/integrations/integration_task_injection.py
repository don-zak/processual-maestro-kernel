"""Validated handoff envelope from endpoint mapping into a Maestro task slot."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from processual_api.integrations.integration_task_catalog import get_integration_task

TASK_INJECTION_SCHEMA_VERSION = "2026-08-enterprise-task-injection-v1"


class TaskInjectionError(ValueError):
    """Canonical mapped data cannot be handed to the declared task."""


def _digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_task_injection_envelope(
    *,
    task_id: str,
    binding_id: str,
    canonical_input: dict[str, Any],
) -> dict[str, Any]:
    task = get_integration_task(task_id)
    binding = str(binding_id or "").strip()
    if not binding:
        raise TaskInjectionError("binding_id is required")
    if not isinstance(canonical_input, dict):
        raise TaskInjectionError("canonical task input must be an object")

    required = set(task.required_input_fields)
    allowed = required | set(task.optional_input_fields)
    missing = sorted(
        field
        for field in required
        if field not in canonical_input or canonical_input[field] is None
    )
    if missing:
        raise TaskInjectionError(
            "canonical task input is missing required fields: "
            + ", ".join(missing)
        )
    unknown = sorted(set(canonical_input) - allowed)
    if unknown:
        raise TaskInjectionError(
            "canonical task input contains fields outside task schema: "
            + ", ".join(unknown)
        )

    payload_sha256 = _digest(canonical_input)
    authority = {
        "schema_version": TASK_INJECTION_SCHEMA_VERSION,
        "binding_id": binding,
        "task_id": task.task_id,
        "adapter_contract_id": task.adapter_contract_id,
        "operation_class": task.operation_class,
        "output_slot": task.output_slot,
        "required_scope_ids": list(task.required_scope_ids),
        "payload_sha256": payload_sha256,
        "environment": "sandbox",
    }
    return {
        **authority,
        "canonical_input": canonical_input,
        "injection_sha256": _digest(authority),
        "schema_valid": True,
        "ready_for_task_consumption": True,
        "production_allowed": False,
        "runtime_connector_approved": False,
    }


__all__ = [
    "TASK_INJECTION_SCHEMA_VERSION",
    "TaskInjectionError",
    "build_task_injection_envelope",
]
