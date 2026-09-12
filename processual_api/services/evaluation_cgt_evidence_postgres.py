"""Persistence helpers for External Evaluation CGT governance evidence."""

from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy import desc, select

from processual_api.db.session import session_scope
from processual_api.services.evaluation_runtime_delivery import (
    EVALUATION_DELIVERY_STATE_EVIDENCE_PERSISTED,
)
from processual_api.services.evaluation_runtime_delivery_models import EvaluationRuntimeDelivery


def _owner_digest(owner_id: str) -> str:
    return hashlib.sha256(str(owner_id or "").encode("utf-8")).hexdigest()


def _safe_governance(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    allowed = {
        "decision_id",
        "policy_id",
        "policy_version",
        "task_id",
        "binding_id",
        "operation_class",
        "rank",
        "reward",
        "policy",
        "governance_action",
        "disposition",
        "reason_codes",
        "review_required",
        "production_allowed",
        "authority_expansion_allowed",
        "task_input_sha256",
        "trace_sha256",
        "cgt_governance",
        "provider_independent",
        "raw_task_input_included",
        "raw_secret_visible",
    }
    safe = {key: value[key] for key in allowed if key in value}
    safe["production_allowed"] = False
    safe["authority_expansion_allowed"] = False
    safe["raw_task_input_included"] = False
    safe["raw_secret_visible"] = False
    return safe


async def persist_evaluation_cgt_governance(
    *,
    owner_id: str,
    record_id: str,
    governance: dict[str, Any],
    governed_execution_evidence_sha256: str,
) -> None:
    safe = _safe_governance(governance)
    async with session_scope() as session:
        row = (
            await session.execute(
                select(EvaluationRuntimeDelivery)
                .where(EvaluationRuntimeDelivery.record_id == record_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if row is None:
            raise RuntimeError("evaluation_cgt_delivery_record_missing")
        if row.state != EVALUATION_DELIVERY_STATE_EVIDENCE_PERSISTED:
            raise RuntimeError("evaluation_cgt_delivery_record_not_finalized")

        evidence = dict(row.evidence or {})
        evidence["governance"] = safe
        evidence["governance_decision_id"] = safe.get("decision_id")
        evidence["governance_policy_version"] = safe.get("policy_version")
        evidence["governance_disposition"] = safe.get("disposition")
        evidence["governance_trace_sha256"] = safe.get("trace_sha256")
        evidence["governed_execution_evidence_sha256"] = governed_execution_evidence_sha256
        evidence["governance_enforced_before_admission"] = True
        row.evidence = evidence

        replay = dict(row.replay_response or {})
        replay["governance"] = safe
        replay["governance_enforced_before_admission"] = True
        replay["governed_execution_evidence_sha256"] = governed_execution_evidence_sha256
        row.replay_response = replay


async def latest_evaluation_cgt_governance(
    *,
    owner_id: str,
    grant_id: str,
    api_key_id: str,
) -> dict[str, Any] | None:
    async with session_scope() as session:
        row = (
            await session.execute(
                select(EvaluationRuntimeDelivery)
                .where(
                    EvaluationRuntimeDelivery.owner_id_sha256 == _owner_digest(owner_id),
                    EvaluationRuntimeDelivery.grant_id == grant_id,
                    EvaluationRuntimeDelivery.api_key_id == api_key_id,
                    EvaluationRuntimeDelivery.state == EVALUATION_DELIVERY_STATE_EVIDENCE_PERSISTED,
                )
                .order_by(desc(EvaluationRuntimeDelivery.evidence_persisted_at))
                .limit(1)
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        evidence = dict(row.evidence or {})
        governance = _safe_governance(evidence.get("governance"))
        if not governance:
            return None
        return {
            "governance": governance,
            "governance_enforced_before_admission": evidence.get("governance_enforced_before_admission") is True,
            "governed_execution_evidence_sha256": evidence.get("governed_execution_evidence_sha256"),
        }


__all__ = [
    "latest_evaluation_cgt_governance",
    "persist_evaluation_cgt_governance",
]
