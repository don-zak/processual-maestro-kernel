from __future__ import annotations

import json
import re
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

AUDIT_EVENT_PREFIX = "aud_"
REDACTED = "[REDACTED]"
REDACTED_FIELD = "[REDACTED_FIELD]"

_ALLOWED_RESULTS = frozenset({"success", "denied", "already_sent", "failure"})

_SENSITIVE_FIELD_TOKENS = (
    "raw_api_key",
    "api_key",
    "provider_secret",
    "encrypted_key",
    "authorization",
    "cookie",
    "password",
    "client_secret",
    "secret",
    "token",
    "jwt",
)

_SUPERVISOR_SESSION_KEY_RE = re.compile(r"pmk_sup_[A-Za-z0-9._~+/=-]+")
_API_KEY_RE = re.compile(r"pmk_(?!sup_)[A-Za-z0-9._~+/=-]+")
_BEARER_RE = re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE)
_JWT_RE = re.compile(
    r"\beyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"
)
_FIELD_ASSIGNMENT_RE = re.compile(
    r"\b("
    r"raw_api_key|api_key|provider_secret|encrypted_key|authorization|cookie|"
    r"password|client_secret|secret|token|jwt"
    r")\s*[:=]\s*[^,\s}\]]+",
    re.IGNORECASE,
)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _new_event_id() -> str:
    return f"{AUDIT_EVENT_PREFIX}{secrets.token_urlsafe(16)}"


def _is_sensitive_field_name(name: str) -> bool:
    normalized = name.strip().lower()
    return any(token in normalized for token in _SENSITIVE_FIELD_TOKENS)


def redact_audit_string(value: str) -> str:
    redacted = _SUPERVISOR_SESSION_KEY_RE.sub(REDACTED, value)
    redacted = _API_KEY_RE.sub(REDACTED, redacted)
    redacted = _BEARER_RE.sub(f"Bearer {REDACTED}", redacted)
    redacted = _JWT_RE.sub(REDACTED, redacted)
    return _FIELD_ASSIGNMENT_RE.sub(REDACTED_FIELD, redacted)


def _redact_value(value: Any) -> tuple[Any, int]:
    if isinstance(value, str):
        return redact_audit_string(value), 0

    if isinstance(value, list):
        redacted_items = []
        count = 0
        for item in value:
            redacted_item, item_count = _redact_value(item)
            redacted_items.append(redacted_item)
            count += item_count
        return redacted_items, count

    if isinstance(value, tuple):
        redacted_items = []
        count = 0
        for item in value:
            redacted_item, item_count = _redact_value(item)
            redacted_items.append(redacted_item)
            count += item_count
        return redacted_items, count

    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        redacted_count = 0

        for key, item in value.items():
            key_text = str(key)
            if _is_sensitive_field_name(key_text):
                redacted_count += 1
                continue

            redacted_item, item_count = _redact_value(item)
            redacted[key_text] = redacted_item
            redacted_count += item_count

        if redacted_count:
            redacted["redacted_fields_count"] = redacted_count

        return redacted, redacted_count

    return value, 0


def redact_audit_value(value: Any) -> Any:
    redacted, _count = _redact_value(value)
    return redacted


def append_admin_audit_event(
    *,
    audit_path: str | Path,
    actor: str,
    actor_level: str,
    action: str,
    target_type: str,
    target_id: str,
    result: str,
    session_key_id: str | None = None,
    client_id: str | None = None,
    source: str | None = None,
    safe_note: str | None = None,
    reason: str | None = None,
    request_path: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if result not in _ALLOWED_RESULTS:
        allowed = ", ".join(sorted(_ALLOWED_RESULTS))
        raise ValueError(
            f"Unsupported audit result {result!r}; expected one of: {allowed}"
        )

    event: dict[str, Any] = {
        "event_id": _new_event_id(),
        "at": _now_iso(),
        "actor": redact_audit_string(actor),
        "actor_level": redact_audit_string(actor_level),
        "action": redact_audit_string(action),
        "target_type": redact_audit_string(target_type),
        "target_id": redact_audit_string(target_id),
        "result": result,
    }

    optional_fields = {
        "session_key_id": session_key_id,
        "client_id": client_id,
        "source": source,
        "safe_note": safe_note,
        "reason": reason,
        "request_path": request_path,
    }
    for key, value in optional_fields.items():
        if value is not None:
            event[key] = redact_audit_string(value)

    if metadata is not None:
        event["metadata"] = redact_audit_value(metadata)

    path = Path(audit_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True))
        handle.write("\n")

    return event


def read_admin_audit_events(
    audit_path: str | Path,
    *,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    path = Path(audit_path)
    if not path.exists():
        return []

    events = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    if limit is None:
        return events
    if limit <= 0:
        return []
    return events[-limit:]
