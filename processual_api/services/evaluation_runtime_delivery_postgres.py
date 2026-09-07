"""Shared transactional idempotency and quota authority for External Evaluation runtime."""

from __future__ import annotations

import hashlib
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from processual_api.db.session import session_scope
from processual_api.services.evaluation_authority_models import EvaluationAuthorityKey, EvaluationAuthorityState
from processual_api.services.evaluation_grants import EVALUATION_EXECUTION_MODE, find_evaluation_grant, refresh_evaluation_grant_status
from processual_api.services.evaluation_runtime_delivery import (
    EVALUATION_DELIVERY_STATE_EVIDENCE_PERSISTED,
    EVALUATION_DELIVERY_STATE_EXECUTING,
    EvaluationDeliveryError,
    EvaluationIdempotencyConflictError,
    EvaluationReplayBlockedError,
    _validate_safe_replay_response,
    evaluation_request_fingerprint,
)
from processual_api.services.evaluation_runtime_delivery_models import EvaluationRuntimeDelivery


class EvaluationQuotaExceededError(EvaluationDeliveryError):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)


def _owner_digest(owner_id: str) -> str:
    return hashlib.sha256(str(owner_id or "").encode("utf-8")).hexdigest()


def _idempotency_digest(idempotency_key: str) -> str:
    return hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()


def _record_id(*, owner_id: str, grant_id: str, api_key_id: str, idempotency_key: str) -> str:
    material = "\0".join((str(owner_id or ""), str(grant_id or ""), str(api_key_id or ""), idempotency_key))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


async def _consume_admission_quota(session: Any, *, owner_id: str, grant_id: str, api_key_id: str, now: datetime) -> int:
    key = (
        await session.execute(
            select(EvaluationAuthorityKey)
            .where(
                EvaluationAuthorityKey.key_id == api_key_id,
                EvaluationAuthorityKey.owner_id == owner_id,
                EvaluationAuthorityKey.grant_id == grant_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if key is None or key.status != "enabled" or key.revoked_at is not None:
        raise EvaluationDeliveryError("evaluation_authority_key_inactive")
    expires_at = _as_utc(key.expires_at)
    if expires_at is not None and expires_at <= now:
        key.status = "expired"
        raise EvaluationDeliveryError("evaluation_authority_key_expired")

    state = (
        await session.execute(
            select(EvaluationAuthorityState)
            .where(EvaluationAuthorityState.owner_id == owner_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if state is None or not isinstance(state.authority, dict):
        raise EvaluationDeliveryError("evaluation_authority_state_missing")
    raw = deepcopy(state.authority)
    grant = find_evaluation_grant(raw, grant_id)
    if grant is None:
        raise EvaluationDeliveryError("evaluation_grant_not_found")
    refresh_evaluation_grant_status(grant, now=now)
    if (
        grant.get("status") != "active"
        or grant.get("execution_mode") != EVALUATION_EXECUTION_MODE
        or grant.get("real_runtime_execution") is not True
        or grant.get("production_allowed") is not False
    ):
        raise EvaluationDeliveryError("evaluation_grant_inactive")

    grant_limit = int(grant.get("max_requests", 0) or 0)
    payload = dict(key.payload or {})
    key_limit = int(payload.get("quota_limit", 0) or 0)
    effective_limit = grant_limit if key_limit <= 0 else min(grant_limit, key_limit)
    if effective_limit <= 0 or key.usage_count >= effective_limit:
        key.quota_rejected_count += 1
        payload["evaluation_grant_state"] = "quota_exhausted"
        payload["quota_rejected_count"] = key.quota_rejected_count
        payload["quota_semantics"] = "admitted_execution"
        key.payload = payload
        raise EvaluationQuotaExceededError("evaluation_execution_quota_exhausted")

    key.usage_count += 1
    key.last_used_at = now
    payload["usage_count"] = key.usage_count
    payload["last_used_at"] = now.isoformat()
    payload["evaluation_grant_state"] = "active"
    payload["quota_semantics"] = "admitted_execution"
    key.payload = payload
    return key.usage_count


async def claim_evaluation_execution(
    *, owner_id: str, grant_id: str, api_key_id: str, idempotency_key: str,
    request_fingerprint: str, task_id: str, binding_id: str,
) -> dict[str, Any]:
    """Claim one new execution and consume one unit, or return replay at zero cost."""
    normalized_key = str(idempotency_key or "").strip()
    if not normalized_key:
        raise EvaluationDeliveryError("evaluation_idempotency_key_required")
    record_id = _record_id(owner_id=owner_id, grant_id=grant_id, api_key_id=api_key_id, idempotency_key=normalized_key)
    now = _now()
    history = [{"state": "accepted", "at": now.isoformat()}, {"state": EVALUATION_DELIVERY_STATE_EXECUTING, "at": now.isoformat()}]
    try:
        async with session_scope() as session:
            insert_statement = (
                pg_insert(EvaluationRuntimeDelivery)
                .values(
                    record_id=record_id,
                    owner_id_sha256=_owner_digest(owner_id),
                    grant_id=str(grant_id or ""), api_key_id=str(api_key_id or ""),
                    idempotency_key_sha256=_idempotency_digest(normalized_key),
                    request_fingerprint=request_fingerprint,
                    task_id=str(task_id or "").strip().lower(), binding_id=str(binding_id or "").strip(),
                    state=EVALUATION_DELIVERY_STATE_EXECUTING, state_history=history,
                    accepted_at=now, execution_started_at=now,
                    raw_task_input_persisted=False, raw_secret_visible=False,
                )
                .on_conflict_do_nothing()
                .returning(EvaluationRuntimeDelivery.record_id)
            )
            inserted = await session.execute(insert_statement)
            if inserted.scalar_one_or_none() is not None:
                usage_count = await _consume_admission_quota(
                    session, owner_id=owner_id, grant_id=grant_id, api_key_id=api_key_id, now=now
                )
                return {
                    "status": "claimed",
                    "record": {
                        "record_id": record_id, "request_fingerprint": request_fingerprint,
                        "state": EVALUATION_DELIVERY_STATE_EXECUTING,
                        "usage_count": usage_count, "quota_semantics": "admitted_execution",
                        "raw_task_input_persisted": False, "raw_secret_visible": False,
                    },
                }

            existing = (
                await session.execute(select(EvaluationRuntimeDelivery).where(EvaluationRuntimeDelivery.record_id == record_id))
            ).scalar_one_or_none()
            if existing is None:
                raise EvaluationDeliveryError("evaluation_delivery_claim_conflict_unresolved")
            if existing.request_fingerprint != request_fingerprint:
                raise EvaluationIdempotencyConflictError("evaluation_idempotency_key_payload_mismatch")
            state = str(existing.state or "")
            if state != EVALUATION_DELIVERY_STATE_EVIDENCE_PERSISTED:
                raise EvaluationReplayBlockedError(f"evaluation_replay_blocked_{state or 'unknown'}")
            replay = existing.replay_response
            if not isinstance(replay, dict):
                raise EvaluationReplayBlockedError("evaluation_replay_evidence_unavailable")
            return {
                "status": "replay",
                "record": {
                    "record_id": existing.record_id, "request_fingerprint": existing.request_fingerprint,
                    "state": existing.state, "quota_semantics": "admitted_execution",
                    "raw_task_input_persisted": existing.raw_task_input_persisted,
                    "raw_secret_visible": existing.raw_secret_visible,
                },
                "response": dict(replay),
            }
    except EvaluationDeliveryError:
        raise
    except Exception as exc:
        raise EvaluationDeliveryError("evaluation_delivery_database_unavailable") from exc


async def complete_evaluation_execution(*, owner_id: str, record_id: str, evidence: dict[str, Any], replay_response: dict[str, Any]) -> dict[str, Any]:
    del owner_id
    _validate_safe_replay_response(replay_response)
    try:
        async with session_scope() as session:
            row = (
                await session.execute(select(EvaluationRuntimeDelivery).where(EvaluationRuntimeDelivery.record_id == record_id).with_for_update())
            ).scalar_one_or_none()
            if row is None:
                raise EvaluationDeliveryError("evaluation_delivery_claim_missing")
            if row.state != EVALUATION_DELIVERY_STATE_EXECUTING:
                raise EvaluationDeliveryError("evaluation_delivery_state_invalid")
            now = _now()
            history = list(row.state_history) if isinstance(row.state_history, list) else []
            history.extend([{"state": "executed", "at": now.isoformat()}, {"state": EVALUATION_DELIVERY_STATE_EVIDENCE_PERSISTED, "at": now.isoformat()}])
            row.state = EVALUATION_DELIVERY_STATE_EVIDENCE_PERSISTED
            row.state_history = history; row.evidence = dict(evidence); row.replay_response = dict(replay_response)
            row.executed_at = now; row.evidence_persisted_at = now
            row.raw_task_input_persisted = False; row.raw_secret_visible = False
            return {"record_id": record_id, "state": EVALUATION_DELIVERY_STATE_EVIDENCE_PERSISTED, "evidence": dict(evidence), "replay_response": dict(replay_response), "raw_task_input_persisted": False, "raw_secret_visible": False}
    except EvaluationDeliveryError:
        raise
    except Exception as exc:
        raise EvaluationDeliveryError("evaluation_delivery_database_unavailable") from exc


async def fail_evaluation_execution(*, owner_id: str, record_id: str, failure_code: str) -> None:
    del owner_id
    try:
        async with session_scope() as session:
            row = (
                await session.execute(select(EvaluationRuntimeDelivery).where(EvaluationRuntimeDelivery.record_id == record_id).with_for_update())
            ).scalar_one_or_none()
            if row is None or row.state == EVALUATION_DELIVERY_STATE_EVIDENCE_PERSISTED:
                return
            now = _now()
            history = list(row.state_history) if isinstance(row.state_history, list) else []
            history.append({"state": "failed", "at": now.isoformat()})
            row.state = "failed"; row.state_history = history; row.failed_at = now
            row.failure_code = str(failure_code or "evaluation_execution_failed")[:200]
            row.network_outcome = "unknown"
    except EvaluationDeliveryError:
        raise
    except Exception as exc:
        raise EvaluationDeliveryError("evaluation_delivery_database_unavailable") from exc


__all__ = [
    "EvaluationDeliveryError", "EvaluationIdempotencyConflictError", "EvaluationQuotaExceededError",
    "EvaluationReplayBlockedError", "claim_evaluation_execution", "complete_evaluation_execution",
    "evaluation_request_fingerprint", "fail_evaluation_execution",
]
