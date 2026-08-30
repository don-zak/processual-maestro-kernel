"""Quality assessment for one external-program Evaluation campaign.

Coverage answers whether every protected endpoint has succeeded at least once.
This module answers whether the evidence is repeatable and operationally useful.
Thresholds are explicit inputs so release policy can be tightened without changing
credential authority or pretending that one latency target fits every deployment.
"""

from __future__ import annotations

import math
from typing import Any

from processual_api.integrations.api_key_access_policy import list_api_key_access_policies
from processual_api.services import usage_log_store

_PUBLIC_PROBES = {
    ("GET", "/health/live"),
    ("GET", "/health/ready"),
}


def _status(record: dict[str, Any]) -> int:
    try:
        return int(record.get("status_code", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _latency(record: dict[str, Any]) -> float:
    try:
        return max(float(record.get("latency_ms", 0.0) or 0.0), 0.0)
    except (TypeError, ValueError):
        return 0.0


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil((percentile / 100.0) * len(ordered)))
    return round(ordered[min(rank - 1, len(ordered) - 1)], 3)


def assess_evaluation_campaign_quality(
    *,
    client_id: str,
    min_successes_per_endpoint: int = 3,
    max_failure_rate: float = 0.0,
    max_p95_latency_ms: float | None = None,
) -> dict[str, Any]:
    campaign = str(client_id or "").strip()
    if not campaign:
        raise ValueError("client_id is required for campaign quality assessment")
    if min_successes_per_endpoint < 1 or min_successes_per_endpoint > 100:
        raise ValueError("min_successes_per_endpoint must be between 1 and 100")
    if max_failure_rate < 0.0 or max_failure_rate > 1.0:
        raise ValueError("max_failure_rate must be between 0 and 1")
    if max_p95_latency_ms is not None and max_p95_latency_ms <= 0:
        raise ValueError("max_p95_latency_ms must be positive when provided")

    records = [
        record
        for record in usage_log_store._iter_usage_log_records()
        if str(record.get("client_id", "")) == campaign
        and record.get("entitlement_source") == "admin_evaluation_grant"
        and record.get("execution_mode") == "evaluation_runtime"
    ]

    rows: list[dict[str, Any]] = []
    for policy in list_api_key_access_policies():
        key = (policy.method, policy.path)
        if key in _PUBLIC_PROBES:
            continue
        matches = [
            record
            for record in records
            if str(record.get("method", "")).upper() == policy.method
            and str(record.get("endpoint", "")) == policy.path
        ]
        successes = [
            record
            for record in matches
            if 200 <= _status(record) < 400
            and not bool(record.get("quota_rejected", False))
        ]
        failures = len(matches) - len(successes)
        failure_rate = round(failures / len(matches), 4) if matches else 1.0
        latencies = [_latency(record) for record in successes]
        p50 = _percentile(latencies, 50)
        p95 = _percentile(latencies, 95)
        repeatability_ok = len(successes) >= min_successes_per_endpoint
        failure_rate_ok = failure_rate <= max_failure_rate
        latency_ok = max_p95_latency_ms is None or p95 <= max_p95_latency_ms
        rows.append(
            {
                "method": policy.method,
                "path": policy.path,
                "task_id": policy.task_id,
                "attempt_count": len(matches),
                "success_count": len(successes),
                "failure_count": failures,
                "failure_rate": failure_rate,
                "p50_latency_ms": p50,
                "p95_latency_ms": p95,
                "repeatability_ok": repeatability_ok,
                "failure_rate_ok": failure_rate_ok,
                "latency_ok": latency_ok,
                "quality_evidence_sufficient": (
                    repeatability_ok and failure_rate_ok and latency_ok
                ),
            }
        )

    sufficient = [row for row in rows if row["quality_evidence_sufficient"]]
    coverage = usage_log_store.summarize_evaluation_endpoint_coverage(client_id=campaign)
    return {
        "client_id": campaign,
        "protected_endpoint_count": len(rows),
        "quality_sufficient_endpoint_count": len(sufficient),
        "quality_evidence_percent": (
            round((len(sufficient) / len(rows)) * 100, 2) if rows else 100.0
        ),
        "protected_runtime_coverage_complete": coverage[
            "protected_runtime_coverage_complete"
        ],
        "repeatability_evidence_complete": len(sufficient) == len(rows),
        "quality_gate_passed": (
            coverage["protected_runtime_coverage_complete"]
            and len(sufficient) == len(rows)
        ),
        "thresholds": {
            "min_successes_per_endpoint": min_successes_per_endpoint,
            "max_failure_rate": max_failure_rate,
            "max_p95_latency_ms": max_p95_latency_ms,
        },
        "endpoints": rows,
        "public_probe_evidence_required": True,
        "cross_application_evidence_required": True,
        "raw_secret_visible": False,
        "production_allowed": False,
    }


__all__ = ["assess_evaluation_campaign_quality"]
