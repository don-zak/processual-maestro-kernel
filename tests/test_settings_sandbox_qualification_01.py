from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime, timedelta

from processual_api.services import api_key_store


def _pbkdf2_hash(raw_key: str) -> str:
    iterations = 120_000
    salt = b"settings-sandbox-qualification-01"
    digest = hashlib.pbkdf2_hmac("sha256", raw_key.encode("utf-8"), salt, iterations)
    return "pbkdf2_sha256${}${}${}".format(
        iterations,
        base64.urlsafe_b64encode(salt).decode("ascii"),
        base64.urlsafe_b64encode(digest).decode("ascii"),
    )


def _write_settings(tmp_path, *, raw_key: str, status: str = "enabled", expires_at: str | None = None):
    payload = {
        "subscription": {"client_id": "tenant-qualification"},
        "api_keys": [
            {
                "id": "sandbox-key-01",
                "client_id": "tenant-qualification",
                "prefix": raw_key[:12] + "...",
                "hashed": _pbkdf2_hash(raw_key),
                "status": status,
                "environment": "sandbox",
                "production_allowed": False,
                "runtime_connector_approved": False,
                "scopes": ["read:health"],
                "expires_at": expires_at,
                "usage_count": 0,
                "revoked_at": None,
            }
        ],
    }
    path = tmp_path / "settings_client-qualification.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_sandbox_key_verification_uses_hash_only_and_records_usage(tmp_path, monkeypatch) -> None:
    raw_key = "pmk_sandbox_qualification_visible_once"
    path = _write_settings(
        tmp_path,
        raw_key=raw_key,
        expires_at=(datetime.now(UTC) + timedelta(days=1)).isoformat(),
    )
    monkeypatch.setattr(api_key_store, "_DATA_DIR", tmp_path)

    identity = api_key_store.verify_dynamic_api_key(raw_key)

    assert identity is not None
    assert identity["auth_method"] == "api_key"
    assert identity["api_key_id"] == "sandbox-key-01"
    stored = json.loads(path.read_text(encoding="utf-8"))["api_keys"][0]
    assert raw_key not in json.dumps(stored)
    assert stored["usage_count"] == 1
    assert stored["production_allowed"] is False
    assert stored["runtime_connector_approved"] is False


def test_revoked_sandbox_key_is_denied(tmp_path, monkeypatch) -> None:
    raw_key = "pmk_sandbox_qualification_revoked"
    _write_settings(
        tmp_path,
        raw_key=raw_key,
        status="revoked",
        expires_at=(datetime.now(UTC) + timedelta(days=1)).isoformat(),
    )
    monkeypatch.setattr(api_key_store, "_DATA_DIR", tmp_path)

    assert api_key_store.verify_dynamic_api_key(raw_key) is None


def test_expired_sandbox_key_is_denied_and_marked_expired(tmp_path, monkeypatch) -> None:
    raw_key = "pmk_sandbox_qualification_expired"
    path = _write_settings(
        tmp_path,
        raw_key=raw_key,
        expires_at=(datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
    )
    monkeypatch.setattr(api_key_store, "_DATA_DIR", tmp_path)

    assert api_key_store.verify_dynamic_api_key(raw_key) is None
    stored = json.loads(path.read_text(encoding="utf-8"))["api_keys"][0]
    assert stored["status"] == "expired"
    assert stored["usage_count"] == 0
