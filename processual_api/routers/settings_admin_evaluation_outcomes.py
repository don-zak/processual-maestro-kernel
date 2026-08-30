"""Super-Administrator provisioning of hashed Evaluation outcome expectations."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, status
from pydantic import BaseModel, Field

from processual_api.auth.platform_admin_authority import require_active_platform_admin
from processual_api.auth.security import get_current_user
from processual_api.services.evaluation_outcome_expectations import (
    build_outcome_expectation,
    upsert_outcome_expectation,
)

from . import settings as settings_module
from . import settings_enterprise_endpoint_bindings_runtime as binding_runtime
from . import settings_enterprise_sandbox_operational_runtime as sandbox_runtime


class EvaluationOutcomeExpectationCreate(BaseModel):
    task_id: str = Field(min_length=1, max_length=160)
    expected_fields: dict[str, Any] = Field(min_length=1, max_length=32)


def _owner_user_id(current_user: dict[str, Any]) -> str:
    return str(current_user.get("sub") or current_user.get("user_id") or "default")


@settings_module.router.put(
    "/admin/evaluation-grants/bindings/{binding_id}/outcome-expectation",
    response_model=dict,
)
async def save_evaluation_outcome_expectation(
    binding_id: str,
    body: EvaluationOutcomeExpectationCreate,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    await require_active_platform_admin(current_user)
    owner_id = _owner_user_id(current_user)
    raw = settings_module._load_raw(owner_id)
    spec = binding_runtime._find_binding(raw, binding_id)
    task_id = str(body.task_id or "").strip().lower()
    if task_id != str(spec.task_id or "").strip().lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Outcome expectation task must match the prepared endpoint binding.",
        )
    content = sandbox_runtime._content_contract(raw, binding_id)
    if content is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Prepared sandbox content contract is required before outcome expectation provisioning.",
        )

    actor = str(
        current_user.get("email")
        or current_user.get("sub")
        or current_user.get("user_id")
        or "platform_admin"
    )
    try:
        expectation = build_outcome_expectation(
            binding_id=binding_id,
            task_id=task_id,
            expected_fields=body.expected_fields,
            acceptance_criteria_references=content.acceptance_criteria_references,
            dataset_reference=content.dataset_reference,
            fixture_profile_reference=content.fixture_profile_reference,
            created_by=actor,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    upsert_outcome_expectation(raw, expectation)
    settings_module._save_raw(owner_id, raw)
    return {
        "status": "saved",
        "binding_id": binding_id,
        "task_id": task_id,
        "expectation_sha256": expectation["expectation_sha256"],
        "required_fields": expectation["required_fields"],
        "acceptance_criteria_references": expectation["acceptance_criteria_references"],
        "raw_expected_values_persisted": False,
        "provisioned_by_authority": "platform_admin",
        "production_allowed": False,
    }


__all__ = [
    "EvaluationOutcomeExpectationCreate",
    "save_evaluation_outcome_expectation",
]
