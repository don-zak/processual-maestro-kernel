"""Runtime outcome validation for completed governed Evaluation tasks."""

from __future__ import annotations

from typing import Any, Mapping

from processual_api.integrations.integration_task_catalog import READ, get_integration_task
from processual_api.integrations.sandbox_operational_readiness import SandboxContentContract
from processual_api.services.evaluation_outcome_expectations import (
    find_outcome_expectation,
    validate_read_outcome,
)


def evaluate_completed_task_outcome(
    *,
    raw: Mapping[str, Any],
    binding_id: str,
    task_id: str,
    canonical_result: Mapping[str, Any],
    content_contract: SandboxContentContract,
    maestro_task_completed: bool,
) -> dict[str, Any]:
    task = get_integration_task(task_id)
    if not maestro_task_completed:
        return {
            "outcome_validation_status": "task_incomplete",
            "outcome_validated": False,
            "outcome_validation_passed": False,
            "outcome_validation_sha256": None,
            "production_allowed": False,
        }
    if task.operation_class != READ:
        return {
            "outcome_validation_status": "unsupported_without_downstream_consumer",
            "outcome_validated": False,
            "outcome_validation_passed": False,
            "outcome_validation_sha256": None,
            "production_allowed": False,
        }

    expectation = find_outcome_expectation(
        raw,
        binding_id=binding_id,
        task_id=task_id,
    )
    return validate_read_outcome(
        expectation=expectation,
        canonical_result=canonical_result,
        acceptance_criteria_references=content_contract.acceptance_criteria_references,
        dataset_reference=content_contract.dataset_reference,
        fixture_profile_reference=content_contract.fixture_profile_reference,
    )


__all__ = ["evaluate_completed_task_outcome"]
