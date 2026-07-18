import json

from processual_api.routers import settings as settings_router
from processual_api.services import api_key_store


def test_settings_load_raw_returns_empty_dict_for_missing_or_corrupt_json(monkeypatch, tmp_path):
    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)

    assert settings_router._load_raw("missing_user") == {}

    corrupt_path = settings_router._settings_path("corrupt_user")
    corrupt_path.write_text("{not-valid-json", encoding="utf-8")

    assert settings_router._load_raw("corrupt_user") == {}


def test_settings_save_raw_uses_tmp_replace_and_cleans_tmp_file(monkeypatch, tmp_path):
    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)

    user_id = "settings_save_test"
    path = settings_router._settings_path(user_id)
    tmp_file = path.with_suffix(path.suffix + ".tmp")
    backup_file = path.with_suffix(path.suffix + ".bak")

    settings_router._save_raw(
        user_id,
        {
            "general": {"language": "en"},
            "api_keys": [],
        },
    )

    saved = json.loads(path.read_text(encoding="utf-8"))

    assert saved["general"]["language"] == "en"
    assert saved["api_keys"] == []
    assert path.exists()
    assert not tmp_file.exists()
    assert not backup_file.exists()


def test_settings_save_raw_creates_backup_when_replacing_existing_file(monkeypatch, tmp_path):
    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)

    user_id = "settings_backup_test"
    path = settings_router._settings_path(user_id)
    tmp_file = path.with_suffix(path.suffix + ".tmp")
    backup_file = path.with_suffix(path.suffix + ".bak")

    original = {
        "general": {"language": "ar"},
        "api_keys": [{"id": "old_key", "status": "enabled"}],
    }
    updated = {
        "general": {"language": "fr"},
        "api_keys": [{"id": "new_key", "status": "enabled"}],
    }

    settings_router._save_raw(user_id, original)
    settings_router._save_raw(user_id, updated)

    saved = json.loads(path.read_text(encoding="utf-8"))
    backup = json.loads(backup_file.read_text(encoding="utf-8"))

    assert saved == updated
    assert backup == original
    assert not tmp_file.exists()


def test_api_key_store_safe_load_json_returns_empty_dict_for_corrupt_json(tmp_path):
    path = tmp_path / "settings_api_key_user.json"
    path.write_text("{not-valid-json", encoding="utf-8")

    assert api_key_store._safe_load_json(path) == {}


def test_api_key_store_safe_save_json_uses_tmp_replace_and_cleans_tmp_file(tmp_path):
    path = tmp_path / "settings_api_key_user.json"
    tmp_file = path.with_suffix(path.suffix + ".tmp")

    api_key_store._safe_save_json(
        path,
        {
            "api_keys": [
                {
                    "id": "key_1",
                    "status": "enabled",
                    "usage_count": 1,
                }
            ]
        },
    )

    saved = json.loads(path.read_text(encoding="utf-8"))

    assert saved["api_keys"][0]["id"] == "key_1"
    assert saved["api_keys"][0]["usage_count"] == 1
    assert path.exists()
    assert not tmp_file.exists()
