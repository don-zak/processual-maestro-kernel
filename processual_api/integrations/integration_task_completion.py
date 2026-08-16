"""Truthful completion semantics for canonical integration tasks.

A mapped external response is not automatically a completed Maestro task.
For canonical READ tasks, however, the governed external read plus schema-valid
mapping is the task's declared safe operation, so the mapped canonical result
can be marked complete without inventing a downstream workflow. Draft and
approval-gated write tasks remain incomplete until a dedicated consumer performs
their declared operation.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from processual_api.integrations.integration_task_catalog import READ, get_integration_task
from processual_api.integrations.integration_task_injection import (
    build_task_injection_envelope,
)


class IntegrationTaskCompletionError(ValueError):
    """A canonical task cannot truthfully be marked completed at this stage."""


def _digest(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def complete_mapped_read_task(
    *,
    task_id: str,
    binding_id: str,
    canonical_input: dict[str, Any],
    expected_output_slot: str,
) -> dict[str, Any]:
    """Mark a canonical READ task complete after governed external execution.

    This function deliberately refuses draft and write operation classes. It
    re-validates the canonical payload using the task-injection contract so a
    caller cannot turn an arbitrary mapped object into completion evidence.
    """

    task = get_integration_task(task_id)
    if task.operation_class != READ:
        raise IntegrationTaskCompletionError(
            "canonical task requires a dedicated downstream consumer before completion"
        )

    output_slot = str(expected_output_slot or "").strip()
    if output_slot != task.output_slot:
        raise IntegrationTaskCompletionError(
            "canonical task output slot does not match the task contract"
        )

    injection = build_task_injection_envelope(
        task_id=task.task_id,
        binding_id=binding_id,
        canonical_input=canonical_input,
    )
    if injection.get("ready_for_task_consumption") is not True:
        raise IntegrationTaskCompletionError(
            "canonical task payload is not ready for task consumption"
        )

    completion_material = {
        "task_id": task.task_id,
        "binding_id": str(binding_id),
        "operation_class": task.operation_class,
        "safe_operation": task.safe_operation,
        "output_slot": task.output_slot,
        "canonical_result_sha256": injection["payload_sha256"],
        "task_injection_sha256": injection["injection_sha256"],
        "completion_semantics": "governed_external_read_mapped_to_canonical_result",
    }
    return {
        **completion_material,
        "completion_sha256": _digest(completion_material),
        "maestro_task_completed": True,
        "completion_stage": "canonical_read_task_completed",
        "dedicated_downstream_consumer_required": False,
        "production_allowed": False,
        "raw_secret_visible": False,
    }


__all__ = [
    "IntegrationTaskCompletionError",
    "complete_mapped_read_task",
]
