"""Safe local progress tracking for operator pilot handoff actions 14E."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from processual_api.services.operator_pilot_handoff_actions import (
    build_operator_pilot_handoff_actions_preview,
)

PROGRESS_PHASE_ID = "operator-pilot-handoff-progress-14e"
PROGRESS_SCHEMA_VERSION = "operator_pilot_handoff_progress_14e"

DEFAULT_PROGRESS_STORE_PATH = Path("data/operator_pilot_handoff_progress.json")

ALLOWED_PROGRESS_STATUSES = (
    "pending_operator_input",
    "requested",
    "received_for_review",
    "needs_clarification",
)

_ALLOWED_UPDATE_FIELDS = {
    "status",
    "supervisor_actor",
    "note",
    "safe_reference",
}

_FORBIDDEN_TEXT_FRAGMENTS = (
    "http://",
    "https://",
    "sk-",
    "secret",
    "password",
    "passwd",
    "token=",
    "api_key",
    "apikey",
    "bearer ",
    "authorization:",
)


def _guardrails() -> dict[str, bool]:
    return {
        "production_allowed": False,
        "runtime_connector_approved": False,
        "customer_credentials_present": False,
        "external_http_allowed": False,
        "automatic_activation_allowed": False,
        "action_execution_allowed": False,
        "credentials_storage_allowed": False,
        "free_form_secret_fields_allowed": False,
        "local_progress_tracking_only": True,
    }


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def progress_store_path(path: str | Path | None = None) -> Path:
    if path is not None:
        return Path(path)

    environment_path = os.getenv("PMK_OPERATOR_PILOT_HANDOFF_PROGRESS_PATH")

    if environment_path:
        return Path(environment_path)

    return DEFAULT_PROGRESS_STORE_PATH


def _safe_text(
    value: object,
    *,
    field_name: str,
    max_length: int,
    required: bool = False,
) -> str:
    text = str(value or "").strip()

    if required and not text:
        raise ValueError(f"{field_name} is required")

    lowered = text.lower()

    if any(fragment in lowered for fragment in _FORBIDDEN_TEXT_FRAGMENTS):
        raise ValueError(f"{field_name} contains a prohibited secret or external reference")

    return text[:max_length]


def _action_identifier(action: dict[str, Any]) -> str:
    for candidate_name in ("action_id", "id", "key"):
        candidate = str(action.get(candidate_name, "")).strip()

        if candidate:
            return candidate

    raise RuntimeError("14D action is missing a stable identifier")


def _known_actions() -> tuple[dict[str, Any], ...]:
    preview = build_operator_pilot_handoff_actions_preview()
    actions = preview.get("actions", ())

    if not isinstance(actions, (list, tuple)):
        raise RuntimeError("14D actions preview has an invalid actions list")

    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for raw_action in actions:
        if not isinstance(raw_action, dict):
            raise RuntimeError("14D action entry must be an object")

        action = dict(raw_action)
        action_id = _action_identifier(action)

        if action_id in seen_ids:
            raise RuntimeError(f"Duplicate 14D action identifier: {action_id}")

        seen_ids.add(action_id)
        action["action_id"] = action_id
        normalized.append(action)

    return tuple(normalized)


def _empty_store_payload() -> dict[str, Any]:
    return {
        "schema_version": PROGRESS_SCHEMA_VERSION,
        "actions": {},
        "timeline": [],
        "guardrails": _guardrails(),
        "updated_at": "",
    }


def _read_store(path: Path) -> dict[str, Any]:
    if not path.exists():
        return _empty_store_payload()

    raw_text = path.read_text(encoding="utf-8").strip()

    if not raw_text:
        return _empty_store_payload()

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        return _empty_store_payload()

    if not isinstance(payload, dict):
        return _empty_store_payload()

    actions = payload.get("actions")
    timeline = payload.get("timeline")

    if not isinstance(actions, dict):
        actions = {}

    if not isinstance(timeline, list):
        timeline = []

    return {
        "schema_version": PROGRESS_SCHEMA_VERSION,
        "actions": actions,
        "timeline": timeline,
        "guardrails": _guardrails(),
        "updated_at": str(payload.get("updated_at", "")),
    }


def _write_store(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    safe_payload = {
        "schema_version": PROGRESS_SCHEMA_VERSION,
        "actions": payload.get("actions", {}),
        "timeline": payload.get("timeline", [])[-200:],
        "guardrails": _guardrails(),
        "updated_at": str(payload.get("updated_at", "")),
    }

    temporary_path = path.with_suffix(path.suffix + ".tmp")

    temporary_path.write_text(
        json.dumps(
            safe_payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    temporary_path.replace(path)


def _default_progress_record(action_id: str) -> dict[str, str]:
    return {
        "action_id": action_id,
        "status": "pending_operator_input",
        "supervisor_actor": "",
        "note": "",
        "safe_reference": "",
        "updated_at": "",
    }


def _normalize_stored_record(
    action_id: str,
    value: object,
) -> dict[str, str]:
    record = _default_progress_record(action_id)

    if not isinstance(value, dict):
        return record

    stored_status = str(value.get("status", "")).strip().lower()

    if stored_status in ALLOWED_PROGRESS_STATUSES:
        record["status"] = stored_status

    record["supervisor_actor"] = _safe_text(
        value.get("supervisor_actor"),
        field_name="supervisor_actor",
        max_length=120,
    )

    record["note"] = _safe_text(
        value.get("note"),
        field_name="note",
        max_length=240,
    )

    record["safe_reference"] = _safe_text(
        value.get("safe_reference"),
        field_name="safe_reference",
        max_length=160,
    )

    record["updated_at"] = str(value.get("updated_at", ""))[:80]

    return record


def build_operator_pilot_handoff_progress_payload(
    path: str | Path | None = None,
) -> dict[str, Any]:
    store_path = progress_store_path(path)
    stored_payload = _read_store(store_path)
    stored_actions = stored_payload["actions"]

    actions_payload: list[dict[str, Any]] = []

    for action in _known_actions():
        action_id = action["action_id"]
        progress = _normalize_stored_record(
            action_id,
            stored_actions.get(action_id),
        )

        actions_payload.append(
            {
                "action_id": action_id,
                "title": str(action.get("title") or action.get("label") or action_id.replace("_", " ").title()),
                "execution_mode": str(action.get("execution_mode", "copy_only")),
                **progress,
            }
        )

    status_counts = {
        status: sum(1 for action in actions_payload if action["status"] == status)
        for status in ALLOWED_PROGRESS_STATUSES
    }

    return {
        "phase_id": PROGRESS_PHASE_ID,
        "schema_version": PROGRESS_SCHEMA_VERSION,
        "storage": "local_json_only",
        "action_count": len(actions_payload),
        "actions": actions_payload,
        "status_counts": status_counts,
        "allowed_statuses": list(ALLOWED_PROGRESS_STATUSES),
        "timeline": stored_payload["timeline"][-200:],
        "timeline_event_count": len(stored_payload["timeline"][-200:]),
        "updated_at": stored_payload["updated_at"],
        "guardrails": _guardrails(),
    }


def update_operator_pilot_handoff_action_progress(
    action_id: str,
    payload: dict[str, Any],
    path: str | Path | None = None,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("progress update payload must be an object")

    unexpected_fields = set(payload) - _ALLOWED_UPDATE_FIELDS

    if unexpected_fields:
        fields = ", ".join(sorted(unexpected_fields))
        raise ValueError(f"unsupported progress update fields: {fields}")

    known_action_ids = {action["action_id"] for action in _known_actions()}

    normalized_action_id = str(action_id or "").strip()

    if normalized_action_id not in known_action_ids:
        raise ValueError(f"unknown operator pilot handoff action: {normalized_action_id}")

    status = str(payload.get("status", "")).strip().lower()

    if status not in ALLOWED_PROGRESS_STATUSES:
        raise ValueError(f"unsupported progress status: {status}")

    supervisor_actor = _safe_text(
        payload.get("supervisor_actor"),
        field_name="supervisor_actor",
        max_length=120,
        required=True,
    )

    note = _safe_text(
        payload.get("note"),
        field_name="note",
        max_length=240,
    )

    safe_reference = _safe_text(
        payload.get("safe_reference"),
        field_name="safe_reference",
        max_length=160,
    )

    store_path = progress_store_path(path)
    stored_payload = _read_store(store_path)
    updated_at = _utc_now()

    updated_record = {
        "action_id": normalized_action_id,
        "status": status,
        "supervisor_actor": supervisor_actor,
        "note": note,
        "safe_reference": safe_reference,
        "updated_at": updated_at,
    }

    stored_payload["actions"][normalized_action_id] = updated_record
    stored_payload["updated_at"] = updated_at
    stored_payload["timeline"].append(
        {
            "event": "operator_pilot_handoff_progress_updated",
            "action_id": normalized_action_id,
            "status": status,
            "supervisor_actor": supervisor_actor,
            "note": note,
            "safe_reference": safe_reference,
            "at": updated_at,
        }
    )

    _write_store(store_path, stored_payload)

    result = build_operator_pilot_handoff_progress_payload(store_path)
    result["updated_action"] = dict(updated_record)

    return result


__all__ = [
    "ALLOWED_PROGRESS_STATUSES",
    "DEFAULT_PROGRESS_STORE_PATH",
    "PROGRESS_PHASE_ID",
    "PROGRESS_SCHEMA_VERSION",
    "build_operator_pilot_handoff_progress_payload",
    "progress_store_path",
    "update_operator_pilot_handoff_action_progress",
]
