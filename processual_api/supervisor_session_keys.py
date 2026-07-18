"""Supervisor session key store for three-level admin supervision."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .supervision_rbac import (
    can_issue_supervisor_session_key,
    scopes_for_supervision_level,
)

SUPERVISOR_SESSION_KEY_PREFIX = "pmk_sup_"
_HASH_NAME = "sha256"
_HASH_ITERATIONS = 200_000


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _parse_dt(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _load_store(path: Path) -> dict[str, list[dict[str, Any]]]:
    if not path.exists():
        return {"supervisor_session_keys": []}

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"supervisor_session_keys": []}

    if not isinstance(raw, dict):
        return {"supervisor_session_keys": []}

    keys = raw.get("supervisor_session_keys")
    if not isinstance(keys, list):
        raw["supervisor_session_keys"] = []

    return raw


def _save_store(path: Path, raw: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(raw, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _actor_email(actor: dict[str, Any]) -> str:
    return str(actor.get("email") or actor.get("sub") or actor.get("user_id") or "").strip()


def _actor_level(actor: dict[str, Any]) -> str:
    return str(actor.get("supervision_level") or "").strip().lower()


def _hash_key(raw_key: str, *, salt: bytes | None = None) -> str:
    safe_salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        _HASH_NAME,
        raw_key.encode("utf-8"),
        safe_salt,
        _HASH_ITERATIONS,
    )
    return "$".join(
        (
            "pbkdf2",
            _HASH_NAME,
            str(_HASH_ITERATIONS),
            base64.urlsafe_b64encode(safe_salt).decode("ascii"),
            base64.urlsafe_b64encode(digest).decode("ascii"),
        )
    )


def _verify_key(raw_key: str, encoded_hash: str) -> bool:
    parts = str(encoded_hash or "").split("$")
    if len(parts) != 5:
        return False

    marker, hash_name, iterations_raw, salt_raw, digest_raw = parts
    if marker != "pbkdf2" or hash_name != _HASH_NAME:
        return False

    try:
        iterations = int(iterations_raw)
        salt = base64.urlsafe_b64decode(salt_raw.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_raw.encode("ascii"))
    except (ValueError, OSError):
        return False

    digest = hashlib.pbkdf2_hmac(
        _HASH_NAME,
        raw_key.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(digest, expected)


def _safe_record(record: dict[str, Any]) -> dict[str, Any]:
    safe = {
        "session_key_id": str(record.get("session_key_id") or ""),
        "level": str(record.get("level") or ""),
        "scopes": list(record.get("scopes") or []),
        "issued_by": str(record.get("issued_by") or ""),
        "issued_to": str(record.get("issued_to") or ""),
        "session_label": str(record.get("session_label") or ""),
        "reason": str(record.get("reason") or ""),
        "created_at": str(record.get("created_at") or ""),
        "expires_at": str(record.get("expires_at") or ""),
        "revoked_at": str(record.get("revoked_at") or ""),
        "revoked_by": str(record.get("revoked_by") or ""),
        "revocation_reason": str(record.get("revocation_reason") or ""),
        "last_used_at": str(record.get("last_used_at") or ""),
    }
    return {key: value for key, value in safe.items() if value not in ("", [], None)}


def _require_owner(actor: dict[str, Any]) -> None:
    if can_issue_supervisor_session_key(_actor_level(actor)):
        return
    raise PermissionError("Only owner_supervisor can manage supervisor session keys.")


def _session_is_expired(record: dict[str, Any]) -> bool:
    expires_at = _parse_dt(record.get("expires_at"))
    return expires_at is not None and expires_at <= datetime.now(UTC)


def issue_supervisor_session_key(
    path: Path,
    issuer: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Issue a one-time visible supervisor session key."""
    _require_owner(issuer)

    level = str(payload.get("level") or "").strip().lower()
    scopes = tuple(sorted(scopes_for_supervision_level(level)))
    if not scopes:
        raise PermissionError("Unknown or unsupported supervision level.")

    now = _now_iso()
    raw_key = SUPERVISOR_SESSION_KEY_PREFIX + secrets.token_urlsafe(32)
    record = {
        "session_key_id": "supsk_" + secrets.token_hex(12),
        "key_hash": _hash_key(raw_key),
        "level": level,
        "scopes": list(scopes),
        "issued_by": _actor_email(issuer),
        "issued_to": str(payload.get("issued_to") or "").strip(),
        "session_label": str(payload.get("session_label") or "").strip(),
        "reason": str(payload.get("reason") or "").strip(),
        "created_at": now,
        "expires_at": str(payload.get("expires_at") or "").strip(),
        "revoked_at": None,
        "last_used_at": None,
    }

    raw = _load_store(path)
    raw["supervisor_session_keys"].append(record)
    _save_store(path, raw)

    return {
        "raw_key": raw_key,
        "record": _safe_record(record),
    }


def list_supervisor_session_keys(
    path: Path,
    actor: dict[str, Any],
) -> list[dict[str, Any]]:
    """List supervisor session keys without exposing secret material."""
    _require_owner(actor)

    raw = _load_store(path)
    return [
        _safe_record(record)
        for record in raw.get("supervisor_session_keys", [])
        if isinstance(record, dict)
    ]


def validate_supervisor_session_key(path: Path, raw_key: str) -> dict[str, Any]:
    """Validate a supervisor session key and return a safe session record."""
    candidate = str(raw_key or "").strip()
    if not candidate.startswith(SUPERVISOR_SESSION_KEY_PREFIX):
        raise PermissionError("Invalid supervisor session key.")

    raw = _load_store(path)
    for record in raw.get("supervisor_session_keys", []):
        if not isinstance(record, dict):
            continue
        if not _verify_key(candidate, str(record.get("key_hash") or "")):
            continue
        if record.get("revoked_at"):
            raise PermissionError("Supervisor session key was revoked.")
        if _session_is_expired(record):
            raise PermissionError("Supervisor session key expired.")

        record["last_used_at"] = _now_iso()
        _save_store(path, raw)
        return _safe_record(record)

    raise PermissionError("Invalid supervisor session key.")


def revoke_supervisor_session_key(
    path: Path,
    actor: dict[str, Any],
    session_key_id: str,
    *,
    reason: str = "",
) -> dict[str, Any]:
    """Revoke a supervisor session key by id."""
    _require_owner(actor)

    requested = str(session_key_id or "").strip()
    raw = _load_store(path)
    for record in raw.get("supervisor_session_keys", []):
        if not isinstance(record, dict):
            continue
        if str(record.get("session_key_id") or "") != requested:
            continue

        record["revoked_at"] = _now_iso()
        record["revoked_by"] = _actor_email(actor)
        record["revocation_reason"] = str(reason or "").strip()
        _save_store(path, raw)
        return _safe_record(record)

    raise KeyError(f"Supervisor session key not found: {requested}")
