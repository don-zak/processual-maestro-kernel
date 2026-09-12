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
from typing import Any

from processual_api.cgt_governor.policy import policy_engine as runtime_policy_engine

EVALUATION_CGT_POLICY_ID = "external-evaluation-cgt"
EVALUATION_CGT_POLICY_VERSION = "external-evaluation-cgt-v1"


def _digest(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


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
        # The draft itself may be produced, but never applied. CGT requires a
        # human-review boundary before any later mutation could be considered.
        disposition = "allow_with_review"
        review_required = True
    else:
        disposition = "deny"
        review_required = True

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
    """Bind execution evidence and governance trace into one customer-safe digest."""

    return _digest(
        {
            "execution_evidence_sha256": str(execution_evidence_sha256 or ""),
            "governance_trace_sha256": str(governance_trace_sha256 or ""),
            "policy_version": EVALUATION_CGT_POLICY_VERSION,
        }
    )


__all__ = [
    "EVALUATION_CGT_POLICY_ID",
    "EVALUATION_CGT_POLICY_VERSION",
    "evaluate_evaluation_cgt_governance",
    "governed_execution_evidence_sha256",
]
