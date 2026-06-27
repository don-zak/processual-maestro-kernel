from __future__ import annotations

from typing import Any


def telemetry_to_prometheus(metrics: dict[str, float], prefix: str = "processual") -> list[str]:
    lines: list[str] = []
    for key, value in metrics.items():
        safe_key = key.replace("-", "_").replace(".", "_")
        lines.append(f"# HELP {prefix}_{safe_key} {key}")
        lines.append(f"# TYPE {prefix}_{safe_key} gauge")
        lines.append(f"{prefix}_{safe_key} {value}")
    return lines


def workflow_event_to_log_entry(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_type": event.get("event_type", "unknown"),
        "workflow_id": event.get("workflow_id", ""),
        "action": event.get("action"),
        "status": event.get("status", "info"),
        "latency_ms": event.get("latency_ms", 0),
        "fate_rank": event.get("fate_rank"),
    }
