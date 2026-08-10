"""Canonical execution observability records and console read models."""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from threading import RLock
from typing import Any
from uuid import uuid4

_MAX_RECORDS = 500
_LOCK = RLock()
_RECORDS: deque[ExecutionObservation] = deque(maxlen=_MAX_RECORDS)


@dataclass(frozen=True, slots=True)
class ExecutionObservation:
    execution_id: str
    execution_kind: str
    task_id: str
    workflow_id: str | None
    binding_id: str | None
    provider: str | None
    status: str
    started_at: str
    completed_at: str
    duration_ms: float
    items_total: int
    items_succeeded: int
    items_failed: int
    paced: bool
    plan_reason: str | None
    failure_stage: str | None
    failure_code: str | None
    environment: str = "runtime"


def _iso(value: datetime | None = None) -> str:
    current = value or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    return current.astimezone(UTC).isoformat()


def record_execution_observation(
    *,
    execution_kind: str,
    task_id: str,
    status: str,
    duration_ms: float,
    items_total: int = 1,
    items_succeeded: int = 0,
    items_failed: int = 0,
    provider: str | None = None,
    workflow_id: str | None = None,
    binding_id: str | None = None,
    paced: bool = False,
    plan_reason: str | None = None,
    failure_stage: str | None = None,
    failure_code: str | None = None,
    execution_id: str | None = None,
    started_at: str | None = None,
    completed_at: str | None = None,
    environment: str = "runtime",
) -> dict[str, Any]:
    total = max(int(items_total), 0)
    succeeded = max(int(items_succeeded), 0)
    failed = max(int(items_failed), 0)
    if succeeded + failed > total:
        raise ValueError("execution item outcomes cannot exceed items_total")

    observation = ExecutionObservation(
        execution_id=execution_id or f"exec_{uuid4().hex}",
        execution_kind=str(execution_kind or "task").strip() or "task",
        task_id=str(task_id or "unknown").strip() or "unknown",
        workflow_id=str(workflow_id).strip() if workflow_id else None,
        binding_id=str(binding_id).strip() if binding_id else None,
        provider=str(provider).strip() if provider else None,
        status=str(status or "unknown").strip() or "unknown",
        started_at=started_at or _iso(),
        completed_at=completed_at or _iso(),
        duration_ms=max(float(duration_ms), 0.0),
        items_total=total,
        items_succeeded=succeeded,
        items_failed=failed,
        paced=bool(paced),
        plan_reason=str(plan_reason).strip() if plan_reason else None,
        failure_stage=str(failure_stage).strip() if failure_stage else None,
        failure_code=str(failure_code).strip() if failure_code else None,
        environment=str(environment or "runtime").strip() or "runtime",
    )
    with _LOCK:
        _RECORDS.append(observation)
    return asdict(observation)


def list_execution_observations(*, limit: int = 100) -> list[dict[str, Any]]:
    bounded = min(max(int(limit), 1), _MAX_RECORDS)
    with _LOCK:
        records = list(_RECORDS)[-bounded:]
    return [asdict(record) for record in reversed(records)]


def execution_observability_snapshot(*, limit: int = 50) -> dict[str, Any]:
    records = list_execution_observations(limit=_MAX_RECORDS)
    total = len(records)
    completed = sum(
        1
        for item in records
        if item["status"] in {"success", "partial_error", "failed", "saturated"}
    )
    succeeded = sum(1 for item in records if item["status"] == "success")
    failed = sum(1 for item in records if item["status"] in {"failed", "saturated"})
    partial = sum(1 for item in records if item["status"] == "partial_error")
    durations = [float(item["duration_ms"]) for item in records]
    average_latency_ms = round(sum(durations) / len(durations), 2) if durations else 0.0

    by_task = Counter(item["task_id"] for item in records)
    by_status = Counter(item["status"] for item in records)
    by_provider = Counter(item["provider"] or "none" for item in records)
    by_execution_kind = Counter(item["execution_kind"] for item in records)
    by_environment = Counter(item["environment"] for item in records)
    item_totals = {
        "total": sum(int(item["items_total"]) for item in records),
        "succeeded": sum(int(item["items_succeeded"]) for item in records),
        "failed": sum(int(item["items_failed"]) for item in records),
    }

    success_rate = round((succeeded / completed) * 100.0, 2) if completed else 0.0
    recent = records[: min(max(int(limit), 1), 100)]
    return {
        "status": "ready",
        "source_of_truth": "canonical_execution_records",
        "record_count": total,
        "summary": {
            "executions_total": total,
            "executions_completed": completed,
            "executions_succeeded": succeeded,
            "executions_failed": failed,
            "executions_partial_error": partial,
            "success_rate_percent": success_rate,
            "average_latency_ms": average_latency_ms,
            "items_total": item_totals["total"],
            "items_succeeded": item_totals["succeeded"],
            "items_failed": item_totals["failed"],
        },
        "by_status": dict(sorted(by_status.items())),
        "by_task": dict(sorted(by_task.items())),
        "by_provider": dict(sorted(by_provider.items())),
        "by_execution_kind": dict(sorted(by_execution_kind.items())),
        "by_environment": dict(sorted(by_environment.items())),
        "recent_executions": recent,
        "reconciliation": {
            "aggregate_record_count": total,
            "recent_count": len(recent),
            "aggregates_derived_from_records": True,
        },
    }


def clear_execution_observations_for_tests() -> None:
    with _LOCK:
        _RECORDS.clear()


__all__ = [
    "ExecutionObservation",
    "clear_execution_observations_for_tests",
    "execution_observability_snapshot",
    "list_execution_observations",
    "record_execution_observation",
]
