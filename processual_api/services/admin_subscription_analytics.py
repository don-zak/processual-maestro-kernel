from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from processual_api.billing.usage_pricing import monthly_unit_allowance, normalize_plan_id

PLAN_BUCKETS = (
    "developer",
    "starter",
    "business",
    "enterprise",
    "enterprise_integration",
    "unknown",
)

SUBSCRIPTION_BUCKETS = (
    "active",
    "trial",
    "past_due",
    "cancelled",
    "expired",
)

FORBIDDEN_MARKERS = (
    "api_key",
    "encrypted_key",
    "provider_secret",
    "raw_key",
    "token",
    "password",
)


def _safe_int(value: Any) -> int:
    try:
        return max(0, int(float(value or 0)))
    except (TypeError, ValueError):
        return 0


def _read_json(path: Path, fallback: Any) -> Any:
    try:
        if not path.exists():
            return fallback
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def _iter_dict_records(value: Any):
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                yield item
        return

    if not isinstance(value, dict):
        return

    for key in (
        "subscriptions",
        "items",
        "records",
        "api_keys",
        "keys",
        "clients",
        "data",
    ):
        nested = value.get(key)
        if isinstance(nested, list | dict):
            yield from _iter_dict_records(nested)
            return

    dict_values = [item for item in value.values() if isinstance(item, dict)]
    if dict_values and len(dict_values) == len(value):
        for item in dict_values:
            yield item
        return

    yield value


def _first_text(record: dict, *keys: str) -> str:
    for key in keys:
        value = record.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _nested_text(record: dict, parent: str, *keys: str) -> str:
    nested = record.get(parent)
    if not isinstance(nested, dict):
        return ""
    return _first_text(nested, *keys)


def _normalize_plan(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "unknown"
    try:
        normalized = normalize_plan_id(raw)
    except (TypeError, ValueError):
        normalized = raw.lower().strip()
    return normalized if normalized in PLAN_BUCKETS else "unknown"


def _plan_allowance(plan_id: str) -> int:
    if not plan_id or plan_id == "unknown":
        return 0
    try:
        return _safe_int(monthly_unit_allowance(plan_id))
    except (KeyError, TypeError, ValueError):
        return 0


def _subscription_status(value: Any) -> str:
    status = str(value or "").strip().lower()
    if status in {"trial", "trialing"}:
        return "trial"
    if status in {"cancelled", "canceled"}:
        return "cancelled"
    if status in SUBSCRIPTION_BUCKETS:
        return status
    return "active" if not status else "expired"


def _client_status(value: Any, plan_id: str) -> str:
    status = str(value or "").strip().lower()
    if "pilot" in str(plan_id or "").lower():
        return "pilot"
    if status in {"suspended", "disabled", "blocked"}:
        return "suspended"
    if status in {"expired", "cancelled", "canceled"}:
        return "expired"
    return "active"


def _api_key_is_revoked(record: dict) -> bool:
    status = str(record.get("status") or "").strip().lower()
    if status in {"revoked", "disabled", "inactive", "expired"}:
        return True
    if record.get("revoked") is True:
        return True
    if record.get("active") is False:
        return True
    return bool(record.get("revoked_at") or record.get("disabled_at"))


def _api_key_profile(record: dict) -> str:
    raw = " ".join(
        str(record.get(key) or "")
        for key in ("profile", "category", "kind", "role", "label", "name")
    ).lower()
    if "billing" in raw:
        return "billing_keys"
    if "ops" in raw or "operation" in raw or "admin" in raw:
        return "ops_keys"
    return "client_keys"


def _record_units(record: dict) -> int:
    for key in (
        "units",
        "maestro_units",
        "usage_units",
        "billable_units",
        "unit_cost",
        "cost",
    ):
        units = _safe_int(record.get(key))
        if units:
            return units
    return 0


def _record_client_id(record: dict) -> str:
    return _first_text(
        record,
        "client_id",
        "user_id",
        "customer_id",
        "account_id",
        "sub",
    )


def _record_plan_id(record: dict) -> str:
    return (
        _first_text(record, "plan_id", "plan", "tier")
        or _nested_text(record, "plan", "plan_id", "id")
        or _nested_text(record, "subscription", "plan_id", "plan")
        or "unknown"
    )


def _record_timestamp(record: dict) -> str:
    return _first_text(
        record,
        "timestamp",
        "created_at",
        "used_at",
        "logged_at",
        "at",
    )


def _is_current_period(record: dict, current_period: str) -> bool:
    timestamp = _record_timestamp(record)
    if not timestamp:
        return True
    return timestamp.startswith(current_period)


def _read_usage_records(data_dir: Path):
    path = data_dir / "usage_logs.jsonl"
    if not path.exists():
        return

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return

    for line in lines:
        raw = line.strip()
        if not raw:
            continue
        try:
            record = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            yield record


def _empty_summary() -> dict:
    return {
        "clients": {
            "total": 0,
            "active": 0,
            "pilot": 0,
            "suspended": 0,
            "expired": 0,
        },
        "plans": {bucket: 0 for bucket in PLAN_BUCKETS},
        "usage": {
            "monthly_units_used": 0,
            "monthly_units_allowance": 0,
            "near_quota_limit": 0,
            "quota_exceeded": 0,
        },
        "api_keys": {
            "active": 0,
            "revoked": 0,
            "client_keys": 0,
            "billing_keys": 0,
            "ops_keys": 0,
        },
        "subscriptions": {bucket: 0 for bucket in SUBSCRIPTION_BUCKETS},
        "risk": [],
    }


def _append_risk(
    risk: list[dict],
    *,
    severity: str,
    kind: str,
    client_id: str,
    plan_id: str,
    used: int = 0,
    limit: int = 0,
    message: str,
) -> None:
    risk.append(
        {
            "severity": severity,
            "kind": kind,
            "client_id": str(client_id or ""),
            "plan_id": _normalize_plan(plan_id),
            "used": _safe_int(used),
            "limit": _safe_int(limit),
            "message": str(message or "")[:240],
        }
    )



def _assert_no_forbidden_values(value: Any) -> None:
    if isinstance(value, dict):
        for nested in value.values():
            _assert_no_forbidden_values(nested)
        return

    if isinstance(value, list):
        for nested in value:
            _assert_no_forbidden_values(nested)
        return

    if value is None:
        return

    text_value = str(value).lower()
    if any(marker in text_value for marker in FORBIDDEN_MARKERS):
        raise RuntimeError(
            "Admin subscription analytics payload contains a forbidden value."
        )

def build_admin_subscription_analytics(data_dir: str | Path | None = None) -> dict:
    base_dir = Path(data_dir or "processual_api/data")
    summary = _empty_summary()

    client_ids: set[str] = set()
    client_plans: dict[str, str] = {}
    client_statuses: dict[str, str] = {}
    client_usage: defaultdict[str, int] = defaultdict(int)
    client_limits: dict[str, int] = {}
    client_key_counts: defaultdict[str, dict[str, int]] = defaultdict(
        lambda: {"active": 0, "revoked": 0}
    )

    for settings_path in sorted(base_dir.glob("settings_*.json")):
        raw = _read_json(settings_path, {})
        if not isinstance(raw, dict):
            continue

        fallback_client_id = settings_path.stem.replace("settings_", "", 1)
        client_id = (
            _record_client_id(raw)
            or _nested_text(raw, "client", "client_id", "user_id", "id")
            or fallback_client_id
        )
        if not client_id:
            continue

        plan_id = _normalize_plan(_record_plan_id(raw))
        status = _client_status(
            _first_text(raw, "status", "account_status", "client_status")
            or _nested_text(raw, "subscription", "status"),
            plan_id,
        )

        client_ids.add(client_id)
        client_plans.setdefault(client_id, plan_id)
        client_statuses.setdefault(client_id, status)

        api_key_records = raw.get("api_keys") or raw.get("keys") or []
        for key_record in _iter_dict_records(api_key_records):
            if _api_key_is_revoked(key_record):
                summary["api_keys"]["revoked"] += 1
                client_key_counts[client_id]["revoked"] += 1
            else:
                summary["api_keys"]["active"] += 1
                client_key_counts[client_id]["active"] += 1
            summary["api_keys"][_api_key_profile(key_record)] += 1

    subscriptions_path = base_dir / "subscriptions.json"
    subscriptions_raw = _read_json(subscriptions_path, [])
    for subscription in _iter_dict_records(subscriptions_raw):
        client_id = _record_client_id(subscription)
        plan_id = _normalize_plan(_record_plan_id(subscription))
        raw_subscription_status = _first_text(
            subscription,
            "status",
            "subscription_status",
            "stage",
        ).lower()
        status = _subscription_status(raw_subscription_status)

        summary["subscriptions"][status] += 1

        if client_id:
            client_ids.add(client_id)
            client_plans.setdefault(client_id, plan_id)
            client_statuses[client_id] = _client_status(status, plan_id)

        if status == "past_due":
            _append_risk(
                summary["risk"],
                severity="warning",
                kind="subscription_past_due",
                client_id=client_id,
                plan_id=plan_id,
                message="Subscription payment is past due.",
            )
        if status in {"cancelled", "expired"}:
            _append_risk(
                summary["risk"],
                severity="danger",
                kind=f"subscription_{status}",
                client_id=client_id,
                plan_id=plan_id,
                message="Subscription is not active.",
            )

        if raw_subscription_status in {"suspended", "disabled", "blocked"}:
            _append_risk(
                summary["risk"],
                severity="danger",
                kind="subscription_suspended",
                client_id=client_id,
                plan_id=plan_id,
                message="Subscription is suspended or disabled.",
            )


    current_period = datetime.now(UTC).strftime("%Y-%m")
    for record in _read_usage_records(base_dir) or []:
        if not _is_current_period(record, current_period):
            continue

        client_id = _record_client_id(record)
        if not client_id:
            continue

        plan_id = _normalize_plan(_record_plan_id(record))
        units = _record_units(record)
        quota_limit = _safe_int(
            record.get("quota_limit")
            or record.get("allowance_units")
            or record.get("monthly_included_units")
        )

        client_ids.add(client_id)
        client_usage[client_id] += units
        summary["usage"]["monthly_units_used"] += units

        if plan_id != "unknown":
            client_plans.setdefault(client_id, plan_id)
        if quota_limit:
            client_limits[client_id] = max(client_limits.get(client_id, 0), quota_limit)

    for client_id in sorted(client_ids):
        plan_id = client_plans.get(client_id, "unknown")
        status = client_statuses.get(client_id, "active")

        summary["clients"]["total"] += 1
        summary["clients"][status] = summary["clients"].get(status, 0) + 1
        summary["plans"][plan_id if plan_id in PLAN_BUCKETS else "unknown"] += 1

        used = client_usage.get(client_id, 0)
        limit = client_limits.get(client_id) or _plan_allowance(plan_id)
        summary["usage"]["monthly_units_allowance"] += limit

        active_keys = client_key_counts.get(client_id, {}).get("active", 0)
        revoked_keys = client_key_counts.get(client_id, {}).get("revoked", 0)

        if active_keys == 0 and revoked_keys > 0:
            _append_risk(
                summary["risk"],
                severity="warning",
                kind="inactive_keys",
                client_id=client_id,
                plan_id=plan_id,
                used=used,
                limit=limit,
                message="Client has revoked or inactive keys and no active key.",
            )

        if plan_id == "unknown":
            _append_risk(
                summary["risk"],
                severity="warning",
                kind="unknown_plan",
                client_id=client_id,
                plan_id=plan_id,
                used=used,
                limit=limit,
                message="Client plan is unknown, so allowance cannot be calculated.",
            )

        if used > 0 and limit <= 0:
            _append_risk(
                summary["risk"],
                severity="warning",
                kind="usage_without_allowance",
                client_id=client_id,
                plan_id=plan_id,
                used=used,
                limit=limit,
                message="Client has usage but no known allowance.",
            )

        if limit > 0 and used >= limit:
            summary["usage"]["quota_exceeded"] += 1
            _append_risk(
                summary["risk"],
                severity="danger",
                kind="quota_exceeded",
                client_id=client_id,
                plan_id=plan_id,
                used=used,
                limit=limit,
                message="Client has exceeded the monthly allowance.",
            )
        elif limit > 0 and used / limit >= 0.8:
            summary["usage"]["near_quota_limit"] += 1
            _append_risk(
                summary["risk"],
                severity="warning",
                kind="near_quota_limit",
                client_id=client_id,
                plan_id=plan_id,
                used=used,
                limit=limit,
                message="Client is above 80% of the monthly allowance.",
            )

    summary["risk"].sort(
        key=lambda item: (
            {"danger": 0, "warning": 1, "info": 2}.get(item["severity"], 3),
            item["kind"],
            item["client_id"],
        )
    )
    summary["risk"] = summary["risk"][:25]
    _assert_no_forbidden_values(summary)

    return summary
