"""Transitional API-key Maestro Unit quota store.

Maestro Units are the sole commercial consumption authority. Legacy JSON storage
is retained, while unit pricing, plan entitlements, and monthly periods are
resolved through centralized commercial contracts.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status

from processual_api.billing.maestro_units import (
    MAESTRO_UNIT_METRIC,
    MAESTRO_UNIT_RULES,
    is_maestro_metered_endpoint,
    maestro_capability_for_endpoint,
)
from processual_api.billing.plan_entitlement_gate import (
    PlanEntitlementDeniedError,
    require_plan_entitlement,
)

from .plan_store import get_plan_policy, quota_limit_for_plan, resolve_plan_id

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DEFAULT_API_KEY_QUOTA_LIMIT = int(os.environ.get("PMK_DEFAULT_API_KEY_QUOTA_LIMIT", "50"))

COUNTED_ENDPOINT_CAPABILITIES: dict[tuple[str, str], str] = {
    ("POST", path): rule.capability_code
    for path, rule in MAESTRO_UNIT_RULES.items()
    if rule.capability_code is not None and not rule.free
}
COUNTED_ENDPOINTS: set[tuple[str, str]] = set(COUNTED_ENDPOINT_CAPABILITIES)


def _now() -> datetime:
    return datetime.now(UTC)


def _now_iso() -> str:
    return _now().isoformat()


def _period_id(moment: datetime | None = None) -> str:
    value = moment or _now()
    return value.strftime("%Y-%m")


def _normalize_endpoint(endpoint: str) -> str:
    value = endpoint.strip() or "/"
    if len(value) > 1:
        value = value.rstrip("/")
    return value


def is_quota_counted(method: str, endpoint: str) -> bool:
    del method
    return is_maestro_metered_endpoint(_normalize_endpoint(endpoint))


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
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Invalid settings JSON: {path.name}") from exc


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def _as_int(value: Any, default: int) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _enforce_authoritative_capability(
    *,
    plan_id: str,
    policy: dict[str, Any],
    endpoint: str,
    method: str | None = None,
) -> None:
    # method is intentionally accepted for backwards-compatible direct callers;
    # endpoint capability authority is method-agnostic in the Maestro contract.
    del method
    if policy.get("source") != "authoritative_fulfillment_catalog":
        return
    capability_code = maestro_capability_for_endpoint(endpoint)
    if capability_code is None:
        return
    try:
        require_plan_entitlement(plan_id, capability_code)
    except PlanEntitlementDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "plan_capability_denied",
                "plan_id": plan_id,
                "capability_code": capability_code,
                "maestro_unit_metric": MAESTRO_UNIT_METRIC,
            },
        ) from exc


def _reset_monthly_period_if_needed(key: dict[str, Any], *, now: datetime) -> None:
    current_period = _period_id(now)
    stored_period = str(key.get("quota_period") or "")
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()

    if not stored_period:
        key["quota_period"] = current_period
        key["quota_period_started_at"] = period_start
        return

    if stored_period == current_period:
        return

    key["quota_period"] = current_period
    key["quota_used"] = 0
    key["quota_rejected_count"] = 0
    key["quota_period_started_at"] = period_start


def consume_quota(
    current_user: dict[str, Any],
    *,
    method: str,
    endpoint: str,
    quota_scope: str = "evaluation",
    amount: int = 1,
) -> dict[str, Any]:
    if current_user.get("auth_method") != "api_key":
        return current_user
    if not is_quota_counted(method, endpoint):
        return current_user
    if amount <= 0:
        raise ValueError("Maestro Unit consumption amount must be positive")

    api_key_id = current_user.get("api_key_id")
    if not api_key_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing API key quota identity")

    now_dt = _now()
    now = now_dt.isoformat()
    for path in _iter_settings_files():
        raw = _load_json(path)
        keys = raw.get("api_keys", [])
        if not isinstance(keys, list):
            continue

        for key in keys:
            if not isinstance(key, dict) or key.get("id") != api_key_id:
                continue

            subscription = raw.get("subscription", {})
            if not isinstance(subscription, dict):
                subscription = {}
            raw_plan_id = key.get("plan_id") or key.get("plan") or subscription.get("plan_id") or subscription.get("plan")
            if not isinstance(raw_plan_id, str) or not raw_plan_id.strip():
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="API key subscription plan authority is missing.")
            try:
                plan_id = resolve_plan_id(raw_plan_id)
            except KeyError as exc:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="API key subscription plan is not recognized.") from exc

            existing_policy = key.get("quota_policy", {})
            policy_source = existing_policy.get("source") if isinstance(existing_policy, dict) else None
            manual_limit = key.get("quota_limit_override")
            if policy_source == "manual" or manual_limit is not None:
                quota_limit = _as_int(manual_limit if manual_limit is not None else key.get("quota_limit"), DEFAULT_API_KEY_QUOTA_LIMIT)
                effective_policy = existing_policy if isinstance(existing_policy, dict) else {"source": "manual"}
            else:
                quota_limit = quota_limit_for_plan(plan_id, quota_scope, DEFAULT_API_KEY_QUOTA_LIMIT)
                effective_policy = get_plan_policy(plan_id)
                key["plan_id"] = plan_id
                key["quota_policy"] = effective_policy

            _enforce_authoritative_capability(
                plan_id=plan_id,
                policy=effective_policy,
                method=method,
                endpoint=endpoint,
            )
            _reset_monthly_period_if_needed(key, now=now_dt)
            quota_used = _as_int(key.get("quota_used"), 0)

            key["quota_limit"] = quota_limit
            key["quota_scope"] = quota_scope
            key["quota_metric"] = MAESTRO_UNIT_METRIC
            if quota_limit >= 0 and quota_used + amount > quota_limit:
                key["quota_last_rejected_at"] = now
                key["quota_rejected_count"] = _as_int(key.get("quota_rejected_count"), 0) + 1
                raw["api_keys"] = keys
                _write_json(path, raw)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "error": "quota_exceeded",
                        "quota_scope": quota_scope,
                        "quota_metric": MAESTRO_UNIT_METRIC,
                        "quota_period": key["quota_period"],
                        "plan_id": plan_id,
                        "quota_limit": quota_limit,
                        "quota_used": quota_used,
                        "quota_requested": amount,
                        "quota_remaining": max(quota_limit - quota_used, 0),
                    },
                )

            quota_used += amount
            key["quota_used"] = quota_used
            key["quota_last_used_at"] = now
            raw["api_keys"] = keys
            _write_json(path, raw)

            updated_user = dict(current_user)
            updated_user["quota"] = {
                "scope": quota_scope,
                "metric": MAESTRO_UNIT_METRIC,
                "period": key["quota_period"],
                "plan_id": key.get("plan_id") or plan_id,
                "limit": quota_limit,
                "used": quota_used,
                "requested": amount,
                "remaining": max(quota_limit - quota_used, 0) if quota_limit >= 0 else None,
            }
            return updated_user

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="API key quota record not found")
