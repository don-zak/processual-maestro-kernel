"""Simple transitional API key quota store.

KEY-04 starts with JSON-backed quota enforcement for dynamic API keys.
This is intentionally small and local-first before PostgreSQL / billing plans.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from .plan_store import get_plan_policy, quota_limit_for_plan, resolve_plan_id


DATA_DIR = Path(__file__).resolve().parents[1] / "data"

DEFAULT_API_KEY_QUOTA_LIMIT = int(
    os.environ.get("PMK_DEFAULT_API_KEY_QUOTA_LIMIT", "50")
)

COUNTED_ENDPOINTS: set[tuple[str, str]] = {
    ("POST", "/cgt/govern"),
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_endpoint(endpoint: str) -> str:
    value = endpoint.strip() or "/"
    if len(value) > 1:
        value = value.rstrip("/")
    return value


def is_quota_counted(method: str, endpoint: str) -> bool:
    """Return True only for endpoints that should consume commercial quota."""
    return (method.upper(), _normalize_endpoint(endpoint)) in COUNTED_ENDPOINTS


def _iter_settings_files() -> list[Path]:
    if not DATA_DIR.exists():
        return []
    return sorted(DATA_DIR.glob("settings_*.json"))


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Invalid settings JSON: {path.name}",
        ) from exc


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp_path.replace(path)


def _as_int(value: Any, default: int) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def consume_quota(
    current_user: dict[str, Any],
    *,
    method: str,
    endpoint: str,
    quota_scope: str = "evaluation",
    amount: int = 1,
) -> dict[str, Any]:
    """Consume quota for counted API-key requests.

    Non-API-key users and non-counted endpoints pass through unchanged.
    """

    if current_user.get("auth_method") != "api_key":
        return current_user

    if not is_quota_counted(method, endpoint):
        return current_user

    api_key_id = current_user.get("api_key_id")
    if not api_key_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing API key quota identity",
        )

    now = _now_iso()

    for path in _iter_settings_files():
        raw = _load_json(path)
        keys = raw.get("api_keys", [])

        if not isinstance(keys, list):
            continue

        for key in keys:
            if not isinstance(key, dict):
                continue

            if key.get("id") != api_key_id:
                continue

            subscription = raw.get("subscription", {})
            plan_id = resolve_plan_id(
                key.get("plan_id")
                or key.get("plan")
                or subscription.get("plan_id")
                or subscription.get("plan")
                or "Starter"
            )

            existing_policy = key.get("quota_policy", {})
            policy_source = (
                existing_policy.get("source")
                if isinstance(existing_policy, dict)
                else None
            )
            manual_limit = key.get("quota_limit_override")

            if policy_source == "manual" or manual_limit is not None:
                quota_limit = _as_int(
                    manual_limit if manual_limit is not None else key.get("quota_limit"),
                    DEFAULT_API_KEY_QUOTA_LIMIT,
                )
            else:
                quota_limit = quota_limit_for_plan(
                    plan_id,
                    quota_scope,
                    DEFAULT_API_KEY_QUOTA_LIMIT,
                )
                key["plan_id"] = plan_id
                key["quota_policy"] = get_plan_policy(plan_id)

            quota_used = _as_int(key.get("quota_used"), 0)

            key["quota_limit"] = quota_limit
            key["quota_scope"] = key.get("quota_scope") or quota_scope
            if quota_limit >= 0 and quota_used + amount > quota_limit:
                key["quota_last_rejected_at"] = now
                key["quota_rejected_count"] = (
                    _as_int(key.get("quota_rejected_count"), 0) + 1
                )
                raw["api_keys"] = keys
                _write_json(path, raw)

                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "error": "quota_exceeded",
                        "quota_scope": quota_scope,
                        "quota_limit": quota_limit,
                        "quota_used": quota_used,
                    },
                )

            quota_used += amount
            key["quota_used"] = quota_used
            key["quota_last_used_at"] = now
            key["quota_scope"] = key.get("quota_scope") or quota_scope

            raw["api_keys"] = keys
            _write_json(path, raw)

            updated_user = dict(current_user)
            updated_user["quota"] = {
                "scope": quota_scope,
                "plan_id": key.get("plan_id"),
                "limit": quota_limit,
                "used": quota_used,
                "remaining": max(quota_limit - quota_used, 0)
                if quota_limit >= 0
                else None,
            }
            return updated_user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="API key quota record not found",
    )