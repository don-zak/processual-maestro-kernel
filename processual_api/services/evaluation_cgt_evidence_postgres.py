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
        "fate_vector",
        "fate_vector_basis",
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


def _safe_maestro_receipt(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    allowed = {
        "schema_version",
        "workflow_id",
        "workflow_state",
        "step_state",
        "agent_id",
        "task_id",
        "binding_id",
        "output_slot",
        "consumption_sha256",
        "execution_evidence_sha256",
        "task_injection_sha256",
        "governance_trace_sha256",
        "receipt_sha256",
        "maestro_task_completed",
        "maestro_kernel",
        "raw_task_input_included",
        "raw_provider_response_included",
        "raw_secret_visible",
        "production_allowed",
    }
    safe = {key: value[key] for key in allowed if key in value}
    safe["maestro_task_completed"] = safe.get("maestro_task_completed") is True
    safe["raw_task_input_included"] = False
    safe["raw_provider_response_included"] = False
    safe["raw_secret_visible"] = False
    safe["production_allowed"] = False
    return safe


async def persist_evaluation_cgt_governance(
    *,
    owner_id: str,
    record_id: str,
    governance: dict[str, Any],
    governed_execution_evidence_sha256: str,
    maestro_receipt: dict[str, Any] | None = None,
    maestro_governed_evidence_sha256: str | None = None,
) -> None:
    safe = _safe_governance(governance)
    maestro_safe = _safe_maestro_receipt(maestro_receipt)
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
        if maestro_safe:
            evidence["maestro_consumption"] = maestro_safe
            evidence["maestro_task_completed"] = maestro_safe.get("maestro_task_completed") is True
            evidence["maestro_consumption_sha256"] = maestro_safe.get("consumption_sha256")
            evidence["maestro_consumption_receipt_sha256"] = maestro_safe.get("receipt_sha256")
            evidence["maestro_governed_evidence_sha256"] = maestro_governed_evidence_sha256
            evidence["evaluation_stage"] = "maestro_task_consumed"
        row.evidence = evidence

        replay = dict(row.replay_response or {})
        replay["governance"] = safe
        replay["governance_enforced_before_admission"] = True
        replay["governed_execution_evidence_sha256"] = governed_execution_evidence_sha256
        if maestro_safe:
            replay["maestro_consumption"] = maestro_safe
            replay["maestro_task_completed"] = maestro_safe.get("maestro_task_completed") is True
            replay["maestro_consumption_sha256"] = maestro_safe.get("consumption_sha256")
            replay["maestro_consumption_receipt_sha256"] = maestro_safe.get("receipt_sha256")
            replay["maestro_governed_evidence_sha256"] = maestro_governed_evidence_sha256
            replay["evaluation_stage"] = "maestro_task_consumed"
            replay["next_readiness_stage"] = "qualification_complete"
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
            "maestro_task_completed": evidence.get("maestro_task_completed") is True,
            "maestro_consumption": _safe_maestro_receipt(evidence.get("maestro_consumption")),
            "maestro_governed_evidence_sha256": evidence.get("maestro_governed_evidence_sha256"),
        }


__all__ = [
    "latest_evaluation_cgt_governance",
    "persist_evaluation_cgt_governance",
]
