from __future__ import annotations

import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from processual_api.billing.maestro_units import MAESTRO_UNIT_METRIC
from processual_api.billing.usage_pricing import monthly_unit_allowance, pricing_decision
from processual_api.integrations.api_key_access_policy import list_api_key_access_policies

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_USAGE_LOG_PATH = _DATA_DIR / "usage_logs.jsonl"
_RAW_API_KEY_PATTERN = re.compile(r"pmk_[A-Za-z0-9_-]+")
_PUBLIC_EVALUATION_PROBES = {
    ("GET", "/health/live"),
    ("GET", "/health/ready"),
}


def _as_int_or_none(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def sanitize_usage_endpoint(endpoint: str) -> str:
    return _RAW_API_KEY_PATTERN.sub("pmk_[redacted]", endpoint)


def append_usage_log(record: dict[str, Any]) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    endpoint = sanitize_usage_endpoint(str(record.get("endpoint", "")))
    pricing_record = pricing_decision(endpoint).to_usage_record()

    quota_after = _as_int_or_none(record.get("quota_after", record.get("quota_used")))
    quota_requested = _as_int_or_none(record.get("quota_requested"))
    if quota_requested is None:
        quota_requested = _as_int_or_none(record.get("units_charged")) or int(pricing_record["units_charged"])

    quota_before = _as_int_or_none(record.get("quota_before"))
    if quota_before is None and quota_after is not None:
        quota_before = max(quota_after - quota_requested, 0)

    clean_record = {
        "created_at": record.get("created_at") or datetime.now(UTC).isoformat(),
        "request_id": record.get("request_id", ""),
        "client_id": record.get("client_id", ""),
        "user_id": record.get("user_id", ""),
        "api_key_id": record.get("api_key_id", ""),
        "api_key_prefix": record.get("api_key_prefix", ""),
        "auth_method": record.get("auth_method", ""),
        "session_type": record.get("session_type", ""),
        "method": record.get("method", ""),
        "endpoint": endpoint,
        "status_code": record.get("status_code", 0),
        "latency_ms": record.get("latency_ms", 0),
        "role": record.get("role", ""),
        "pricing_version": record.get("pricing_version") or pricing_record["pricing_version"],
        "billing_policy": record.get("billing_policy") or pricing_record["billing_policy"],
        "billing_scope": record.get("billing_scope") or pricing_record["billing_scope"],
        "provider_cost_included": bool(record.get("provider_cost_included", pricing_record["provider_cost_included"])),
        "endpoint_class": record.get("endpoint_class") or pricing_record["endpoint_class"],
        "units_charged": int(record.get("units_charged", pricing_record["units_charged"]) or 0),
        "quota_scope": record.get("quota_scope", ""),
        "quota_metric": record.get("quota_metric") or MAESTRO_UNIT_METRIC,
        "quota_period": record.get("quota_period", ""),
        "quota_limit": _as_int_or_none(record.get("quota_limit")),
        "quota_used": quota_after,
        "quota_requested": quota_requested,
        "quota_remaining": _as_int_or_none(record.get("quota_remaining")),
        "quota_before": quota_before,
        "quota_after": quota_after,
        "plan_id": record.get("plan_id", ""),
        "quota_rejected": bool(record.get("quota_rejected", False)),
        "entitlement_source": record.get("entitlement_source", ""),
        "evaluation_grant_id": record.get("evaluation_grant_id", ""),
        "execution_mode": record.get("execution_mode", ""),
        "real_runtime_execution": bool(record.get("real_runtime_execution", False)),
        "endpoint_authority_source": record.get("endpoint_authority_source", ""),
        "task_authority_source": record.get("task_authority_source", ""),
        "evaluation_request_limit": _as_int_or_none(record.get("evaluation_request_limit")),
        "evaluation_request_used": _as_int_or_none(record.get("evaluation_request_used")),
        "evaluation_request_remaining": _as_int_or_none(record.get("evaluation_request_remaining")),
        "production_allowed": bool(record.get("production_allowed", False)),
    }

    with _USAGE_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(clean_record, ensure_ascii=False) + "\n")


def _safe_int(value: Any, default: int = 0) -> int:
    parsed = _as_int_or_none(value)
    return default if parsed is None else parsed


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _iter_usage_log_records() -> list[dict[str, Any]]:
    try:
        lines = _USAGE_LOG_PATH.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    records: list[dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            records.append(record)
    return records


def _quota_status(*, quota_limit: int | None, quota_remaining: int | None, rejected_requests: int) -> str:
    if quota_remaining is not None:
        if quota_remaining <= 0:
            return "exhausted"
        if rejected_requests > 0:
            return "warning"
        if quota_limit and quota_limit > 0:
            warning_threshold = max(1, int(quota_limit * 0.2))
            if quota_remaining <= warning_threshold:
                return "warning"
    if rejected_requests > 0:
        return "warning"
    return "ok"


def summarize_usage_logs(
    *,
    client_id: str | None = None,
    api_key_id: str | None = None,
    latest_limit: int = 10,
) -> dict[str, Any]:
    records = _iter_usage_log_records()
    if client_id:
        records = [record for record in records if str(record.get("client_id", "")) == client_id]
    if api_key_id:
        records = [record for record in records if str(record.get("api_key_id", "")) == api_key_id]

    endpoint_class_counts: Counter[str] = Counter()
    status_code_counts: Counter[str] = Counter()
    endpoint_counts: Counter[str] = Counter()
    total_units = successful_units = rejected_units = rejected_requests = successful_requests = 0
    latest_quota_limit: int | None = None
    latest_quota_used: int | None = None
    latest_quota_remaining: int | None = None
    latest_plan_id = ""
    latest_quota_period = ""
    latest_quota_metric = MAESTRO_UNIT_METRIC

    for record in records:
        units = _safe_int(record.get("units_charged"), 0)
        total_units += units
        status_code = _safe_int(record.get("status_code"), 0)
        quota_rejected = bool(record.get("quota_rejected", False))
        is_success = 200 <= status_code < 400 and not quota_rejected
        if is_success:
            successful_requests += 1
            successful_units += units
        if quota_rejected or status_code == 429:
            rejected_requests += 1
            rejected_units += units

        endpoint_class = str(record.get("endpoint_class", "") or "unknown")
        endpoint_class_counts[endpoint_class] += 1
        endpoint = str(record.get("endpoint", "") or "unknown")
        endpoint_counts[endpoint] += 1
        status_code_counts[str(status_code)] += 1

        quota_limit = _as_int_or_none(record.get("quota_limit"))
        quota_used = _as_int_or_none(record.get("quota_after", record.get("quota_used")))
        quota_remaining = _as_int_or_none(record.get("quota_remaining"))
        if quota_limit is not None:
            latest_quota_limit = quota_limit
        if quota_used is not None:
            latest_quota_used = quota_used
        if quota_remaining is not None:
            latest_quota_remaining = quota_remaining
        plan_id = str(record.get("plan_id", "") or "")
        if plan_id:
            latest_plan_id = plan_id
        quota_period = str(record.get("quota_period", "") or "")
        if quota_period:
            latest_quota_period = quota_period
        quota_metric = str(record.get("quota_metric", "") or "")
        if quota_metric:
            latest_quota_metric = quota_metric

    bounded_limit = max(min(int(latest_limit or 10), 50), 0)
    latest_events = list(reversed(records[-bounded_limit:])) if bounded_limit else []
    latest_usage_at = str(latest_events[0].get("created_at", "") or "") if latest_events else ""
    current_period = latest_quota_period or (latest_usage_at[:7] if latest_usage_at else "")
    monthly_included_units = monthly_unit_allowance(latest_plan_id)
    usage_quota_status = _quota_status(
        quota_limit=latest_quota_limit,
        quota_remaining=latest_quota_remaining,
        rejected_requests=rejected_requests,
    )

    avg_latency_ms = 0.0
    if records:
        avg_latency_ms = round(sum(_safe_float(record.get("latency_ms"), 0.0) for record in records) / len(records), 3)

    return {
        "client_id": client_id or "",
        "api_key_id": api_key_id or "",
        "total_events": len(records),
        "successful_requests": successful_requests,
        "rejected_requests": rejected_requests,
        "total_units": total_units,
        "successful_units": successful_units,
        "rejected_units": rejected_units,
        "quota_metric": latest_quota_metric,
        "quota_limit": latest_quota_limit,
        "quota_used": latest_quota_used,
        "quota_remaining": latest_quota_remaining,
        "plan_id": latest_plan_id,
        "monthly_included_units": monthly_included_units,
        "allowance_units": monthly_included_units,
        "current_period": current_period,
        "latest_usage_at": latest_usage_at,
        "quota_status": usage_quota_status,
        "billing_policy": "byok",
        "provider_cost_included": False,
        "by_endpoint_class": dict(sorted(endpoint_class_counts.items())),
        "by_status_code": dict(sorted(status_code_counts.items())),
        "top_endpoints": dict(endpoint_counts.most_common(10)),
        "avg_latency_ms": avg_latency_ms,
        "latest_events": latest_events,
    }


def summarize_evaluation_endpoint_coverage(
    *,
    client_id: str | None = None,
    evaluation_grant_id: str | None = None,
    api_key_id: str | None = None,
) -> dict[str, Any]:
    records = [
        record
        for record in _iter_usage_log_records()
        if record.get("entitlement_source") == "admin_evaluation_grant"
        and record.get("execution_mode") == "evaluation_runtime"
    ]
    if client_id:
        records = [
            record
            for record in records
            if str(record.get("client_id", "")) == client_id
        ]
    if evaluation_grant_id:
        records = [
            record
            for record in records
            if str(record.get("evaluation_grant_id", "")) == evaluation_grant_id
        ]
    if api_key_id:
        records = [
            record
            for record in records
            if str(record.get("api_key_id", "")) == api_key_id
        ]

    endpoints: list[dict[str, Any]] = []
    protected_total = protected_observed = 0
    for policy in list_api_key_access_policies():
        key = (policy.method, policy.path)
        public_probe = key in _PUBLIC_EVALUATION_PROBES
        if not public_probe:
            protected_total += 1
        matches = [
            record
            for record in records
            if str(record.get("method", "")).upper() == policy.method
            and str(record.get("endpoint", "")) == policy.path
        ]
        successes = [
            record
            for record in matches
            if 200 <= _safe_int(record.get("status_code"), 0) < 400
            and not bool(record.get("quota_rejected", False))
        ]
        if successes and not public_probe:
            protected_observed += 1
        avg_latency_ms = 0.0
        if matches:
            avg_latency_ms = round(
                sum(_safe_float(record.get("latency_ms"), 0.0) for record in matches)
                / len(matches),
                3,
            )
        endpoints.append(
            {
                "method": policy.method,
                "path": policy.path,
                "task_id": policy.task_id,
                "capability": policy.capability,
                "proof_mode": (
                    "public_availability_probe"
                    if public_probe
                    else "evaluation_key_runtime"
                ),
                "attempt_count": len(matches),
                "success_count": len(successes),
                "failure_count": len(matches) - len(successes),
                "observed_success": bool(successes),
                "avg_latency_ms": avg_latency_ms,
                "requires_external_public_probe": public_probe,
                "production_allowed": False,
            }
        )

    protected_percent = (
        round((protected_observed / protected_total) * 100, 2)
        if protected_total
        else 100.0
    )
    return {
        "client_id": client_id or "",
        "evaluation_grant_id": evaluation_grant_id or "",
        "api_key_id": api_key_id or "",
        "policy_endpoint_count": len(endpoints),
        "public_probe_count": len(_PUBLIC_EVALUATION_PROBES),
        "protected_endpoint_count": protected_total,
        "protected_endpoint_success_count": protected_observed,
        "protected_coverage_percent": protected_percent,
        "protected_runtime_coverage_complete": protected_observed == protected_total,
        "full_campaign_requires_public_probe_evidence": True,
        "campaign_correlation": "client_id",
        "endpoints": endpoints,
        "raw_secret_visible": False,
        "production_allowed": False,
    }
