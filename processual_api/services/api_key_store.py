from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    import bcrypt as _bcrypt_lib
except ImportError:
    _bcrypt_lib = None


_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


DEFAULT_CLIENT_SCOPES = [
    "read:health",
    "read:adapters",
    "read:governor",
    "run:analyze",
    "run:govern",
    "run:compare",
    "read:reports",
    "create:reports",
]


def _verify_pbkdf2_api_key(plain_key: str, hashed_key: str) -> bool:
    try:
        algorithm, iterations_raw, salt_b64, digest_b64 = hashed_key.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_raw)
        salt = base64.urlsafe_b64decode(salt_b64.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_b64.encode("ascii"))
        actual = hashlib.pbkdf2_hmac("sha256", plain_key.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def _verify_stored_key(plain_key: str, hashed_key: str) -> bool:
    if not hashed_key:
        return False

    if hashed_key.startswith("pbkdf2_sha256$"):
        return _verify_pbkdf2_api_key(plain_key, hashed_key)

    if _bcrypt_lib is None:
        return False

    try:
        return _bcrypt_lib.checkpw(plain_key.encode("utf-8"), hashed_key.encode("utf-8"))
    except Exception:
        return False


def _safe_load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text("utf-8"))
    except Exception:
        return {}


def _safe_save_json(path: Path, data: dict[str, Any]) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")
    tmp_path.replace(path)


def _is_expired(value: str | None) -> bool:
    if not value:
        return False

    try:
        normalized = value.replace("Z", "+00:00")
        expiry = datetime.fromisoformat(normalized)
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=UTC)
        return expiry <= datetime.now(UTC)
    except Exception:
        return False


def _public_identity(user_id: str, raw: dict[str, Any], key: dict[str, Any]) -> dict[str, Any]:
    client_id = (
        key.get("client_id")
        or raw.get("client_id")
        or raw.get("subscription", {}).get("client_id")
        or user_id
    )

    scopes = key.get("scopes")
    if not isinstance(scopes, list) or not scopes:
        scopes = DEFAULT_CLIENT_SCOPES

    return {
        "sub": user_id,
        "user_id": user_id,
        "client_id": client_id,
        "role": key.get("role", "client"),
        "auth_method": "api_key",
        "session_type": "api_key",
        "api_key_id": key.get("id", ""),
        "api_key_prefix": key.get("prefix", ""),
        "scopes": scopes,
    }


def verify_dynamic_api_key(api_key: str) -> dict[str, Any] | None:
    if not api_key or not api_key.startswith("pmk_"):
        return None

    if not _DATA_DIR.exists():
        return None

    now = datetime.now(UTC).isoformat()

    for path in _DATA_DIR.glob("settings_*.json"):
        user_id = path.stem.replace("settings_", "", 1)
        raw = _safe_load_json(path)
        keys = raw.get("api_keys", [])

        if not isinstance(keys, list):
            continue

        changed = False

        for key in keys:
            if not isinstance(key, dict):
                continue

            status = key.get("status", "enabled")
            if status in {"revoked", "disabled", "expired"}:
                continue

            if key.get("revoked_at"):
                continue

            if _is_expired(key.get("expires_at")):
                key["status"] = "expired"
                changed = True
                continue

            hashed = key.get("hashed") or key.get("hashed_key")
            if not hashed:
                continue

            if not _verify_stored_key(api_key, hashed):
                continue

            key["last_used_at"] = now
            key["usage_count"] = int(key.get("usage_count", 0) or 0) + 1
            changed = True

            raw["api_keys"] = keys
            _safe_save_json(path, raw)

            return _public_identity(user_id, raw, key)

        if changed:
            raw["api_keys"] = keys
            _safe_save_json(path, raw)

    return None
