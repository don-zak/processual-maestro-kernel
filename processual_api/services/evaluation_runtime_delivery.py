"""Durable idempotency ledger for External Evaluation runtime execution.

The ledger is intentionally separate from general user settings so a successful
external side effect is never made dependent on a secondary settings/evidence
write. A claim is persisted before network execution. If the process crashes
while an execution is in-flight, automatic replay is blocked rather than
risking a duplicate external side effect.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from processual_api.dependencies import file_lock

EVALUATION_DELIVERY_SCHEMA_VERSION = "evaluation-runtime-delivery-v1"
EVALUATION_DELIVERY_MAX_RECORDS = 500
EVALUATION_DELIVERY_STATE_ACCEPTED = "accepted"
EVALUATION_DELIVERY_STATE_EXECUTING = "executing"
EVALUATION_DELIVERY_STATE_EXECUTED = "executed"
EVALUATION_DELIVERY_STATE_EVIDENCE_PERSISTED = "evidence_persisted"
EVALUATION_DELIVERY_STATE_FAILED = "failed"

_FORBIDDEN_REPLAY_KEYS = frozenset(
    {
        "api_key",
        "authorization",
        "canonical_input",
        "credentials",
        "raw_response",
        "request_body",
        "response_body",
        "secret",
        "task_input",
    }
)
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class EvaluationDeliveryError(RuntimeError):
    """Base class for delivery-ledger failures."""


class EvaluationIdempotencyConflictError(EvaluationDeliveryError):
    """The same idempotency key was reused for different authority/input."""


class EvaluationReplayBlockedError(EvaluationDeliveryError):
    """A prior execution has a non-terminal or uncertain outcome."""


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def evaluation_request_fingerprint(
    *,
    grant_id: str,
    api_key_id: str,
    task_id: str,
    binding_id: str,
    task_input: dict[str, Any],
) -> str:
    """Return a stable fingerprint without persisting raw task input."""

    payload = {
        "grant_id": str(grant_id or ""),
        "api_key_id": str(api_key_id or ""),
        "task_id": str(task_id or "").strip().lower(),
        "binding_id": str(binding_id or "").strip(),
        "task_input": task_input,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _owner_ledger_path(owner_id: str) -> Path:
    owner_hash = hashlib.sha256(str(owner_id or "").encode("utf-8")).hexdigest()
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    return _DATA_DIR / f"evaluation_delivery_{owner_hash}.json"


def _record_id(*, grant_id: str, api_key_id: str, idempotency_key: str) -> str:
    material = "\0".join((str(grant_id or ""), str(api_key_id or ""), idempotency_key))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _load_locked(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "schema_version": EVALUATION_DELIVERY_SCHEMA_VERSION,
            "records": {},
            "order": [],
        }
    try:
        loaded = json.loads(path.read_text("utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise EvaluationDeliveryError("evaluation_delivery_ledger_unreadable") from exc
    if not isinstance(loaded, dict):
        raise EvaluationDeliveryError("evaluation_delivery_ledger_invalid")
    records = loaded.get("records")
    order = loaded.get("order")
    if not isinstance(records, dict) or not isinstance(order, list):
        raise EvaluationDeliveryError("evaluation_delivery_ledger_invalid")
    loaded["schema_version"] = EVALUATION_DELIVERY_SCHEMA_VERSION
    return loaded


def _save_locked(path: Path, ledger: dict[str, Any]) -> None:
    payload = json.dumps(ledger, indent=2, sort_keys=True, ensure_ascii=False)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    backup_path = path.with_suffix(path.suffix + ".bak")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        tmp_path.write_text(payload, encoding="utf-8")
        if path.exists():
            shutil.copy2(path, backup_path)
        tmp_path.replace(path)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def _trim(ledger: dict[str, Any]) -> None:
    records = ledger["records"]
    order = ledger["order"]
    while len(order) > EVALUATION_DELIVERY_MAX_RECORDS:
        oldest = str(order.pop(0))
        records.pop(oldest, None)


def _contains_forbidden_replay_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key).strip().lower() in _FORBIDDEN_REPLAY_KEYS:
                return True
            if _contains_forbidden_replay_key(nested):
                return True
        return False
    if isinstance(value, list):
        return any(_contains_forbidden_replay_key(item) for item in value)
    return False


def _validate_safe_replay_response(replay_response: dict[str, Any]) -> None:
    if _contains_forbidden_replay_key(replay_response):
        raise EvaluationDeliveryError("evaluation_replay_payload_contains_sensitive_material")


def claim_evaluation_execution(
    *,
    owner_id: str,
    grant_id: str,
    api_key_id: str,
    idempotency_key: str,
    request_fingerprint: str,
    task_id: str,
    binding_id: str,
) -> dict[str, Any]:
    """Atomically claim one idempotent execution or return a safe replay record."""

    normalized_key = str(idempotency_key or "").strip()
    if not normalized_key:
        raise EvaluationDeliveryError("evaluation_idempotency_key_required")
    record_id = _record_id(
        grant_id=grant_id,
        api_key_id=api_key_id,
        idempotency_key=normalized_key,
    )
    path = _owner_ledger_path(owner_id)
    with file_lock(path):
        ledger = _load_locked(path)
        records = ledger["records"]
        existing = records.get(record_id)
        if isinstance(existing, dict):
            if existing.get("request_fingerprint") != request_fingerprint:
                raise EvaluationIdempotencyConflictError(
                    "evaluation_idempotency_key_payload_mismatch"
                )
            state = str(existing.get("state") or "")
            if state == EVALUATION_DELIVERY_STATE_EVIDENCE_PERSISTED:
                replay = existing.get("replay_response")
                if isinstance(replay, dict):
                    return {
                        "status": "replay",
                        "record": dict(existing),
                        "response": dict(replay),
                    }
                raise EvaluationReplayBlockedError(
                    "evaluation_replay_evidence_unavailable"
                )
            raise EvaluationReplayBlockedError(
                f"evaluation_replay_blocked_{state or 'unknown'}"
            )

        now = _now_iso()
        record = {
            "record_id": record_id,
            "idempotency_key_sha256": hashlib.sha256(
                normalized_key.encode("utf-8")
            ).hexdigest(),
            "request_fingerprint": request_fingerprint,
            "evaluation_grant_id": str(grant_id or ""),
            "api_key_id": str(api_key_id or ""),
            "task_id": str(task_id or "").strip().lower(),
            "binding_id": str(binding_id or "").strip(),
            "state": EVALUATION_DELIVERY_STATE_EXECUTING,
            "state_history": [
                {"state": EVALUATION_DELIVERY_STATE_ACCEPTED, "at": now},
                {"state": EVALUATION_DELIVERY_STATE_EXECUTING, "at": now},
            ],
            "accepted_at": now,
            "execution_started_at": now,
            "raw_task_input_persisted": False,
            "raw_secret_visible": False,
        }
        records[record_id] = record
        ledger["order"].append(record_id)
        _trim(ledger)
        _save_locked(path, ledger)
        return {"status": "claimed", "record": dict(record)}


def complete_evaluation_execution(
    *,
    owner_id: str,
    record_id: str,
    evidence: dict[str, Any],
    replay_response: dict[str, Any],
) -> dict[str, Any]:
    """Atomically persist executed/evidence states and the bounded replay payload."""

    _validate_safe_replay_response(replay_response)
    path = _owner_ledger_path(owner_id)
    with file_lock(path):
        ledger = _load_locked(path)
        record = ledger["records"].get(record_id)
        if not isinstance(record, dict):
            raise EvaluationDeliveryError("evaluation_delivery_claim_missing")
        if record.get("state") != EVALUATION_DELIVERY_STATE_EXECUTING:
            raise EvaluationDeliveryError("evaluation_delivery_state_invalid")
        now = _now_iso()
        history = record.setdefault("state_history", [])
        if not isinstance(history, list):
            history = []
            record["state_history"] = history
        history.append({"state": EVALUATION_DELIVERY_STATE_EXECUTED, "at": now})
        record["state"] = EVALUATION_DELIVERY_STATE_EVIDENCE_PERSISTED
        history.append(
            {"state": EVALUATION_DELIVERY_STATE_EVIDENCE_PERSISTED, "at": now}
        )
        record["executed_at"] = now
        record["evidence_persisted_at"] = now
        record["evidence"] = dict(evidence)
        record["replay_response"] = dict(replay_response)
        record["raw_task_input_persisted"] = False
        record["raw_secret_visible"] = False
        _save_locked(path, ledger)
        return dict(record)


def fail_evaluation_execution(
    *,
    owner_id: str,
    record_id: str,
    failure_code: str,
) -> None:
    """Mark an execution failed/uncertain without enabling automatic replay."""

    path = _owner_ledger_path(owner_id)
    with file_lock(path):
        ledger = _load_locked(path)
        record = ledger["records"].get(record_id)
        if not isinstance(record, dict):
            return
        if record.get("state") == EVALUATION_DELIVERY_STATE_EVIDENCE_PERSISTED:
            return
        now = _now_iso()
        history = record.setdefault("state_history", [])
        if not isinstance(history, list):
            history = []
            record["state_history"] = history
        record["state"] = EVALUATION_DELIVERY_STATE_FAILED
        record["failed_at"] = now
        record["failure_code"] = str(
            failure_code or "evaluation_execution_failed"
        )[:200]
        record["network_outcome"] = "unknown"
        history.append({"state": EVALUATION_DELIVERY_STATE_FAILED, "at": now})
        _save_locked(path, ledger)


__all__ = [
    "EVALUATION_DELIVERY_STATE_EVIDENCE_PERSISTED",
    "EVALUATION_DELIVERY_STATE_EXECUTING",
    "EVALUATION_DELIVERY_STATE_FAILED",
    "EvaluationDeliveryError",
    "EvaluationIdempotencyConflictError",
    "EvaluationReplayBlockedError",
    "claim_evaluation_execution",
    "complete_evaluation_execution",
    "evaluation_request_fingerprint",
    "fail_evaluation_execution",
]
