"""Durable zero-quota evidence for CGT-denied External Evaluation requests."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert

from processual_api.db.session import session_scope
from processual_api.services.evaluation_runtime_delivery_models import EvaluationRuntimeDelivery


def _digest(value: str) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def _record_id(*, owner_id: str, grant_id: str, api_key_id: str, idempotency_key: str) -> str:
    material = "\0".join((owner_id, grant_id, api_key_id, idempotency_key))
    return _digest(material)


def _safe_governance(governance: dict[str, Any]) -> dict[str, Any]:
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
    safe = {key: governance[key] for key in allowed if key in governance}
    safe["production_allowed"] = False
    safe["authority_expansion_allowed"] = False
    safe["raw_task_input_included"] = False
    safe["raw_secret_visible"] = False
    return safe


async def persist_evaluation_cgt_denial(
    *,
    owner_id: str,
    grant_id: str,
    api_key_id: str,
    idempotency_key: str,
    request_fingerprint: str,
    task_id: str,
    binding_id: str,
    governance: dict[str, Any],
) -> dict[str, Any]:
    """Persist a governance denial without consuming an admitted-execution unit."""

    now = datetime.now(UTC)
    record_id = _record_id(
        owner_id=owner_id,
        grant_id=grant_id,
        api_key_id=api_key_id,
        idempotency_key=idempotency_key,
    )
    safe_governance = _safe_governance(governance)
    evidence = {
        "evaluation_grant_id": grant_id,
        "api_key_id": api_key_id,
        "task_id": task_id,
        "binding_id": binding_id,
        "evaluation_stage": "cgt_governance_denied_before_admission",
        "governance": safe_governance,
        "governance_decision_id": safe_governance.get("decision_id"),
        "governance_policy_version": safe_governance.get("policy_version"),
        "governance_disposition": "deny",
        "governance_trace_sha256": safe_governance.get("trace_sha256"),
        "governance_enforced_before_admission": True,
        "quota_consumed": False,
        "network_request_executed": False,
        "maestro_task_completed": False,
        "production_allowed": False,
        "raw_task_input_persisted": False,
        "raw_secret_visible": False,
    }
    history = [
        {"state": "governance_evaluated", "at": now.isoformat()},
        {"state": "failed", "at": now.isoformat(), "reason": "cgt_governance_denied"},
    ]
    statement = (
        pg_insert(EvaluationRuntimeDelivery)
        .values(
            record_id=record_id,
            owner_id_sha256=_digest(owner_id),
            grant_id=grant_id,
            api_key_id=api_key_id,
            idempotency_key_sha256=_digest(idempotency_key),
            request_fingerprint=request_fingerprint,
            task_id=task_id,
            binding_id=binding_id,
            state="failed",
            state_history=history,
            evidence=evidence,
            replay_response=None,
            accepted_at=now,
            execution_started_at=now,
            failed_at=now,
            failure_code="CGTGovernanceDenied",
            network_outcome="not_executed",
            raw_task_input_persisted=False,
            raw_secret_visible=False,
        )
        .on_conflict_do_nothing()
    )
    async with session_scope() as session:
        await session.execute(statement)
    return {
        "record_id": record_id,
        "governance_evidence_persisted": True,
        "quota_consumed": False,
        "network_request_executed": False,
        "maestro_task_completed": False,
        "production_allowed": False,
        "raw_task_input_persisted": False,
        "raw_secret_visible": False,
    }


__all__ = ["persist_evaluation_cgt_denial"]
