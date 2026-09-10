from __future__ import annotations

import hashlib
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from processual_api.db.session import session_scope
from processual_api.services.api_key_store import _verify_stored_key
from processual_api.services.evaluation_authority_models import (
    EvaluationAuthorityKey,
    EvaluationAuthorityState,
)
from processual_api.services.evaluation_grants import (
    EVALUATION_EXECUTION_MODE,
    find_evaluation_grant,
    refresh_evaluation_grant_status,
)
from processual_api.services.evaluation_key_quota_policy import (
    normalized_evaluation_key_type,
)


class EvaluationAuthorityError(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)


def _lookup_sha256(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return _as_utc(value)
    text = str(value or "").strip()
    if not text:
        return None
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return _as_utc(parsed)


def evaluation_authority_snapshot(raw: dict[str, Any]) -> dict[str, Any]:
    allowed_keys = (
        "evaluation_grants_v1",
        "enterprise_endpoint_bindings_v1",
        "enterprise_endpoint_request_mappings_v1",
        "enterprise_endpoint_sandbox_grants_v1",
        "enterprise_sandbox_secret_references_v1",
        "enterprise_sandbox_content_contracts_v1",
        "enterprise_endpoint_sandbox_evidence_v1",
    )
    return {
        key: deepcopy(raw.get(key, []))
        for key in allowed_keys
        if isinstance(raw.get(key), list)
    }


def _safe_key_summary(row: EvaluationAuthorityKey) -> dict[str, Any]:
    payload = dict(row.payload or {})
    return {
        "key_id": row.key_id,
        "grant_id": row.grant_id,
        "prefix": row.prefix,
        "status": row.status,
        "lifecycle_status": str(payload.get("lifecycle_status") or "issued"),
        "label": str(payload.get("label") or ""),
        "issued_to": str(payload.get("issued_to") or ""),
        "created_at": _as_utc(row.created_at).isoformat(),
        "delivered_at": payload.get("delivered_at"),
        "delivered_by": payload.get("delivered_by"),
        "acknowledged_at": payload.get("acknowledged_at"),
        "acknowledged_by": payload.get("acknowledged_by"),
        "last_used_at": _as_utc(row.last_used_at).isoformat() if row.last_used_at else None,
        "usage_count": row.usage_count,
        "quota_rejected_count": row.quota_rejected_count,
        "expires_at": _as_utc(row.expires_at).isoformat() if row.expires_at else None,
        "revoked_at": _as_utc(row.revoked_at).isoformat() if row.revoked_at else None,
        "revoked_by": payload.get("revoked_by"),
        "revocation_reason": payload.get("revocation_reason"),
        "quota_semantics": "admitted_execution",
        "production_allowed": False,
        "raw_secret_visible": False,
    }


async def save_evaluation_authority_state(owner_id: str, raw: dict[str, Any]) -> None:
    snapshot = evaluation_authority_snapshot(raw)
    now = _now()
    try:
        async with session_scope() as session:
            row = await session.get(EvaluationAuthorityState, owner_id)
            if row is None:
                row = EvaluationAuthorityState(
                    owner_id=owner_id,
                    authority=snapshot,
                    updated_at=now,
                    production_allowed=False,
                    raw_secret_visible=False,
                )
                session.add(row)
            else:
                row.authority = snapshot
                row.updated_at = now
                row.production_allowed = False
                row.raw_secret_visible = False
    except Exception as exc:
        raise EvaluationAuthorityError("evaluation_authority_database_unavailable") from exc


async def load_evaluation_authority_state(owner_id: str) -> dict[str, Any]:
    try:
        async with session_scope() as session:
            row = await session.get(EvaluationAuthorityState, owner_id)
            if row is None or not isinstance(row.authority, dict):
                raise EvaluationAuthorityError("evaluation_authority_state_missing")
            return deepcopy(row.authority)
    except EvaluationAuthorityError:
        raise
    except Exception as exc:
        raise EvaluationAuthorityError("evaluation_authority_database_unavailable") from exc


async def create_evaluation_authority_key(
    *, owner_id: str, raw_key: str, entry: dict[str, Any]
) -> None:
    now = _now()
    try:
        async with session_scope() as session:
            row = EvaluationAuthorityKey(
                key_id=str(entry["id"]),
                owner_id=owner_id,
                grant_id=str(entry["evaluation_grant_id"]),
                lookup_sha256=_lookup_sha256(raw_key),
                prefix=str(entry.get("prefix") or ""),
                hashed=str(entry["hashed"]),
                status=str(entry.get("status") or "enabled"),
                expires_at=_parse_datetime(entry.get("expires_at")),
                usage_count=int(entry.get("usage_count", 0) or 0),
                quota_rejected_count=int(entry.get("quota_rejected_count", 0) or 0),
                payload={key: value for key, value in entry.items() if key != "hashed"},
                created_at=_parse_datetime(entry.get("created_at")) or now,
                last_used_at=None,
                revoked_at=None,
                production_allowed=False,
                raw_secret_visible=False,
            )
            session.add(row)
    except Exception as exc:
        raise EvaluationAuthorityError("evaluation_authority_key_create_failed") from exc


async def list_evaluation_authority_keys(owner_id: str, grant_id: str) -> list[dict[str, Any]]:
    try:
        async with session_scope() as session:
            rows = (
                await session.execute(
                    select(EvaluationAuthorityKey)
                    .where(
                        EvaluationAuthorityKey.owner_id == owner_id,
                        EvaluationAuthorityKey.grant_id == grant_id,
                    )
                    .order_by(EvaluationAuthorityKey.created_at.desc())
                )
            ).scalars().all()
            return [_safe_key_summary(row) for row in rows]
    except Exception as exc:
        raise EvaluationAuthorityError("evaluation_authority_key_list_failed") from exc


async def evaluation_key_runtime_status(
    owner_id: str,
    grant_id: str,
    key_id: str,
) -> dict[str, Any]:
    """Return a customer-safe status snapshot without consuming execution quota."""

    try:
        async with session_scope() as session:
            key = (
                await session.execute(
                    select(EvaluationAuthorityKey).where(
                        EvaluationAuthorityKey.key_id == key_id,
                        EvaluationAuthorityKey.owner_id == owner_id,
                        EvaluationAuthorityKey.grant_id == grant_id,
                    )
                )
            ).scalar_one_or_none()
            if key is None:
                raise EvaluationAuthorityError("evaluation_authority_key_not_found")

            state = await session.get(EvaluationAuthorityState, owner_id)
            if state is None or not isinstance(state.authority, dict):
                raise EvaluationAuthorityError("evaluation_authority_state_missing")
            raw = deepcopy(state.authority)
            grant = find_evaluation_grant(raw, grant_id)
            if grant is None:
                raise EvaluationAuthorityError("evaluation_grant_not_found")
            refresh_evaluation_grant_status(grant)

            payload = dict(key.payload or {})
            grant_limit = int(grant.get("max_requests", 0) or 0)
            key_limit = int(payload.get("quota_limit", 0) or 0)
            quota_limit = grant_limit if key_limit <= 0 else min(grant_limit, key_limit)
            quota_used = max(0, int(key.usage_count or 0))
            quota_remaining = max(0, quota_limit - quota_used)
            evaluation_type = normalized_evaluation_key_type(
                str(grant.get("evaluation_type") or payload.get("evaluation_type") or ""),
                allowed_binding_ids=list(grant.get("allowed_binding_ids") or []),
                allowed_endpoints=list(grant.get("allowed_endpoints") or []),
            )
            now = _now()
            expires_at = _as_utc(key.expires_at)
            if key.revoked_at is not None or key.status == "revoked":
                credential_status = "revoked"
            elif expires_at is not None and expires_at <= now:
                credential_status = "expired"
            elif grant.get("status") != "active":
                credential_status = str(grant.get("status") or "inactive")
            elif quota_limit <= 0 or quota_remaining <= 0:
                credential_status = "quota_exhausted"
            elif key.status != "enabled":
                credential_status = str(key.status or "inactive")
            else:
                credential_status = "active"

            warning_threshold = max(1, min(10, quota_limit // 10)) if quota_limit > 0 else 0
            quota_warning = (
                "exhausted"
                if quota_remaining <= 0
                else "low"
                if warning_threshold and quota_remaining <= warning_threshold
                else "normal"
            )
            return {
                "credential_status": credential_status,
                "evaluation_type": evaluation_type,
                "grant_id": grant_id,
                "api_key_id": key_id,
                "api_key_prefix": key.prefix,
                "quota": {
                    "limit": quota_limit,
                    "used": quota_used,
                    "remaining": quota_remaining,
                    "warning": quota_warning,
                    "semantics": "admitted_execution",
                    "status_checks_consume_quota": False,
                    "idempotent_replays_consume_quota": False,
                },
                "expires_at": expires_at.isoformat() if expires_at else None,
                "last_used_at": (
                    _as_utc(key.last_used_at).isoformat() if key.last_used_at else None
                ),
                "allowed_task_ids": list(grant.get("allowed_task_ids") or []),
                "allowed_binding_ids": list(grant.get("allowed_binding_ids") or []),
                "production_allowed": False,
                "raw_secret_visible": False,
            }
    except EvaluationAuthorityError:
        raise
    except Exception as exc:
        raise EvaluationAuthorityError("evaluation_authority_status_unavailable") from exc


async def update_evaluation_authority_key_lifecycle(
    owner_id: str,
    grant_id: str,
    key_id: str,
    *,
    action: str,
    actor: str,
    reason: str | None = None,
) -> dict[str, Any]:
    if action not in {"confirm_delivery", "acknowledge", "revoke"}:
        raise EvaluationAuthorityError("evaluation_authority_key_action_invalid")
    try:
        async with session_scope() as session:
            row = (
                await session.execute(
                    select(EvaluationAuthorityKey)
                    .where(
                        EvaluationAuthorityKey.key_id == key_id,
                        EvaluationAuthorityKey.owner_id == owner_id,
                        EvaluationAuthorityKey.grant_id == grant_id,
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if row is None:
                raise EvaluationAuthorityError("evaluation_authority_key_not_found")

            now = _now()
            payload = dict(row.payload or {})
            current = str(payload.get("lifecycle_status") or "issued")

            if action == "confirm_delivery":
                if row.status != "enabled" or row.revoked_at is not None:
                    raise EvaluationAuthorityError("evaluation_authority_key_revoked")
                if current in {"delivery_confirmed", "acknowledged"}:
                    return _safe_key_summary(row)
                if current != "issued":
                    raise EvaluationAuthorityError("evaluation_authority_key_transition_invalid")
                payload["lifecycle_status"] = "delivery_confirmed"
                payload["delivered_at"] = now.isoformat()
                payload["delivered_by"] = actor

            elif action == "acknowledge":
                if row.status != "enabled" or row.revoked_at is not None:
                    raise EvaluationAuthorityError("evaluation_authority_key_revoked")
                if current == "acknowledged":
                    return _safe_key_summary(row)
                if current != "delivery_confirmed":
                    raise EvaluationAuthorityError("evaluation_authority_key_delivery_required")
                payload["lifecycle_status"] = "acknowledged"
                payload["acknowledged_at"] = now.isoformat()
                payload["acknowledged_by"] = actor

            else:
                if row.status == "revoked" or row.revoked_at is not None:
                    return _safe_key_summary(row)
                row.status = "revoked"
                row.revoked_at = now
                payload["status"] = "revoked"
                payload["lifecycle_status"] = "revoked"
                payload["revoked_at"] = now.isoformat()
                payload["revoked_by"] = actor
                payload["revocation_reason"] = (reason or "administrator_revoked").strip()[:500]

            row.payload = payload
            await session.flush()
            return _safe_key_summary(row)
    except EvaluationAuthorityError:
        raise
    except Exception as exc:
        raise EvaluationAuthorityError("evaluation_authority_key_update_failed") from exc


async def active_evaluation_key_count(owner_id: str, grant_id: str) -> int:
    try:
        async with session_scope() as session:
            rows = (
                await session.execute(
                    select(EvaluationAuthorityKey).where(
                        EvaluationAuthorityKey.owner_id == owner_id,
                        EvaluationAuthorityKey.grant_id == grant_id,
                        EvaluationAuthorityKey.status == "enabled",
                        EvaluationAuthorityKey.revoked_at.is_(None),
                    )
                )
            ).scalars().all()
            now = _now()
            return sum(
                1
                for row in rows
                if (expires_at := _as_utc(row.expires_at)) is None or expires_at > now
            )
    except Exception as exc:
        raise EvaluationAuthorityError("evaluation_authority_key_count_failed") from exc


async def revoke_evaluation_authority_grant(owner_id: str, grant_id: str) -> int:
    try:
        async with session_scope() as session:
            state_result = await session.execute(
                select(EvaluationAuthorityState)
                .where(EvaluationAuthorityState.owner_id == owner_id)
                .with_for_update()
            )
            state = state_result.scalar_one_or_none()
            if state is None or not isinstance(state.authority, dict):
                raise EvaluationAuthorityError("evaluation_authority_state_missing")
            raw = deepcopy(state.authority)
            grant = find_evaluation_grant(raw, grant_id)
            if grant is None:
                raise EvaluationAuthorityError("evaluation_grant_not_found")
            now = _now()
            grant["status"] = "revoked"
            grant["revoked_at"] = now.isoformat()
            state.authority = raw
            state.updated_at = now

            keys = (
                await session.execute(
                    select(EvaluationAuthorityKey)
                    .where(
                        EvaluationAuthorityKey.owner_id == owner_id,
                        EvaluationAuthorityKey.grant_id == grant_id,
                        EvaluationAuthorityKey.status == "enabled",
                    )
                    .with_for_update()
                )
            ).scalars().all()
            for key in keys:
                key.status = "revoked"
                key.revoked_at = now
                payload = dict(key.payload or {})
                payload["status"] = "revoked"
                payload["lifecycle_status"] = "revoked"
                payload["revoked_at"] = now.isoformat()
                payload["revocation_reason"] = "evaluation_grant_revoked"
                key.payload = payload
            return len(keys)
    except EvaluationAuthorityError:
        raise
    except Exception as exc:
        raise EvaluationAuthorityError("evaluation_authority_revoke_failed") from exc


async def verify_evaluation_api_key(raw_key: str) -> dict[str, Any] | None:
    """Authenticate Evaluation authority without consuming execution quota.

    Quota is consumed transactionally by the delivery claim when a new runtime
    execution is admitted. Authentication, invalid task/binding requests, and
    durable idempotent replays therefore do not increment ``usage_count``.
    """

    if not raw_key.startswith("pmk_"):
        return None
    try:
        async with session_scope() as session:
            key = (
                await session.execute(
                    select(EvaluationAuthorityKey)
                    .where(EvaluationAuthorityKey.lookup_sha256 == _lookup_sha256(raw_key))
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if key is None:
                return None
            if key.status != "enabled" or key.revoked_at is not None:
                return None
            now = _now()
            expires_at = _as_utc(key.expires_at)
            if expires_at is not None and expires_at <= now:
                key.status = "expired"
                return None
            if not _verify_stored_key(raw_key, key.hashed):
                return None

            state = await session.get(EvaluationAuthorityState, key.owner_id)
            if state is None or not isinstance(state.authority, dict):
                return None
            raw = deepcopy(state.authority)
            grant = find_evaluation_grant(raw, key.grant_id)
            if grant is None:
                return None
            refresh_evaluation_grant_status(grant)
            if (
                grant.get("status") != "active"
                or grant.get("execution_mode") != EVALUATION_EXECUTION_MODE
                or grant.get("real_runtime_execution") is not True
                or grant.get("production_allowed") is not False
            ):
                return None

            payload = dict(key.payload or {})
            return {
                "sub": key.owner_id,
                "user_id": str(payload.get("user_id") or key.owner_id),
                "client_id": str(payload.get("client_id") or key.owner_id),
                "role": str(payload.get("role") or "client"),
                "auth_method": "api_key",
                "session_type": "api_key",
                "api_key_id": key.key_id,
                "api_key_prefix": key.prefix,
                "scopes": list(payload.get("scopes") or []),
                "evaluation_grant_id": key.grant_id,
                "entitlement_source": "admin_evaluation_grant",
                "subscription_required": False,
                "registration_required": False,
                "commercial_quota_required": False,
                "allowed_task_ids": list(grant.get("allowed_task_ids") or []),
                "task_scope_ids": list(grant.get("task_scope_ids") or []),
                "allowed_binding_ids": list(grant.get("allowed_binding_ids") or []),
                "allowed_endpoints": list(grant.get("allowed_endpoints") or []),
                "task_authority_source": str(
                    grant.get("task_authority_source") or "integration_task_catalog"
                ),
                "endpoint_authority_source": str(
                    grant.get("endpoint_authority_source")
                    or "canonical_runtime_access_policy"
                ),
                "execution_mode": EVALUATION_EXECUTION_MODE,
                "real_runtime_execution": True,
                "evaluation_access": True,
                "quota_semantics": "admitted_execution",
                "production_allowed": False,
            }
    except EvaluationAuthorityError:
        raise
    except Exception as exc:
        raise EvaluationAuthorityError("evaluation_authority_database_unavailable") from exc


__all__ = [
    "EvaluationAuthorityError",
    "active_evaluation_key_count",
    "create_evaluation_authority_key",
    "evaluation_authority_snapshot",
    "evaluation_key_runtime_status",
    "list_evaluation_authority_keys",
    "load_evaluation_authority_state",
    "revoke_evaluation_authority_grant",
    "save_evaluation_authority_state",
    "update_evaluation_authority_key_lifecycle",
    "verify_evaluation_api_key",
]
