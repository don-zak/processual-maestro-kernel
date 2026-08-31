from __future__ import annotations

import base64
import hashlib
import hmac
import json
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from processual_api.services.evaluation_grants import (
    EVALUATION_EXECUTION_MODE,
    find_evaluation_grant,
    key_evaluation_grant_state,
)

try:
    import bcrypt as _bcrypt_lib
except ImportError:
    _bcrypt_lib = None

if sys.platform == "win32":
    import msvcrt

    def _lock_fd(fd: int) -> None:
        msvcrt.locking(fd, msvcrt.LK_LOCK, 1)

    def _unlock_fd(fd: int) -> None:
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    def _lock_fd(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_EX)

    def _unlock_fd(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_UN)


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


@contextmanager
def _settings_file_lock(path: Path) -> Iterator[None]:
    """Serialize API-key read/validate/update cycles across workers."""
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "a+b") as handle:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        _lock_fd(handle.fileno())
        try:
            yield
        finally:
            handle.seek(0)
            _unlock_fd(handle.fileno())


def _verify_pbkdf2_api_key(plain_key: str, hashed_key: str) -> bool:
    try:
        algorithm, iterations_raw, salt_b64, digest_b64 = hashed_key.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_raw)
        salt = base64.urlsafe_b64decode(salt_b64.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_b64.encode("ascii"))
        actual = hashlib.pbkdf2_hmac(
            "sha256",
            plain_key.encode("utf-8"),
            salt,
            iterations,
        )
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
        return _bcrypt_lib.checkpw(
            plain_key.encode("utf-8"),
            hashed_key.encode("utf-8"),
        )
    except Exception:
        return False


def _safe_load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text("utf-8"))
    except Exception:
        return {}


def _safe_save_json(path: Path, data: dict[str, Any]) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        "utf-8",
    )
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


def _public_identity(
    user_id: str,
    raw: dict[str, Any],
    key: dict[str, Any],
) -> dict[str, Any]:
    client_id = (
        key.get("client_id")
        or raw.get("client_id")
        or raw.get("subscription", {}).get("client_id")
        or user_id
    )

    scopes = key.get("scopes")
    if not isinstance(scopes, list) or not scopes:
        scopes = DEFAULT_CLIENT_SCOPES

    identity = {
        "sub": user_id,
        "user_id": user_id,
        "client_id": client_id,
        "role": key.get("role", "client"),
        "auth_method": "api_key",
        "session_type": "api_key",
        "api_key_id": key.get("id", ""),
        "api_key_prefix": key.get("prefix", ""),
        "scopes": scopes,
        "evaluation_grant_id": key.get("evaluation_grant_id"),
        "entitlement_source": key.get("entitlement_source"),
        "subscription_required": key.get("subscription_required", True),
        "allowed_task_ids": list(key.get("allowed_task_ids") or []),
        "task_scope_ids": list(key.get("task_scope_ids") or []),
        "task_authority_source": key.get("task_authority_source"),
    }

    if key.get("entitlement_source") == "admin_evaluation_grant":
        grant = find_evaluation_grant(
            raw,
            str(key.get("evaluation_grant_id") or ""),
        )
        if grant is not None:
            identity.update(
                {
                    "category": "pilot_client",
                    "allowed_endpoints": list(grant.get("allowed_endpoints") or []),
                    "endpoint_authority_source": str(
                        grant.get("endpoint_authority_source")
                        or "canonical_runtime_access_policy"
                    ),
                    "execution_mode": str(
                        grant.get("execution_mode") or EVALUATION_EXECUTION_MODE
                    ),
                    "real_runtime_execution": grant.get("real_runtime_execution") is True,
                    "evaluation_access": True,
                    "registration_required": False,
                    "commercial_quota_required": False,
                    "production_allowed": False,
                }
            )

    return identity


def _governed_evaluation_usage_limit(
    raw: dict[str, Any],
    key: dict[str, Any],
) -> int | None:
    if str(key.get("category") or "") != "pilot_client":
        return None

    grant_id = str(key.get("evaluation_grant_id") or "").strip()
    entitlement_source = str(key.get("entitlement_source") or "").strip()
    if not grant_id and entitlement_source != "admin_evaluation_grant":
        return None

    grant = find_evaluation_grant(raw, grant_id)
    if grant is None:
        return 0

    grant_limit = int(grant.get("max_requests", 0) or 0)
    if grant_limit <= 0:
        return 0

    key_limit = int(key.get("quota_limit", 0) or 0)
    if key_limit <= 0:
        return grant_limit
    return min(key_limit, grant_limit)


def verify_dynamic_api_key(api_key: str) -> dict[str, Any] | None:
    if not api_key or not api_key.startswith("pmk_"):
        return None

    if not _DATA_DIR.exists():
        return None

    now = datetime.now(UTC).isoformat()

    for path in _DATA_DIR.glob("settings_*.json"):
        with _settings_file_lock(path):
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

                grant_allowed, grant_state = key_evaluation_grant_state(raw, key)
                if not grant_allowed:
                    key["evaluation_grant_state"] = grant_state
                    changed = True
                    continue
                if key.get("category") == "pilot_client":
                    key["evaluation_grant_state"] = grant_state
                    changed = True

                hashed = key.get("hashed") or key.get("hashed_key")
                if not hashed:
                    continue

                if not _verify_stored_key(api_key, hashed):
                    continue

                usage_limit = _governed_evaluation_usage_limit(raw, key)
                usage_count = int(key.get("usage_count", 0) or 0)
                if usage_limit is not None and (
                    usage_limit <= 0 or usage_count >= usage_limit
                ):
                    key["evaluation_grant_state"] = "quota_exhausted"
                    key["quota_rejected_count"] = int(
                        key.get("quota_rejected_count", 0) or 0
                    ) + 1
                    changed = True
                    raw["api_keys"] = keys
                    _safe_save_json(path, raw)
                    return None

                key["last_used_at"] = now
                key["usage_count"] = usage_count + 1
                changed = True

                raw["api_keys"] = keys
                _safe_save_json(path, raw)

                return _public_identity(user_id, raw, key)

            if changed:
                raw["api_keys"] = keys
                _safe_save_json(path, raw)

    return None
