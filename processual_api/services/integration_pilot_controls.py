"""Pilot terms, supervisor controls, and activation permission keys for 13B.

13B remains onboarding/sandbox-preparation only. It does not enable production,
runtime connectors, external HTTP, or raw secret visibility.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

GUARDRAILS: dict[str, bool] = {
    "runtime_enabled": False,
    "production_allowed": False,
    "external_http_enabled": False,
    "raw_secret_visible": False,
}

TASK_STATUSES: set[str] = {
    "draft",
    "claim_issued",
    "claimed",
    "onboarding_in_progress",
    "pending_operator_inputs",
    "pending_supervisor_review",
    "sandbox_grant_issued",
    "sandbox_active",
    "suspended",
    "revoked",
    "cancelled",
    "expired",
    "completed",
    "production_review_required",
    "activation_permission_issued",
}

DISABLED_STATUSES: set[str] = {
    "suspended",
    "revoked",
    "cancelled",
    "expired",
}

DEFAULT_ALLOWED_OPERATIONS: list[str] = [
    "review_operator_inputs",
    "prepare_sandbox_handoff",
    "request_security_scope_mapping",
]

DEFAULT_ALLOWED_RATE_LIMITS: dict[str, int] = {
    "requests_per_minute": 30,
    "requests_per_day": 500,
}


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _store_path() -> Path:
    override = os.environ.get("PMK_INTEGRATION_PILOT_TASKS_STORE")
    if override:
        return Path(override)
    return _project_root() / "data" / "integration_pilot_tasks.json"


def _audit_path() -> Path:
    override = os.environ.get("PMK_ADMIN_AUDIT_EVENTS_PATH")
    if override:
        return Path(override)
    return _project_root() / "data" / "admin_audit_events.jsonl"


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _new_store() -> dict[str, Any]:
    return {
        "version": "integration-pilot-controls-13b",
        "tasks": [],
    }


def _load_store() -> dict[str, Any]:
    path = _store_path()
    if not path.exists():
        return _new_store()
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        loaded = _new_store()

    if not isinstance(loaded, dict):
        loaded = _new_store()

    loaded.setdefault("version", "integration-pilot-controls-13b")
    loaded.setdefault("tasks", [])
    return loaded


def _save_store(store: dict[str, Any]) -> None:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(store, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


def _append_audit_event(event_type: str, **payload: Any) -> None:
    path = _audit_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "event": event_type,
        "event_type": event_type,
        "at": _iso(_utcnow()),
        **payload,
        **GUARDRAILS,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def _clean_string(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _clean_list(value: Any, default: list[str] | None = None) -> list[str]:
    if value is None:
        return list(default or [])
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else list(default or [])
    if isinstance(value, (list, tuple, set)):
        cleaned: list[str] = []
        for item in value:
            text = str(item).strip()
            if text and text not in cleaned:
                cleaned.append(text)
        return cleaned or list(default or [])
    return list(default or [])


def _clean_rate_limits(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return dict(DEFAULT_ALLOWED_RATE_LIMITS)

    cleaned: dict[str, int] = {}
    for key, raw in value.items():
        name = str(key).strip()
        if not name:
            continue
        try:
            number = int(raw)
        except (TypeError, ValueError):
            continue
        if number > 0:
            cleaned[name] = number

    return cleaned or dict(DEFAULT_ALLOWED_RATE_LIMITS)


def _find_task(store: dict[str, Any], task_id: str) -> dict[str, Any] | None:
    for task in store.get("tasks", []):
        if task.get("task_id") == task_id:
            return task
    return None


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def _mask_key(key_id: str) -> str:
    return f"{key_id}.************************"


def _timeline_event(action: str, actor: str, reason: str = "") -> dict[str, Any]:
    return {
        "action": action,
        "actor": actor,
        "reason": reason,
        "at": _iso(_utcnow()),
        **GUARDRAILS,
    }


def _sanitize_task(task: dict[str, Any]) -> dict[str, Any]:
    safe = dict(task)
    safe.pop("activation_permission_key_hash", None)
    safe.pop("activation_permission_key_once", None)

    key_id = str(task.get("activation_permission_key_id") or "")
    safe["masked_activation_permission_key"] = _mask_key(key_id) if key_id else ""
    safe.update(GUARDRAILS)
    return safe


def create_integration_task(
    payload: dict[str, Any] | None,
    *,
    created_by: str = "supervisor",
) -> dict[str, Any]:
    payload = payload or {}
    now = _utcnow()

    requested_status = _clean_string(payload.get("status"), "pending_supervisor_review")
    status = requested_status if requested_status in TASK_STATUSES else "pending_supervisor_review"

    task_id = "itask_" + uuid.uuid4().hex[:16]
    task = {
        "task_id": task_id,
        "source": _clean_string(payload.get("source"), "supervisor_api_keys_panel"),
        "claim_key_id": _clean_string(payload.get("claim_key_id")),
        "client_id": _clean_string(payload.get("client_id"), "pending-client"),
        "user_id": _clean_string(payload.get("user_id"), "pending-user"),
        "operator_org_id": _clean_string(payload.get("operator_org_id"), "pending-operator-org"),
        "integration_officer_identity": _clean_string(
            payload.get("integration_officer_identity"),
            "operator-integration-officer",
        ),
        "status": status,
        "pilot_terms_note": _clean_string(payload.get("pilot_terms_note")),
        "public_reason_for_client": _clean_string(payload.get("public_reason_for_client")),
        "internal_reason_for_supervisor": _clean_string(
            payload.get("internal_reason_for_supervisor")
        ),
        "terms_source": _clean_string(payload.get("terms_source"), "supervisor_note"),
        "terms_reference": _clean_string(payload.get("terms_reference")),
        "expires_at": _clean_string(payload.get("expires_at")),
        "allowed_operations": _clean_list(
            payload.get("allowed_operations"),
            DEFAULT_ALLOWED_OPERATIONS,
        ),
        "allowed_rate_limits": _clean_rate_limits(payload.get("allowed_rate_limits")),
        "sandbox_only": True,
        "sandbox_grant_disabled": True,
        "integration_key_revoked": False,
        "runtime_connector_grant_disabled": True,
        "activation_permission_key_id": "",
        "activation_permission_issued_at": "",
        "activation_permission_expires_at": "",
        "created_at": _iso(now),
        "updated_at": _iso(now),
        "created_by": created_by,
        "timeline": [_timeline_event("created", created_by)],
        **GUARDRAILS,
    }

    store = _load_store()
    store["tasks"].append(task)
    _save_store(store)

    _append_audit_event(
        "integration_task_created",
        task_id=task_id,
        client_id=task["client_id"],
        operator_org_id=task["operator_org_id"],
        created_by=created_by,
        status=status,
    )

    return {
        "ok": True,
        "package_version": "integration-pilot-controls-13b",
        "task": _sanitize_task(task),
        "guardrails": dict(GUARDRAILS),
    }


def list_integration_tasks() -> dict[str, Any]:
    store = _load_store()
    tasks = [_sanitize_task(task) for task in store.get("tasks", [])]
    return {
        "package_version": "integration-pilot-controls-13b",
        "tasks": tasks,
        "task_count": len(tasks),
        "guardrails": dict(GUARDRAILS),
    }


def control_integration_task(
    task_id: str,
    action: str,
    *,
    actor: str = "supervisor",
    reason: str = "",
) -> dict[str, Any]:
    action = _clean_string(action)
    status_by_action = {
        "suspend": "suspended",
        "resume": "pending_supervisor_review",
        "revoke": "revoked",
        "cancel": "cancelled",
    }

    if action not in status_by_action:
        return {
            "ok": False,
            "error": "unsupported_task_action",
            "action": action,
            "guardrails": dict(GUARDRAILS),
        }

    store = _load_store()
    task = _find_task(store, task_id)
    if not task:
        return {
            "ok": False,
            "error": "task_not_found",
            "task_id": task_id,
            "guardrails": dict(GUARDRAILS),
        }

    new_status = status_by_action[action]
    task["status"] = new_status
    task["updated_at"] = _iso(_utcnow())
    task["public_reason_for_client"] = reason or task.get("public_reason_for_client", "")
    task["internal_reason_for_supervisor"] = reason

    if action in {"suspend", "revoke", "cancel"}:
        task["sandbox_grant_disabled"] = True
        task["runtime_connector_grant_disabled"] = True

    if action in {"revoke", "cancel"}:
        task["integration_key_revoked"] = True

    task.setdefault("timeline", []).append(_timeline_event(action, actor, reason))
    task.update(GUARDRAILS)

    _save_store(store)

    event_type = {
        "suspend": "integration_task_suspended",
        "resume": "integration_task_resumed",
        "revoke": "integration_task_revoked",
        "cancel": "integration_task_cancelled",
    }[action]

    _append_audit_event(
        event_type,
        task_id=task_id,
        action=action,
        status=new_status,
        actor=actor,
        reason=reason,
        sandbox_grant_disabled=task["sandbox_grant_disabled"],
        runtime_connector_grant_disabled=task["runtime_connector_grant_disabled"],
        integration_key_revoked=task["integration_key_revoked"],
    )

    return {
        "ok": True,
        "action": action,
        "task": _sanitize_task(task),
        "guardrails": dict(GUARDRAILS),
    }


def issue_activation_permission_key(
    task_id: str,
    payload: dict[str, Any] | None = None,
    *,
    issued_by: str = "supervisor",
) -> dict[str, Any]:
    payload = payload or {}
    store = _load_store()
    task = _find_task(store, task_id)
    if not task:
        return {
            "ok": False,
            "error": "task_not_found",
            "task_id": task_id,
            "guardrails": dict(GUARDRAILS),
        }

    if task.get("status") in DISABLED_STATUSES:
        return {
            "ok": False,
            "error": "task_not_eligible_for_activation_permission",
            "task": _sanitize_task(task),
            "guardrails": dict(GUARDRAILS),
        }

    activation_permission_already_issued = (
        bool(task.get("activation_permission_key_id"))
        or bool(task.get("activation_permission_key_hash"))
        or bool(task.get("activation_permission_issued_at"))
        or task.get("status") == "activation_permission_issued"
    )
    if activation_permission_already_issued:
        return {
            "ok": False,
            "error": "activation_permission_key_already_issued",
            "task": _sanitize_task(task),
            "guardrails": dict(GUARDRAILS),
        }

    now = _utcnow()
    expires_at = _clean_string(payload.get("expires_at"))
    if not expires_at:
        expires_at = _iso(now + timedelta(days=7))

    key_id = "iapk_" + uuid.uuid4().hex[:16]
    raw_key = f"{key_id}.{secrets.token_urlsafe(32)}"

    task["activation_permission_key_id"] = key_id
    task["activation_permission_key_hash"] = _hash_key(raw_key)
    task["activation_permission_issued_at"] = _iso(now)
    task["activation_permission_expires_at"] = expires_at
    task["activation_permission_issued_by"] = issued_by
    task["status"] = "activation_permission_issued"
    task["updated_at"] = _iso(now)
    task["sandbox_only"] = True
    task["sandbox_grant_disabled"] = True
    task["runtime_connector_grant_disabled"] = True
    task.setdefault("timeline", []).append(
        _timeline_event("activation_permission_key_issued", issued_by)
    )
    task.update(GUARDRAILS)

    _save_store(store)

    _append_audit_event(
        "integration_activation_permission_key_issued",
        task_id=task_id,
        activation_permission_key_id=key_id,
        client_id=task.get("client_id"),
        operator_org_id=task.get("operator_org_id"),
        issued_by=issued_by,
        expires_at=expires_at,
        sandbox_grant_disabled=True,
        runtime_connector_grant_disabled=True,
    )

    return {
        "ok": True,
        "package_version": "integration-pilot-controls-13b",
        "activation_permission_key_once": raw_key,
        "raw_activation_permission_key_visible_once": True,
        "task": _sanitize_task(task),
        "guardrails": dict(GUARDRAILS),
    }

def _parse_activation_permission_expiry(
    value: Any,
) -> datetime | None:
    cleaned = _clean_string(value)
    if not cleaned:
        return None

    try:
        parsed = datetime.fromisoformat(
            cleaned.replace("Z", "+00:00")
        )
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return None

    return parsed.astimezone(UTC)


def validate_activation_permission_key(
    task_id: str,
    raw_key: str,
) -> dict[str, Any]:
    """Validate an issued key against persisted state without side effects."""

    store = _load_store()
    task = _find_task(store, task_id)

    if not task:
        return {
            "ok": False,
            "error": "task_not_found",
            "task_id": task_id,
            "activation_permission_key_valid": False,
            "guardrails": dict(GUARDRAILS),
        }

    safe_task = _sanitize_task(task)

    if (
        task.get("status") != "activation_permission_issued"
        or task.get("status") in DISABLED_STATUSES
        or task.get("integration_key_revoked") is True
    ):
        return {
            "ok": False,
            "error": "activation_permission_key_inactive",
            "activation_permission_key_valid": False,
            "task": safe_task,
            "guardrails": dict(GUARDRAILS),
        }

    stored_key_id = _clean_string(
        task.get("activation_permission_key_id")
    )
    stored_key_hash = _clean_string(
        task.get("activation_permission_key_hash")
    )
    expires_at = _parse_activation_permission_expiry(
        task.get("activation_permission_expires_at")
    )

    if not stored_key_id or not stored_key_hash or expires_at is None:
        return {
            "ok": False,
            "error": "activation_permission_key_metadata_invalid",
            "activation_permission_key_valid": False,
            "task": safe_task,
            "guardrails": dict(GUARDRAILS),
        }

    if expires_at <= _utcnow():
        return {
            "ok": False,
            "error": "activation_permission_key_expired",
            "activation_permission_key_valid": False,
            "task": safe_task,
            "guardrails": dict(GUARDRAILS),
        }

    if not isinstance(raw_key, str):
        raw_key = ""

    provided_key_id, separator, provided_secret = raw_key.partition(".")
    provided_key_hash = _hash_key(raw_key) if raw_key else ""

    key_matches = (
        bool(separator)
        and bool(provided_secret)
        and secrets.compare_digest(provided_key_id, stored_key_id)
        and secrets.compare_digest(provided_key_hash, stored_key_hash)
    )

    if not key_matches:
        return {
            "ok": False,
            "error": "invalid_activation_permission_key",
            "activation_permission_key_valid": False,
            "task": safe_task,
            "guardrails": dict(GUARDRAILS),
        }

    return {
        "ok": True,
        "package_version": "integration-pilot-controls-16g-r4",
        "activation_permission_key_valid": True,
        "task": safe_task,
        "guardrails": dict(GUARDRAILS),
    }
