"""CGT-governed wrapper for External Evaluation task execution."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, status

from processual_api.auth.security import require_scope
from processual_api.integrations.integration_task_catalog import get_integration_task
from processual_api.services.evaluation_authority_postgres import (
    EvaluationAuthorityError,
    load_evaluation_authority_state,
)
from processual_api.services.evaluation_cgt_evidence_postgres import (
    persist_evaluation_cgt_governance,
)
from processual_api.services.evaluation_cgt_governance import (
    evaluate_evaluation_cgt_governance,
    governed_execution_evidence_sha256,
)
from processual_api.services.evaluation_grants import evaluation_binding_allowed

from . import settings_enterprise_endpoint_bindings_runtime as binding_runtime
from .evaluation_runtime import (
    EvaluationRuntimeTaskExecuteRequest,
    _authorize_task,
    _evaluation_owner_id,
    _require_evaluation_credential,
    execute_evaluation_runtime_task,
)


async def governed_execute_evaluation_runtime_task(
    body: EvaluationRuntimeTaskExecuteRequest,
    current_user: dict = Depends(require_scope("run:evaluation")),
) -> dict[str, Any]:
    """Apply CGT after grant authority checks and before quota admission/execution."""

    owner_id = _evaluation_owner_id(current_user)
    try:
        raw = await load_evaluation_authority_state(owner_id)
    except EvaluationAuthorityError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Shared Evaluation runtime authority is unavailable.",
        ) from exc

    _require_evaluation_credential(current_user, raw)
    if not evaluation_binding_allowed(current_user, body.binding_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Evaluation grant does not allow this prepared binding.",
        )

    spec = binding_runtime._find_binding(raw, body.binding_id)
    task_id = _authorize_task(
        current_user,
        requested_task_id=body.task_id,
        binding_task_id=spec.task_id,
    )
    task = get_integration_task(task_id)
    grant_id = str(current_user.get("evaluation_grant_id") or "").strip()
    api_key_id = str(current_user.get("api_key_id") or "").strip()

    governance = evaluate_evaluation_cgt_governance(
        grant_id=grant_id,
        api_key_id=api_key_id,
        task_id=task_id,
        binding_id=spec.binding_id,
        operation_class=str(task.operation_class),
        task_input=body.task_input,
        sandbox_allowed=bool(task.sandbox_allowed),
        auto_execute_production=bool(task.auto_execute_production),
        production_allowed=False,
    )
    if governance.get("disposition") == "deny":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "evaluation_cgt_governance_denied",
                "decision_id": governance.get("decision_id"),
                "policy_version": governance.get("policy_version"),
                "reason_codes": governance.get("reason_codes"),
                "production_allowed": False,
            },
        )

    # The existing runtime function performs the authoritative idempotent claim,
    # quota admission, prepared-binding proof validation, network execution, and
    # durable execution evidence commit. CGT has already narrowed the request.
    response = await execute_evaluation_runtime_task(body=body, current_user=current_user)

    execution_status = response.get("execution_status") or {}
    record_id = str(execution_status.get("record_id") or "").strip()
    execution_evidence_sha256 = str(response.get("evidence_sha256") or "").strip()
    combined_sha256 = governed_execution_evidence_sha256(
        execution_evidence_sha256=execution_evidence_sha256,
        governance_trace_sha256=str(governance.get("trace_sha256") or ""),
    )

    if record_id:
        await persist_evaluation_cgt_governance(
            owner_id=owner_id,
            record_id=record_id,
            governance=governance,
            governed_execution_evidence_sha256=combined_sha256,
        )

    response["governance"] = governance
    response["governance_enforced_before_admission"] = True
    response["governed_execution_evidence_sha256"] = combined_sha256
    response["policy_authority_can_expand_grant"] = False
    return response


__all__ = ["governed_execute_evaluation_runtime_task"]
