import json
from datetime import UTC, datetime
from pathlib import Path

from processual_api.auth.security import _pbkdf2_hash_api_key, generate_api_key
from processual_api.services import api_key_store


def _write_settings_file(
    tmp_path: Path,
    keys: list[dict],
    user_id: str = "api_key_test_user",
) -> Path:
    path = tmp_path / f"settings_{user_id}.json"
    path.write_text(
        json.dumps(
            {
                "client_id": "client_root",
                "subscription": {"client_id": "client_subscription"},
                "api_keys": keys,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def _key_record(raw_key: str, **overrides) -> dict:
    record = {
        "id": "key_1",
        "client_id": "client_direct",
        "hashed": _pbkdf2_hash_api_key(raw_key),
        "scopes": ["read:health", "read:adapters"],
        "status": "enabled",
        "created_at": datetime.now(UTC).isoformat(),
        "last_used_at": None,
        "usage_count": 0,
        "expires_at": None,
        "revoked_at": None,
    }
    record.update(overrides)
    return record


def test_verify_dynamic_api_key_accepts_hash_only_and_tracks_usage(monkeypatch, tmp_path):
    monkeypatch.setattr(api_key_store, "_DATA_DIR", tmp_path)

    raw_key = generate_api_key()
    settings_path = _write_settings_file(tmp_path, [_key_record(raw_key)])

    assert raw_key.startswith("pmk_")
    assert raw_key not in settings_path.read_text(encoding="utf-8")

    identity = api_key_store.verify_dynamic_api_key(raw_key)

    assert identity is not None

    saved = json.loads(settings_path.read_text(encoding="utf-8"))
    stored_key = saved["api_keys"][0]

    assert stored_key["hashed"].startswith("pbkdf2_sha256$")
    assert stored_key["hashed"] != raw_key
    assert raw_key not in settings_path.read_text(encoding="utf-8")
    assert stored_key["usage_count"] == 1
    assert stored_key["last_used_at"] is not None


def test_verify_dynamic_api_key_rejects_wrong_or_non_dynamic_keys(monkeypatch, tmp_path):
    monkeypatch.setattr(api_key_store, "_DATA_DIR", tmp_path)

    raw_key = generate_api_key()
    settings_path = _write_settings_file(tmp_path, [_key_record(raw_key)])

    assert api_key_store.verify_dynamic_api_key("not-a-dynamic-key") is None
    assert api_key_store.verify_dynamic_api_key(raw_key + "_wrong") is None

    saved = json.loads(settings_path.read_text(encoding="utf-8"))
    stored_key = saved["api_keys"][0]

    assert stored_key["usage_count"] == 0
    assert stored_key["last_used_at"] is None


def test_verify_dynamic_api_key_rejects_revoked_keys(monkeypatch, tmp_path):
    monkeypatch.setattr(api_key_store, "_DATA_DIR", tmp_path)

    raw_key = generate_api_key()
    settings_path = _write_settings_file(
        tmp_path,
        [
            _key_record(
                raw_key,
                status="revoked",
                revoked_at=datetime.now(UTC).isoformat(),
            )
        ],
    )

    assert api_key_store.verify_dynamic_api_key(raw_key) is None

    saved = json.loads(settings_path.read_text(encoding="utf-8"))
    stored_key = saved["api_keys"][0]

    assert stored_key["usage_count"] == 0
    assert stored_key["last_used_at"] is None