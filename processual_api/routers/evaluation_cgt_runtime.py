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
from processual_api.services.evaluation_cgt_denial_postgres import (
    persist_evaluation_cgt_denial,
)
from processual_api.services.evaluation_cgt_evidence_postgres import (
    persist_evaluation_cgt_governance,
)
from processual_api.services.evaluation_cgt_governance import (
    evaluate_evaluation_cgt_governance,
    governed_execution_evidence_sha256,
    maestro_governed_evidence_sha256,
)
from processual_api.services.evaluation_grants import evaluation_binding_allowed
from processual_api.services.evaluation_maestro_consumption import (
    consume_evaluation_task_with_maestro,
)
from processual_api.services.evaluation_runtime_delivery_postgres import (
    evaluation_request_fingerprint,
)

from . import settings_enterprise_endpoint_bindings_runtime as binding_runtime
from .evaluation_runtime import (
    EvaluationRuntimeTaskExecuteRequest,
    _authorize_task,
    _evaluation_owner_id,
    _require_evaluation_credential,
    execute_evaluation_runtime_task,
)


def _governance_proof_summary(governance: dict[str, Any]) -> dict[str, Any]:
    return {
        "layer": "CGT Governance",
        "decision": governance.get("disposition"),
        "decision_id": governance.get("decision_id"),
        "policy_version": governance.get("policy_version"),
        "governance_action": governance.get("governance_action"),
        "reason_codes": list(governance.get("reason_codes") or []),
        "review_required": governance.get("review_required") is True,
        "fate_vector": governance.get("fate_vector"),
        "fate_vector_basis": governance.get("fate_vector_basis"),
        "authority_expansion_allowed": False,
        "production_allowed": False,
        "governance_enforced_before_admission": True,
        "capabilities_proven": [
            "grant_authority_cannot_be_expanded_by_governance",
            "policy_decision_precedes_quota_admission",
            "safe_reads_can_be_allowed",
            "drafts_can_require_supervisor_review",
            "unsupported_or_production_authority_is_denied_fail_closed",
            "governance_trace_is_hash_bound_to_execution_evidence",
            "cgt_fate_vector_is_exposed_in_governance_evidence",
            "governed_task_output_is_consumed_by_processual_maestro_kernel",
        ],
    }


def _project_committed_governance_into_execution_status(
    execution_status: dict[str, Any],
    *,
    governance: dict[str, Any],
    governed_execution_evidence_sha256: str,
    maestro_receipt: dict[str, Any] | None = None,
    maestro_governed_evidence_sha256_value: str | None = None,
) -> dict[str, Any]:
    projected = dict(execution_status or {})
    projected["governance_decision_id"] = governance.get("decision_id")
    projected["governance_policy_version"] = governance.get("policy_version")
    projected["governance_disposition"] = governance.get("disposition")
    projected["governance_trace_sha256"] = governance.get("trace_sha256")
    projected["governed_execution_evidence_sha256"] = governed_execution_evidence_sha256
    projected["governance_enforced_before_admission"] = True
    projected["governance"] = governance
    if maestro_receipt:
        projected["maestro_task_completed"] = maestro_receipt.get("maestro_task_completed") is True
        projected["maestro_consumption"] = maestro_receipt
        projected["maestro_consumption_sha256"] = maestro_receipt.get("consumption_sha256")
        projected["maestro_consumption_receipt_sha256"] = maestro_receipt.get("receipt_sha256")
        projected["maestro_governed_evidence_sha256"] = maestro_governed_evidence_sha256_value
        projected["evaluation_stage"] = "maestro_task_consumed"
    return projected


async def governed_execute_evaluation_runtime_task(
    body: EvaluationRuntimeTaskExecuteRequest,
    current_user: dict = Depends(require_scope("run:evaluation")),
) -> dict[str, Any]:
    """Apply CGT before admission, then complete the safe outcome through Maestro."""

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
        request_fingerprint = evaluation_request_fingerprint(
            grant_id=grant_id,
            api_key_id=api_key_id,
            task_id=task_id,
            binding_id=spec.binding_id,
            task_input=body.task_input,
        )
        try:
            denial = await persist_evaluation_cgt_denial(
                owner_id=owner_id,
                grant_id=grant_id,
                api_key_id=api_key_id,
                idempotency_key=body.idempotency_key,
                request_fingerprint=request_fingerprint,
                task_id=task_id,
                binding_id=spec.binding_id,
                governance=governance,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="CGT denied the request, but durable governance evidence could not be committed.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "evaluation_cgt_governance_denied",
                "decision_id": governance.get("decision_id"),
                "policy_version": governance.get("policy_version"),
                "disposition": governance.get("disposition"),
                "governance_action": governance.get("governance_action"),
                "fate_vector": governance.get("fate_vector"),
                "fate_vector_basis": governance.get("fate_vector_basis"),
                "reason_codes": governance.get("reason_codes"),
                "governance_evidence_persisted": denial["governance_evidence_persisted"],
                "quota_consumed": False,
                "network_request_executed": False,
                "maestro_task_completed": False,
                "production_allowed": False,
                "authority_expansion_allowed": False,
            },
        )

    response = await execute_evaluation_runtime_task(body=body, current_user=current_user)

    execution_status = response.get("execution_status") or {}
    record_id = str(execution_status.get("record_id") or "").strip()
    execution_id = str(response.get("execution_id") or execution_status.get("execution_id") or "").strip()
    execution_evidence_sha256 = str(response.get("evidence_sha256") or "").strip()
    combined_sha256 = governed_execution_evidence_sha256(
        execution_evidence_sha256=execution_evidence_sha256,
        governance_trace_sha256=str(governance.get("trace_sha256") or ""),
    )

    if not record_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Execution completed without a durable record identifier; CGT evidence cannot be finalized.",
        )

    try:
        maestro_receipt = await consume_evaluation_task_with_maestro(
            execution_id=execution_id,
            task_id=task_id,
            binding_id=spec.binding_id,
            output_slot=str(response.get("output_slot") or task.output_slot),
            execution_evidence_sha256=execution_evidence_sha256,
            task_injection_sha256=str(response.get("task_injection_sha256") or ""),
            governance_trace_sha256=str(governance.get("trace_sha256") or ""),
            response_sha256=str(response.get("response_sha256") or ""),
        )
        final_sha256 = maestro_governed_evidence_sha256(
            governed_execution_evidence_sha256=combined_sha256,
            maestro_consumption_sha256=str(maestro_receipt.get("receipt_sha256") or ""),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "External operation succeeded, but Maestro did not complete safe task consumption; "
                "retry the same idempotency key for fail-closed reconciliation."
            ),
        ) from exc

    try:
        await persist_evaluation_cgt_governance(
            owner_id=owner_id,
            record_id=record_id,
            governance=governance,
            governed_execution_evidence_sha256=combined_sha256,
            maestro_receipt=maestro_receipt,
            maestro_governed_evidence_sha256=final_sha256,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Execution and Maestro consumption exist, but governed evidence could not be durably finalized; "
                "retry the same idempotency key for reconciliation."
            ),
        ) from exc

    response["execution_status"] = _project_committed_governance_into_execution_status(
        execution_status,
        governance=governance,
        governed_execution_evidence_sha256=combined_sha256,
        maestro_receipt=maestro_receipt,
        maestro_governed_evidence_sha256_value=final_sha256,
    )
    response["governance"] = governance
    response["governance_proof"] = _governance_proof_summary(governance)
    response["governance_enforced_before_admission"] = True
    response["governed_execution_evidence_sha256"] = combined_sha256
    response["maestro_task_completed"] = True
    response["maestro_consumption"] = maestro_receipt
    response["maestro_consumption_sha256"] = maestro_receipt.get("consumption_sha256")
    response["maestro_consumption_receipt_sha256"] = maestro_receipt.get("receipt_sha256")
    response["maestro_governed_evidence_sha256"] = final_sha256
    response["evaluation_stage"] = "maestro_task_consumed"
    response["next_readiness_stage"] = "qualification_complete"
    response["policy_authority_can_expand_grant"] = False
    return response


__all__ = [
    "_project_committed_governance_into_execution_status",
    "governed_execute_evaluation_runtime_task",
]
