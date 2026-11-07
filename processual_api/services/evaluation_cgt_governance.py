"""Deterministic CGT governance for External Evaluation runtime execution.

This layer can only narrow authority already granted by the PostgreSQL-backed
Evaluation Grant. It never adds tasks, bindings, scopes, endpoints, quota, or
production authority. Decisions are intentionally deterministic and provider-
independent so External Evaluation can prove governance without depending on an
external LLM.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import Any

from processual_api.cgt_governor.evaluator import compute_fate_vector
from processual_api.cgt_governor.policy import policy_engine as runtime_policy_engine

EVALUATION_CGT_POLICY_ID = "external-evaluation-cgt"
EVALUATION_CGT_POLICY_VERSION = "external-evaluation-cgt-v1"
EVALUATION_CGT_FATE_VECTOR_BASIS = "external-evaluation-policy-signal-profile-v1"


def _digest(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _evaluation_fate_vector(*, rank: str, operation_class: str) -> dict[str, float]:
    """Compute a deterministic CGT fate vector from sealed governance signals.

    These are policy-signal profiles, not model-quality guesses. They encode the
    already-determined External Evaluation governance state into the existing CGT
    fate-vector mathematics so reports expose the same seven-dimensional CGT
    surface used elsewhere in Maestro.
    """

    if rank == "stable":
        profile = dict(
            compatibility=1.0,
            coherence=1.0,
            structural_support=1.0,
            usefulness=1.0,
            complexity=0.05,
            fatigue=0.0,
            shock=0.0,
            lift=0.15,
            novelty=0.25,
            no_answer=0.0,
            hallucination=0.0,
            constraint_failure=0.0,
        )
    elif rank == "hybrid" and operation_class == "draft":
        profile = dict(
            compatibility=0.85,
            coherence=0.9,
            structural_support=0.9,
            usefulness=0.9,
            complexity=0.35,
            fatigue=0.0,
            shock=0.05,
            lift=1.0,
            novelty=0.25,
            no_answer=0.0,
            hallucination=0.0,
            constraint_failure=0.05,
        )
    else:
        profile = dict(
            compatibility=0.0,
            coherence=1.0,
            structural_support=1.0,
            usefulness=0.0,
            complexity=0.2,
            fatigue=0.0,
            shock=0.8,
            lift=0.0,
            novelty=0.0,
            no_answer=0.0,
            hallucination=0.0,
            constraint_failure=1.0,
        )
    return asdict(compute_fate_vector(**profile))


def evaluate_evaluation_cgt_governance(
    *,
    grant_id: str,
    api_key_id: str,
    task_id: str,
    binding_id: str,
    operation_class: str,
    task_input: dict[str, Any],
    sandbox_allowed: bool,
    auto_execute_production: bool,
    production_allowed: bool = False,
) -> dict[str, Any]:
    """Return a safe CGT decision that can only narrow Evaluation authority."""

    normalized_operation = str(operation_class or "").strip().lower()
    reasons: list[str] = []

    if production_allowed or auto_execute_production or not sandbox_allowed:
        rank = "extinct"
        reward = 0.0
        policy = "reject_regenerate"
        policy_label = "Reject production or non-sandbox authority"
        reasons.extend(
            [
                "external_evaluation_sandbox_only",
                "production_authority_forbidden",
            ]
        )
    elif normalized_operation == "read":
        rank = "stable"
        reward = 1.0
        policy = "accept"
        policy_label = "Allow bounded sandbox read"
        reasons.extend(
            [
                "grant_authority_prevalidated",
                "sandbox_read_operation",
                "prepared_binding_required",
            ]
        )
    elif normalized_operation == "draft":
        rank = "hybrid"
        reward = 0.85
        policy = "repair_scaffold"
        policy_label = "Allow draft with mandatory supervisor review"
        reasons.extend(
            [
                "grant_authority_prevalidated",
                "draft_only_operation",
                "supervisor_review_required",
                "production_mutation_forbidden",
            ]
        )
    else:
        rank = "extinct"
        reward = 0.0
        policy = "reject_regenerate"
        policy_label = "Reject unsupported Evaluation operation class"
        reasons.extend(
            [
                "unsupported_operation_class",
                "authority_not_expanded",
            ]
        )

    decision = runtime_policy_engine.decide(
        rank=rank,
        reward=reward,
        policy=policy,
        policy_label=policy_label,
    )

    if decision.action.value == "keep":
        disposition = "allow"
        review_required = False
    elif decision.action.value == "repair" and normalized_operation == "draft":
        disposition = "allow_with_review"
        review_required = True
    else:
        disposition = "deny"
        review_required = True

    fate_vector = _evaluation_fate_vector(
        rank=decision.rank,
        operation_class=normalized_operation,
    )
    safe_material = {
        "policy_id": EVALUATION_CGT_POLICY_ID,
        "policy_version": EVALUATION_CGT_POLICY_VERSION,
        "grant_id": str(grant_id or ""),
        "api_key_id": str(api_key_id or ""),
        "task_id": str(task_id or "").strip().lower(),
        "binding_id": str(binding_id or "").strip(),
        "operation_class": normalized_operation,
        "rank": decision.rank,
        "reward": decision.reward,
        "policy": decision.policy,
        "governance_action": decision.action.value,
        "disposition": disposition,
        "reason_codes": reasons,
        "review_required": review_required,
        "production_allowed": False,
        "authority_expansion_allowed": False,
        "fate_vector": fate_vector,
        "fate_vector_basis": EVALUATION_CGT_FATE_VECTOR_BASIS,
        "task_input_sha256": _digest(task_input),
    }
    trace_sha256 = _digest(safe_material)
    decision_id = f"cgt_eval_{trace_sha256[:20]}"

    return {
        "decision_id": decision_id,
        **safe_material,
        "trace_sha256": trace_sha256,
        "cgt_governance": True,
        "provider_independent": True,
        "raw_task_input_included": False,
        "raw_secret_visible": False,
    }


def governed_execution_evidence_sha256(
    *,
    execution_evidence_sha256: str,
    governance_trace_sha256: str,
) -> str:
    return _digest(
        {
            "execution_evidence_sha256": str(execution_evidence_sha256 or ""),
            "governance_trace_sha256": str(governance_trace_sha256 or ""),
            "policy_version": EVALUATION_CGT_POLICY_VERSION,
        }
    )


def maestro_governed_evidence_sha256(
    *,
    governed_execution_evidence_sha256: str,
    maestro_consumption_sha256: str,
) -> str:
    """Bind the governed execution proof to Maestro's task-consumption receipt."""
    return _digest(
        {
            "governed_execution_evidence_sha256": str(governed_execution_evidence_sha256 or ""),
            "maestro_consumption_sha256": str(maestro_consumption_sha256 or ""),
            "policy_version": EVALUATION_CGT_POLICY_VERSION,
        }
    )


__all__ = [
    "EVALUATION_CGT_FATE_VECTOR_BASIS",
    "EVALUATION_CGT_POLICY_ID",
    "EVALUATION_CGT_POLICY_VERSION",
    "evaluate_evaluation_cgt_governance",
    "governed_execution_evidence_sha256",
    "maestro_governed_evidence_sha256",
]
