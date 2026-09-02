"""Shared transactional idempotency authority for External Evaluation runtime.

This store is the production/multi-instance delivery authority. It persists the
claim before external network execution and never persists raw task input or
credential material. PostgreSQL uniqueness serializes competing replicas for
the same evaluation idempotency authority.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from processual_api.db.session import session_scope
from processual_api.services.evaluation_runtime_delivery import (
    EVALUATION_DELIVERY_STATE_EVIDENCE_PERSISTED,
    EVALUATION_DELIVERY_STATE_EXECUTING,
    EvaluationDeliveryError,
    EvaluationIdempotencyConflictError,
    EvaluationReplayBlockedError,
    _validate_safe_replay_response,
    evaluation_request_fingerprint,
)
from processual_api.services.evaluation_runtime_delivery_models import (
    EvaluationRuntimeDelivery,
)


def _now() -> datetime:
    return datetime.now(UTC)


def _owner_digest(owner_id: str) -> str:
    return hashlib.sha256(str(owner_id or "").encode("utf-8")).hexdigest()


def _idempotency_digest(idempotency_key: str) -> str:
    return hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()


def _record_id(
    *, owner_id: str, grant_id: str, api_key_id: str, idempotency_key: str
) -> str:
    material = "\0".join(
        (str(owner_id or ""), str(grant_id or ""), str(api_key_id or ""), idempotency_key)
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


async def claim_evaluation_execution(
    *,
    owner_id: str,
    grant_id: str,
    api_key_id: str,
    idempotency_key: str,
    request_fingerprint: str,
    task_id: str,
    binding_id: str,
) -> dict[str, Any]:
    """Claim one shared execution or return the durable replay receipt."""

    normalized_key = str(idempotency_key or "").strip()
    if not normalized_key:
        raise EvaluationDeliveryError("evaluation_idempotency_key_required")

    record_id = _record_id(
        owner_id=owner_id,
        grant_id=grant_id,
        api_key_id=api_key_id,
        idempotency_key=normalized_key,
    )
    now = _now()
    history = [
        {"state": "accepted", "at": now.isoformat()},
        {"state": EVALUATION_DELIVERY_STATE_EXECUTING, "at": now.isoformat()},
    ]

    try:
        async with session_scope() as session:
            insert_statement = (
                pg_insert(EvaluationRuntimeDelivery)
                .values(
                    record_id=record_id,
                    owner_id_sha256=_owner_digest(owner_id),
                    grant_id=str(grant_id or ""),
                    api_key_id=str(api_key_id or ""),
                    idempotency_key_sha256=_idempotency_digest(normalized_key),
                    request_fingerprint=request_fingerprint,
                    task_id=str(task_id or "").strip().lower(),
                    binding_id=str(binding_id or "").strip(),
                    state=EVALUATION_DELIVERY_STATE_EXECUTING,
                    state_history=history,
                    accepted_at=now,
                    execution_started_at=now,
                    raw_task_input_persisted=False,
                    raw_secret_visible=False,
                )
                .on_conflict_do_nothing()
                .returning(EvaluationRuntimeDelivery.record_id)
            )
            inserted = await session.execute(insert_statement)
            if inserted.scalar_one_or_none() is not None:
                return {
                    "status": "claimed",
                    "record": {
                        "record_id": record_id,
                        "request_fingerprint": request_fingerprint,
                        "state": EVALUATION_DELIVERY_STATE_EXECUTING,
                        "raw_task_input_persisted": False,
                        "raw_secret_visible": False,
                    },
                }

            existing_result = await session.execute(
                select(EvaluationRuntimeDelivery).where(
                    EvaluationRuntimeDelivery.record_id == record_id
                )
            )
            existing = existing_result.scalar_one_or_none()
            if existing is None:
                raise EvaluationDeliveryError("evaluation_delivery_claim_conflict_unresolved")
            if existing.request_fingerprint != request_fingerprint:
                raise EvaluationIdempotencyConflictError(
                    "evaluation_idempotency_key_payload_mismatch"
                )
            state = str(existing.state or "")
            if state != EVALUATION_DELIVERY_STATE_EVIDENCE_PERSISTED:
                raise EvaluationReplayBlockedError(
                    f"evaluation_replay_blocked_{state or 'unknown'}"
                )
            replay = existing.replay_response
            if not isinstance(replay, dict):
                raise EvaluationReplayBlockedError("evaluation_replay_evidence_unavailable")
            return {
                "status": "replay",
                "record": {
                    "record_id": existing.record_id,
                    "request_fingerprint": existing.request_fingerprint,
                    "state": existing.state,
                    "raw_task_input_persisted": existing.raw_task_input_persisted,
                    "raw_secret_visible": existing.raw_secret_visible,
                },
                "response": dict(replay),
            }
    except EvaluationDeliveryError:
        raise
    except Exception as exc:
        raise EvaluationDeliveryError("evaluation_delivery_database_unavailable") from exc


async def complete_evaluation_execution(
    *,
    owner_id: str,
    record_id: str,
    evidence: dict[str, Any],
    replay_response: dict[str, Any],
) -> dict[str, Any]:
    """Finalize the claimed execution and durable safe replay receipt atomically."""

    del owner_id  # record_id already binds the owner authority digest.
    _validate_safe_replay_response(replay_response)
    try:
        async with session_scope() as session:
            selected = await session.execute(
                select(EvaluationRuntimeDelivery)
                .where(EvaluationRuntimeDelivery.record_id == record_id)
                .with_for_update()
            )
            row = selected.scalar_one_or_none()
            if row is None:
                raise EvaluationDeliveryError("evaluation_delivery_claim_missing")
            if row.state != EVALUATION_DELIVERY_STATE_EXECUTING:
                raise EvaluationDeliveryError("evaluation_delivery_state_invalid")

            now = _now()
            history = list(row.state_history) if isinstance(row.state_history, list) else []
            history.extend(
                [
                    {"state": "executed", "at": now.isoformat()},
                    {
                        "state": EVALUATION_DELIVERY_STATE_EVIDENCE_PERSISTED,
                        "at": now.isoformat(),
                    },
                ]
            )
            row.state = EVALUATION_DELIVERY_STATE_EVIDENCE_PERSISTED
            row.state_history = history
            row.evidence = dict(evidence)
            row.replay_response = dict(replay_response)
            row.executed_at = now
            row.evidence_persisted_at = now
            row.raw_task_input_persisted = False
            row.raw_secret_visible = False

            return {
                "record_id": record_id,
                "state": EVALUATION_DELIVERY_STATE_EVIDENCE_PERSISTED,
                "evidence": dict(evidence),
                "replay_response": dict(replay_response),
                "raw_task_input_persisted": False,
                "raw_secret_visible": False,
            }
    except EvaluationDeliveryError:
        raise
    except Exception as exc:
        raise EvaluationDeliveryError("evaluation_delivery_database_unavailable") from exc


async def fail_evaluation_execution(
    *, owner_id: str, record_id: str, failure_code: str
) -> None:
    """Persist an uncertain/failed network outcome without enabling replay."""

    del owner_id
    try:
        async with session_scope() as session:
            selected = await session.execute(
                select(EvaluationRuntimeDelivery)
                .where(EvaluationRuntimeDelivery.record_id == record_id)
                .with_for_update()
            )
            row = selected.scalar_one_or_none()
            if row is None or row.state == EVALUATION_DELIVERY_STATE_EVIDENCE_PERSISTED:
                return

            now = _now()
            history = list(row.state_history) if isinstance(row.state_history, list) else []
            history.append({"state": "failed", "at": now.isoformat()})
            row.state = "failed"
            row.state_history = history
            row.failed_at = now
            row.failure_code = str(failure_code or "evaluation_execution_failed")[:200]
            row.network_outcome = "unknown"
    except EvaluationDeliveryError:
        raise
    except Exception as exc:
        raise EvaluationDeliveryError("evaluation_delivery_database_unavailable") from exc


__all__ = [
    "EvaluationDeliveryError",
    "EvaluationIdempotencyConflictError",
    "EvaluationReplayBlockedError",
    "claim_evaluation_execution",
    "complete_evaluation_execution",
    "evaluation_request_fingerprint",
    "fail_evaluation_execution",
]
