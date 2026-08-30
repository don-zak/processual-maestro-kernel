"""Fail-closed idempotency reservations for non-READ Evaluation executions."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

EVALUATION_IDEMPOTENCY_STORAGE_KEY = "evaluation_runtime_idempotency_v1"


def _digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def execution_request_sha256(*, task_id: str, binding_id: str, task_input: Mapping[str, Any]) -> str:
    return _digest(
        {
            "task_id": str(task_id or "").strip().lower(),
            "binding_id": str(binding_id or "").strip(),
            "task_input": dict(task_input),
        }
    )


def reserve_evaluation_execution(
    raw: dict[str, Any],
    *,
    idempotency_key: str,
    task_id: str,
    binding_id: str,
    task_input: Mapping[str, Any],
    api_key_id: str,
    evaluation_grant_id: str,
) -> dict[str, Any]:
    key = str(idempotency_key or "").strip()
    if len(key) < 8 or len(key) > 160:
        raise ValueError("idempotency_key must contain between 8 and 160 characters")
    request_sha256 = execution_request_sha256(
        task_id=task_id,
        binding_id=binding_id,
        task_input=task_input,
    )
    key_sha256 = _digest(key)
    items = raw.get(EVALUATION_IDEMPOTENCY_STORAGE_KEY, [])
    if not isinstance(items, list):
        items = []

    for item in reversed(items):
        if not isinstance(item, dict):
            continue
        if str(item.get("idempotency_key_sha256") or "") != key_sha256:
            continue
        if str(item.get("request_sha256") or "") != request_sha256:
            return {
                "status": "conflict",
                "request_sha256": request_sha256,
                "idempotency_key_sha256": key_sha256,
                "previous_state": item.get("state"),
            }
        return {
            "status": "duplicate",
            "request_sha256": request_sha256,
            "idempotency_key_sha256": key_sha256,
            "previous_state": item.get("state"),
            "reservation_id": item.get("reservation_id"),
        }

    reservation_id = f"evalidem_{key_sha256[:16]}_{request_sha256[:12]}"
    item = {
        "reservation_id": reservation_id,
        "idempotency_key_sha256": key_sha256,
        "request_sha256": request_sha256,
        "task_id": str(task_id or "").strip().lower(),
        "binding_id": str(binding_id or "").strip(),
        "api_key_id": str(api_key_id or ""),
        "evaluation_grant_id": str(evaluation_grant_id or ""),
        "state": "reserved_before_network",
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
        "raw_task_input_persisted": False,
        "raw_idempotency_key_persisted": False,
        "production_allowed": False,
    }
    items.append(item)
    raw[EVALUATION_IDEMPOTENCY_STORAGE_KEY] = items[-500:]
    return {
        "status": "reserved",
        "request_sha256": request_sha256,
        "idempotency_key_sha256": key_sha256,
        "reservation_id": reservation_id,
        "previous_state": None,
    }


def update_evaluation_execution_reservation(
    raw: dict[str, Any],
    *,
    reservation_id: str,
    state: str,
    execution_id: str | None = None,
    evidence_sha256: str | None = None,
) -> None:
    items = raw.get(EVALUATION_IDEMPOTENCY_STORAGE_KEY, [])
    if not isinstance(items, list):
        return
    for item in reversed(items):
        if not isinstance(item, dict):
            continue
        if str(item.get("reservation_id") or "") != reservation_id:
            continue
        item["state"] = str(state or "unknown")
        item["updated_at"] = datetime.now(UTC).isoformat()
        if execution_id:
            item["execution_id"] = str(execution_id)
        if evidence_sha256:
            item["evidence_sha256"] = str(evidence_sha256)
        return


__all__ = [
    "EVALUATION_IDEMPOTENCY_STORAGE_KEY",
    "execution_request_sha256",
    "reserve_evaluation_execution",
    "update_evaluation_execution_reservation",
]
