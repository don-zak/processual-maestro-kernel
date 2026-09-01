from __future__ import annotations

import hashlib
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
    evaluation_grants,
    find_evaluation_grant,
    refresh_evaluation_grant_status,
)


class EvaluationAuthorityError(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


def _lookup_sha256(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
    text = str(value or "").strip()
    if not text:
        return None
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def evaluation_authority_snapshot(raw: dict[str, Any]) -> dict[str, Any]:
    allowed_keys = (
        "evaluation_grants_v1",
        "enterprise_endpoint_bindings_v1",
        "enterprise_endpoint_request_mappings_v1",
        "enterprise_endpoint_sandbox_grants_v1",
        "enterprise_endpoint_sandbox_secret_references_v1",
        "enterprise_endpoint_sandbox_content_contracts_v1",
        "enterprise_endpoint_sandbox_evidence_v1",
    )
    return {
        key: raw.get(key, [])
        for key in allowed_keys
        if isinstance(raw.get(key), list)
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
            return dict(row.authority)
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
            return sum(1 for row in rows if row.expires_at is None or row.expires_at > now)
    except Exception as exc:
        raise EvaluationAuthorityError("evaluation_authority_key_count_failed") from exc


async def revoke_evaluation_authority_grant(owner_id: str, grant_id: str) -> int:
    try:
        async with session_scope() as session:
            state = await session.get(EvaluationAuthorityState, owner_id, with_for_update=True)
            if state is None or not isinstance(state.authority, dict):
                raise EvaluationAuthorityError("evaluation_authority_state_missing")
            raw = dict(state.authority)
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
                payload["revoked_at"] = now.isoformat()
                payload["revocation_reason"] = "evaluation_grant_revoked"
                key.payload = payload
            return len(keys)
    except EvaluationAuthorityError:
        raise
    except Exception as exc:
        raise EvaluationAuthorityError("evaluation_authority_revoke_failed") from exc


async def verify_evaluation_api_key(raw_key: str) -> dict[str, Any] | None:
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
            if key.expires_at is not None and key.expires_at <= now:
                key.status = "expired"
                return None
            if not _verify_stored_key(raw_key, key.hashed):
                return None

            state = await session.get(EvaluationAuthorityState, key.owner_id)
            if state is None or not isinstance(state.authority, dict):
                return None
            raw = dict(state.authority)
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

            grant_limit = int(grant.get("max_requests", 0) or 0)
            key_limit = int((key.payload or {}).get("quota_limit", 0) or 0)
            effective_limit = grant_limit if key_limit <= 0 else min(grant_limit, key_limit)
            if effective_limit <= 0 or key.usage_count >= effective_limit:
                key.quota_rejected_count += 1
                payload = dict(key.payload or {})
                payload["evaluation_grant_state"] = "quota_exhausted"
                payload["quota_rejected_count"] = key.quota_rejected_count
                key.payload = payload
                return None

            key.usage_count += 1
            key.last_used_at = now
            payload = dict(key.payload or {})
            payload["usage_count"] = key.usage_count
            payload["last_used_at"] = now.isoformat()
            payload["evaluation_grant_state"] = "active"
            key.payload = payload

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
                "task_authority_source": str(grant.get("task_authority_source") or "integration_task_catalog"),
                "endpoint_authority_source": str(grant.get("endpoint_authority_source") or "canonical_runtime_access_policy"),
                "execution_mode": EVALUATION_EXECUTION_MODE,
                "real_runtime_execution": True,
                "evaluation_access": True,
                "production_allowed": False,
            }
    except Exception as exc:
        raise EvaluationAuthorityError("evaluation_authority_database_unavailable") from exc


__all__ = [
    "EvaluationAuthorityError",
    "active_evaluation_key_count",
    "create_evaluation_authority_key",
    "evaluation_authority_snapshot",
    "load_evaluation_authority_state",
    "revoke_evaluation_authority_grant",
    "save_evaluation_authority_state",
    "verify_evaluation_api_key",
]
