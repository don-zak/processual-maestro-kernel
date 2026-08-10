from __future__ import annotations

import pytest

from processual_api.integrations.integration_task_catalog import list_integration_tasks
from processual_api.integrations.integration_task_injection import (
    TASK_INJECTION_SCHEMA_VERSION,
    TaskInjectionError,
    build_task_injection_envelope,
)


def _sample(task) -> dict:
    return {field: f"sample-{field}" for field in task.required_input_fields}


def test_every_declared_task_accepts_its_required_canonical_schema() -> None:
    for task in list_integration_tasks():
        envelope = build_task_injection_envelope(
            task_id=task.task_id,
            binding_id=f"test.{task.task_id}",
            canonical_input=_sample(task),
        )
        assert envelope["schema_version"] == TASK_INJECTION_SCHEMA_VERSION
        assert envelope["task_id"] == task.task_id
        assert envelope["output_slot"] == task.output_slot
        assert envelope["ready_for_task_consumption"] is True
        assert envelope["schema_valid"] is True
        assert len(envelope["payload_sha256"]) == 64
        assert len(envelope["injection_sha256"]) == 64
        assert envelope["production_allowed"] is False
        assert envelope["runtime_connector_approved"] is False


def test_injection_rejects_missing_required_fields() -> None:
    with pytest.raises(TaskInjectionError, match="missing required"):
        build_task_injection_envelope(
            task_id="billing.account_context",
            binding_id="billing.account",
            canonical_input={},
        )


def test_injection_rejects_fields_outside_task_schema() -> None:
    with pytest.raises(TaskInjectionError, match="outside task schema"):
        build_task_injection_envelope(
            task_id="billing.account_context",
            binding_id="billing.account",
            canonical_input={"account_id": "A-1", "unexpected": "no"},
        )
