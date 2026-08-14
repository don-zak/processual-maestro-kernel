"""Governed admin evaluation grants for subscription-independent pilot access."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

EVALUATION_GRANTS_STORAGE_KEY = "evaluation_grants_v1"
EVALUATION_GRANT_ACTIVE = "active"
EVALUATION_GRANT_REVOKED = "revoked"
EVALUATION_GRANT_EXPIRED = "expired"


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def evaluation_grants(raw: dict[str, Any]) -> list[dict[str, Any]]:
    value = raw.get(EVALUATION_GRANTS_STORAGE_KEY, [])
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def find_evaluation_grant(
    raw: dict[str, Any],
    grant_id: str | None,
) -> dict[str, Any] | None:
    requested = str(grant_id or "").strip()
    if not requested:
        return None
    return next(
        (
            grant
            for grant in evaluation_grants(raw)
            if str(grant.get("grant_id") or "") == requested
        ),
        None,
    )


def refresh_evaluation_grant_status(
    grant: dict[str, Any],
    *,
    now: datetime | None = None,
) -> str:
    status = str(grant.get("status") or EVALUATION_GRANT_ACTIVE).strip().lower()
    if status in {EVALUATION_GRANT_REVOKED, EVALUATION_GRANT_EXPIRED}:
        return status

    current = now or datetime.now(UTC)
    expires_at = _parse_datetime(str(grant.get("expires_at") or ""))
    if expires_at is None or expires_at <= current:
        grant["status"] = EVALUATION_GRANT_EXPIRED
        grant["expired_at"] = current.isoformat()
        return EVALUATION_GRANT_EXPIRED

    grant["status"] = EVALUATION_GRANT_ACTIVE
    return EVALUATION_GRANT_ACTIVE


def validate_evaluation_grant(
    raw: dict[str, Any],
    *,
    grant_id: str | None,
    client_id: str,
    requested_scopes: list[str],
    quota_limit: int | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    grant = find_evaluation_grant(raw, grant_id)
    if grant is None:
        raise ValueError("evaluation_grant_required")

    if refresh_evaluation_grant_status(grant, now=now) != EVALUATION_GRANT_ACTIVE:
        raise ValueError("evaluation_grant_inactive")

    if str(grant.get("client_id") or "") != str(client_id or ""):
        raise ValueError("evaluation_grant_client_mismatch")

    allowed_scopes = {
        str(scope).strip()
        for scope in grant.get("allowed_scopes") or []
        if str(scope).strip()
    }
    requested = {str(scope).strip() for scope in requested_scopes if str(scope).strip()}
    if not requested or not requested.issubset(allowed_scopes):
        raise ValueError("evaluation_grant_scope_mismatch")

    max_requests = int(grant.get("max_requests", 0) or 0)
    if max_requests <= 0:
        raise ValueError("evaluation_grant_quota_invalid")
    if quota_limit is not None and int(quota_limit) > max_requests:
        raise ValueError("evaluation_grant_quota_exceeded")

    return grant


def key_evaluation_grant_state(
    raw: dict[str, Any],
    key: dict[str, Any],
    *,
    now: datetime | None = None,
) -> tuple[bool, str]:
    if str(key.get("category") or "") != "pilot_client":
        return True, "not_required"

    try:
        validate_evaluation_grant(
            raw,
            grant_id=str(key.get("evaluation_grant_id") or ""),
            client_id=str(key.get("client_id") or ""),
            requested_scopes=list(key.get("scopes") or []),
            quota_limit=int(key.get("quota_limit", 0) or 0),
            now=now,
        )
    except ValueError as exc:
        return False, str(exc)
    return True, "active"


def safe_evaluation_grant(grant: dict[str, Any]) -> dict[str, Any]:
    return {
        "grant_id": str(grant.get("grant_id") or ""),
        "status": str(grant.get("status") or EVALUATION_GRANT_ACTIVE),
        "client_id": str(grant.get("client_id") or ""),
        "user_id": str(grant.get("user_id") or ""),
        "issued_to": str(grant.get("issued_to") or ""),
        "purpose": str(grant.get("purpose") or ""),
        "allowed_scopes": list(grant.get("allowed_scopes") or []),
        "max_requests": int(grant.get("max_requests", 0) or 0),
        "created_at": str(grant.get("created_at") or ""),
        "expires_at": str(grant.get("expires_at") or ""),
        "revoked_at": grant.get("revoked_at"),
        "approved_by": str(grant.get("approved_by") or ""),
        "approved_by_role": str(grant.get("approved_by_role") or ""),
        "subscription_required": False,
        "production_allowed": False,
    }


__all__ = [
    "EVALUATION_GRANTS_STORAGE_KEY",
    "evaluation_grants",
    "find_evaluation_grant",
    "key_evaluation_grant_state",
    "refresh_evaluation_grant_status",
    "safe_evaluation_grant",
    "validate_evaluation_grant",
]
