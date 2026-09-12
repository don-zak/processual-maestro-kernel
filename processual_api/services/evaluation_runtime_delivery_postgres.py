"""Shared transactional idempotency, quota, and audit authority for External Evaluation runtime."""

from __future__ import annotations

import hashlib
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from processual_api.db.session import session_scope
from processual_api.services.evaluation_authority_models import (
    EvaluationAuthorityKey,
    EvaluationAuthorityState,
)
from processual_api.services.evaluation_grants import (
    EVALUATION_EXECUTION_MODE,
    find_evaluation_grant,
    refresh_evaluation_grant_status,
)
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


class EvaluationQuotaExceededError(EvaluationDeliveryError):
    pass


_AUDIT_EVIDENCE_KEYS = frozenset(
    {
        "execution_id",
        "evaluation_grant_id",
        "api_key_id",
        "binding_id",
        "task_id",
        "adapter_contract_id",
        "operation_class",
        "http_status",
        "network_request_executed",
        "mapping_valid",
        "ready_for_task_consumption",
        "response_sha256",
        "task_injection_sha256",
        "evidence_sha256",
        "completed_at",
        "evaluation_stage",
        "maestro_task_completed",
        "raw_task_input_persisted",
        "raw_secret_visible",
    }
)


def _now() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)


def _iso(value: datetime | None) -> str | None:
    parsed = _as_utc(value)
    return parsed.isoformat() if parsed else None


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


def _safe_audit_evidence(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    safe = {key: value[key] for key in _AUDIT_EVIDENCE_KEYS if key in value}
    safe["raw_task_input_persisted"] = False
    safe["raw_secret_visible"] = False
    return safe


def _execution_status(row: EvaluationRuntimeDelivery) -> str:
    state = str(row.state or "")
    if state == EVALUATION_DELIVERY_STATE_EVIDENCE_PERSISTED:
        return "succeeded"
    if state == "failed":
        return "failed"
    return "executing"


def _customer_execution_receipt(row: EvaluationRuntimeDelivery) -> dict[str, Any]:
    evidence = _safe_audit_evidence(row.evidence)
    return {
        "execution_id": str(evidence.get("execution_id") or row.record_id),
        "record_id": row.record_id,
        "status": _execution_status(row),
        "ledger_state": str(row.state or ""),
        "task_id": row.task_id,
        "binding_id": row.binding_id,
        "accepted_at": _iso(row.accepted_at),
        "execution_started_at": _iso(row.execution_started_at),
        "executed_at": _iso(row.executed_at),
        "evidence_persisted_at": _iso(row.evidence_persisted_at),
        "failed_at": _iso(row.failed_at),
        "failure_code": row.failure_code,
        "network_outcome": row.network_outcome,
        "http_status": evidence.get("http_status"),
        "network_request_executed": evidence.get("network_request_executed") is True,
        "mapping_valid": evidence.get("mapping_valid") is True,
        "evidence_sha256": evidence.get("evidence_sha256"),
        "evidence_persisted": row.evidence_persisted_at is not None,
        "production_allowed": False,
        "raw_task_input_persisted": False,
        "raw_secret_visible": False,
    }


def _audit_receipt(row: EvaluationRuntimeDelivery) -> dict[str, Any]:
    return {
        "audit_id": row.record_id,
        "grant_id": row.grant_id,
        "api_key_id": row.api_key_id,
        "task_id": row.task_id,
        "binding_id": row.binding_id,
        "status": _execution_status(row),
        "ledger_state": str(row.state or ""),
        "request_fingerprint": row.request_fingerprint,
        "idempotency_key_sha256": row.idempotency_key_sha256,
        "accepted_at": _iso(row.accepted_at),
        "execution_started_at": _iso(row.execution_started_at),
        "executed_at": _iso(row.executed_at),
        "evidence_persisted_at": _iso(row.evidence_persisted_at),
        "failed_at": _iso(row.failed_at),
        "failure_code": row.failure_code,
        "network_outcome": row.network_outcome,
        "evidence": _safe_audit_evidence(row.evidence),
        "audit_copy_for_admin": True,
        "production_allowed": False,
        "raw_task_input_persisted": False,
        "raw_secret_visible": False,
    }


async def latest_evaluation_execution_status(
    owner_id: str,
    grant_id: str,
    api_key_id: str,
) -> dict[str, Any] | None:
    try:
        async with session_scope() as session:
            row = (
                await session.execute(
                    select(EvaluationRuntimeDelivery)
                    .where(
                        EvaluationRuntimeDelivery.owner_id_sha256 == _owner_digest(owner_id),
                        EvaluationRuntimeDelivery.grant_id == grant_id,
                        EvaluationRuntimeDelivery.api_key_id == api_key_id,
                    )
                    .order_by(EvaluationRuntimeDelivery.accepted_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            return _customer_execution_receipt(row) if row is not None else None
    except Exception as exc:
        raise EvaluationDeliveryError("evaluation_execution_status_unavailable") from exc


async def get_evaluation_execution_status(
    owner_id: str,
    grant_id: str,
    api_key_id: str,
    execution_id: str,
) -> dict[str, Any] | None:
    """Resolve a safe execution receipt by public execution id or internal record id."""
    try:
        async with session_scope() as session:
            rows = (
                await session.execute(
                    select(EvaluationRuntimeDelivery)
                    .where(
                        EvaluationRuntimeDelivery.owner_id_sha256 == _owner_digest(owner_id),
                        EvaluationRuntimeDelivery.grant_id == grant_id,
                        EvaluationRuntimeDelivery.api_key_id == api_key_id,
                    )
                    .order_by(EvaluationRuntimeDelivery.accepted_at.desc())
                    .limit(100)
                )
            ).scalars().all()
            wanted = str(execution_id or "").strip()
            for row in rows:
                evidence = row.evidence if isinstance(row.evidence, dict) else {}
                public_id = str(evidence.get("execution_id") or "")
                if row.record_id == wanted or public_id == wanted:
                    return _customer_execution_receipt(row)
            return None
    except Exception as exc:
        raise EvaluationDeliveryError("evaluation_execution_status_unavailable") from exc


async def list_evaluation_audit_receipts(
    owner_id: str,
    grant_id: str,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    bounded_limit = max(1, min(int(limit or 50), 100))
    try:
        async with session_scope() as session:
            rows = (
                await session.execute(
                    select(EvaluationRuntimeDelivery)
                    .where(
                        EvaluationRuntimeDelivery.owner_id_sha256 == _owner_digest(owner_id),
                        EvaluationRuntimeDelivery.grant_id == grant_id,
                    )
                    .order_by(EvaluationRuntimeDelivery.accepted_at.desc())
                    .limit(bounded_limit)
                )
            ).scalars().all()
            return [_audit_receipt(row) for row in rows]
    except Exception as exc:
        raise EvaluationDeliveryError("evaluation_audit_receipts_unavailable") from exc


def _resolve_existing_claim(
    existing: EvaluationRuntimeDelivery,
    *,
    request_fingerprint: str,
) -> dict[str, Any]:
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
            "quota_semantics": "admitted_execution",
            "raw_task_input_persisted": existing.raw_task_input_persisted,
            "raw_secret_visible": existing.raw_secret_visible,
        },
        "response": dict(replay),
    }


async def _lock_admission_authority(
    session: Any,
    *,
    owner_id: str,
    grant_id: str,
    api_key_id: str,
    now: datetime,
) -> tuple[EvaluationAuthorityKey, int]:
    """Lock grant state before key, matching grant-wide revocation lock order."""

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

    payload = dict(key.payload or {})
    grant_limit = int(grant.get("max_requests", 0) or 0)
    key_limit = int(payload.get("quota_limit", 0) or 0)
    effective_limit = grant_limit if key_limit <= 0 else min(grant_limit, key_limit)
    return key, effective_limit


def _record_quota_rejection(key: EvaluationAuthorityKey) -> None:
    payload = dict(key.payload or {})
    key.quota_rejected_count += 1
    payload["evaluation_grant_state"] = "quota_exhausted"
    payload["quota_rejected_count"] = key.quota_rejected_count
    payload["quota_semantics"] = "admitted_execution"
    key.payload = payload


def _consume_admission_quota(key: EvaluationAuthorityKey, *, now: datetime) -> int:
    payload = dict(key.payload or {})
    key.usage_count += 1
    key.last_used_at = now
    payload["usage_count"] = key.usage_count
    payload["last_used_at"] = now.isoformat()
    payload["evaluation_grant_state"] = "active"
    payload["quota_semantics"] = "admitted_execution"
    key.payload = payload
    return key.usage_count


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
    """Admit one unique execution atomically; durable replay consumes zero units."""

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
    quota_exhausted = False
    claimed: dict[str, Any] | None = None

    try:
        async with session_scope() as session:
            existing = (
                await session.execute(
                    select(EvaluationRuntimeDelivery).where(
                        EvaluationRuntimeDelivery.record_id == record_id
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                return _resolve_existing_claim(
                    existing,
                    request_fingerprint=request_fingerprint,
                )

            key, effective_limit = await _lock_admission_authority(
                session,
                owner_id=owner_id,
                grant_id=grant_id,
                api_key_id=api_key_id,
                now=now,
            )

            # Re-read after authority locks. A concurrent same-key request may
            # have committed the idempotency record while this transaction waited.
            existing = (
                await session.execute(
                    select(EvaluationRuntimeDelivery).where(
                        EvaluationRuntimeDelivery.record_id == record_id
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                return _resolve_existing_claim(
                    existing,
                    request_fingerprint=request_fingerprint,
                )

            if effective_limit <= 0 or key.usage_count >= effective_limit:
                _record_quota_rejection(key)
                quota_exhausted = True
            else:
                usage_count = _consume_admission_quota(key, now=now)
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
                if inserted.scalar_one_or_none() is None:
                    # Defensive rollback of the in-memory unit if an unexpected
                    # conflict appears despite state/key serialization.
                    key.usage_count -= 1
                    payload = dict(key.payload or {})
                    payload["usage_count"] = key.usage_count
                    key.payload = payload
                    existing = (
                        await session.execute(
                            select(EvaluationRuntimeDelivery).where(
                                EvaluationRuntimeDelivery.record_id == record_id
                            )
                        )
                    ).scalar_one_or_none()
                    if existing is None:
                        raise EvaluationDeliveryError(
                            "evaluation_delivery_claim_conflict_unresolved"
                        )
                    return _resolve_existing_claim(
                        existing,
                        request_fingerprint=request_fingerprint,
                    )

                claimed = {
                    "status": "claimed",
                    "record": {
                        "record_id": record_id,
                        "request_fingerprint": request_fingerprint,
                        "state": EVALUATION_DELIVERY_STATE_EXECUTING,
                        "usage_count": usage_count,
                        "quota_semantics": "admitted_execution",
                        "raw_task_input_persisted": False,
                        "raw_secret_visible": False,
                    },
                }
    except EvaluationDeliveryError:
        raise
    except Exception as exc:
        raise EvaluationDeliveryError("evaluation_delivery_database_unavailable") from exc

    # Raise only after the session context has committed rejection telemetry.
    if quota_exhausted:
        raise EvaluationQuotaExceededError("evaluation_execution_quota_exhausted")
    if claimed is None:
        raise EvaluationDeliveryError("evaluation_delivery_claim_unresolved")
    return claimed


async def complete_evaluation_execution(
    *,
    owner_id: str,
    record_id: str,
    evidence: dict[str, Any],
    replay_response: dict[str, Any],
) -> dict[str, Any]:
    del owner_id
    _validate_safe_replay_response(replay_response)
    try:
        async with session_scope() as session:
            row = (
                await session.execute(
                    select(EvaluationRuntimeDelivery)
                    .where(EvaluationRuntimeDelivery.record_id == record_id)
                    .with_for_update()
                )
            ).scalar_one_or_none()
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
    del owner_id
    try:
        async with session_scope() as session:
            row = (
                await session.execute(
                    select(EvaluationRuntimeDelivery)
                    .where(EvaluationRuntimeDelivery.record_id == record_id)
                    .with_for_update()
                )
            ).scalar_one_or_none()
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
    "EvaluationQuotaExceededError",
    "EvaluationReplayBlockedError",
    "claim_evaluation_execution",
    "complete_evaluation_execution",
    "evaluation_request_fingerprint",
    "fail_evaluation_execution",
    "get_evaluation_execution_status",
    "latest_evaluation_execution_status",
    "list_evaluation_audit_receipts",
]
