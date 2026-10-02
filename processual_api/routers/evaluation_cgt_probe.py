"""Safe governance-only qualification probe for External Evaluation.

The probe exists to prove a real CGT deny path without asking an evaluator to
possess or attempt production authority. It never calls an external provider,
never enters admitted-execution accounting, and can only return a deterministic
CGT denial with durable safe evidence.
"""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, status
from pydantic import BaseModel, Field

from processual_api.auth.security import require_scope
from processual_api.services.evaluation_authority_postgres import (
    EvaluationAuthorityError,
    load_evaluation_authority_state,
)
from processual_api.services.evaluation_cgt_denial_postgres import (
    persist_evaluation_cgt_denial,
)
from processual_api.services.evaluation_cgt_governance import (
    evaluate_evaluation_cgt_governance,
)
from processual_api.services.evaluation_runtime_delivery_postgres import (
    evaluation_request_fingerprint,
)

from .evaluation_runtime import _evaluation_owner_id, _require_evaluation_credential

CGT_DENY_PROBE_ID = "CGT-DENY-01"
CGT_DENY_PROBE_TASK_ID = "qualification.cgt.production_mutation_probe"
CGT_DENY_PROBE_BINDING_ID = "evaluation.governance.deny_probe"


class EvaluationCGTDenyProbeRequest(BaseModel):
    probe_id: str = Field(default=CGT_DENY_PROBE_ID, pattern="^CGT-DENY-01$")
    idempotency_key: str = Field(min_length=8, max_length=160)


def _safe_probe_material() -> dict[str, Any]:
    return {
        "probe_id": CGT_DENY_PROBE_ID,
        "simulated_policy_signal": "production_mutation_requested",
        "executable": False,
    }


async def run_evaluation_cgt_deny_probe(
    body: EvaluationCGTDenyProbeRequest,
    current_user: dict = Depends(require_scope("run:evaluation")),
) -> dict[str, Any]:
    """Prove deterministic CGT deny before admission with +0 quota and no network."""

    owner_id = _evaluation_owner_id(current_user)
    try:
        raw = await load_evaluation_authority_state(owner_id)
    except EvaluationAuthorityError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Shared Evaluation runtime authority is unavailable.",
        ) from exc

    _require_evaluation_credential(current_user, raw)
    grant_id = str(current_user.get("evaluation_grant_id") or "").strip()
    api_key_id = str(current_user.get("api_key_id") or "").strip()
    probe_material = _safe_probe_material()

    governance = evaluate_evaluation_cgt_governance(
        grant_id=grant_id,
        api_key_id=api_key_id,
        task_id=CGT_DENY_PROBE_TASK_ID,
        binding_id=CGT_DENY_PROBE_BINDING_ID,
        operation_class="mutation",
        task_input=probe_material,
        sandbox_allowed=False,
        auto_execute_production=True,
        production_allowed=True,
    )
    if governance.get("disposition") != "deny":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="CGT deny qualification probe did not fail closed.",
        )

    request_fingerprint = evaluation_request_fingerprint(
        grant_id=grant_id,
        api_key_id=api_key_id,
        task_id=CGT_DENY_PROBE_TASK_ID,
        binding_id=CGT_DENY_PROBE_BINDING_ID,
        task_input=probe_material,
    )
    try:
        denial = await persist_evaluation_cgt_denial(
            owner_id=owner_id,
            grant_id=grant_id,
            api_key_id=api_key_id,
            idempotency_key=body.idempotency_key,
            request_fingerprint=request_fingerprint,
            task_id=CGT_DENY_PROBE_TASK_ID,
            binding_id=CGT_DENY_PROBE_BINDING_ID,
            governance=governance,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="CGT denied the qualification probe, but durable governance evidence could not be committed.",
        ) from exc

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": "evaluation_cgt_governance_denied",
            "probe_id": CGT_DENY_PROBE_ID,
            "probe_kind": "governance_only_non_executable",
            "decision_id": governance.get("decision_id"),
            "policy_version": governance.get("policy_version"),
            "governance_action": governance.get("governance_action"),
            "disposition": governance.get("disposition"),
            "rank": governance.get("rank"),
            "fate_vector": governance.get("fate_vector"),
            "fate_vector_basis": governance.get("fate_vector_basis"),
            "reason_codes": governance.get("reason_codes"),
            "governance_trace_sha256": governance.get("trace_sha256"),
            "governance_evidence_persisted": denial["governance_evidence_persisted"],
            "quota_consumed": False,
            "network_request_executed": False,
            "maestro_task_completed": False,
            "production_allowed": False,
            "authority_expansion_allowed": False,
            "raw_task_input_persisted": False,
            "raw_secret_visible": False,
        },
    )


__all__ = [
    "CGT_DENY_PROBE_ID",
    "EvaluationCGTDenyProbeRequest",
    "run_evaluation_cgt_deny_probe",
]
