import asyncio
import copy
import json
from pathlib import Path

from processual_api.routers import settings as settings_router


SETTINGS_PATH = (
    Path(__file__).resolve().parents[1]
    / "processual_api"
    / "routers"
    / "settings.py"
)

SETTINGS_SOURCE = SETTINGS_PATH.read_text(encoding="utf-8")


def _function_block(function_name: str) -> str:
    marker = f"async def {function_name}"
    start = SETTINGS_SOURCE.index(marker)
    next_route = SETTINGS_SOURCE.find("\n@router.", start + len(marker))
    if next_route == -1:
        return SETTINGS_SOURCE[start:]
    return SETTINGS_SOURCE[start:next_route]


def _patch_memory_store(monkeypatch, initial_raw=None):
    saved = {}
    raw = copy.deepcopy(initial_raw or {"api_keys": []})

    def fake_load_raw(user_id: str):
        saved["loaded_user_id"] = user_id
        return copy.deepcopy(raw)

    def fake_save_raw(user_id: str, data: dict):
        saved["saved_user_id"] = user_id
        saved["raw"] = copy.deepcopy(data)

    monkeypatch.setattr(settings_router, "_load_raw", fake_load_raw)
    monkeypatch.setattr(settings_router, "_save_raw", fake_save_raw)

    return saved


def _patch_plan_helpers(monkeypatch):
    monkeypatch.setattr(settings_router, "_resolve_current_plan_id", lambda user_id, raw: "starter")
    monkeypatch.setattr(settings_router, "resolve_plan_id", lambda value: "starter")
    monkeypatch.setattr(
        settings_router,
        "get_plan_policy",
        lambda plan_id: {"id": plan_id, "name": "Starter", "quotas": {"evaluation": 100}},
    )
    monkeypatch.setattr(settings_router, "quota_limit_for_plan", lambda plan_id, scope: 100)


def test_create_api_key_returns_plain_key_once_and_stores_hash_only(monkeypatch):
    _patch_plan_helpers(monkeypatch)
    saved = _patch_memory_store(monkeypatch, {"api_keys": []})

    response = asyncio.run(
        settings_router.create_api_key(
            settings_router.ApiKeyCreateRequest(
                client_id="client_test",
                user_id="runtime_user",
                label="Regression key",
            ),
            current_user={"sub": "owner_user"},
        )
    )

    raw_key = response["api_key"]

    assert raw_key.startswith("pmk_")
    assert response["status"] == "enabled"
    assert response["profile"] == settings_router.CLIENT_KEY_PROFILE
    assert response["scopes"] == settings_router.DEFAULT_API_KEY_SCOPES
    assert response["quota_limit"] == 100
    assert response["quota_used"] == 0

    stored = saved["raw"]["api_keys"][0]
    serialized_store = json.dumps(saved["raw"])

    assert saved["saved_user_id"] == "owner_user"
    assert stored["id"] == response["id"]
    assert stored["client_id"] == "client_test"
    assert stored["user_id"] == "runtime_user"
    assert stored["label"] == "Regression key"
    assert stored["status"] == "enabled"
    assert stored["usage_count"] == 0
    assert stored["last_used_at"] is None
    assert stored["revoked_at"] is None
    assert stored["hashed"] != raw_key
    assert raw_key not in serialized_store


def test_delete_api_key_revokes_without_hard_deleting(monkeypatch):
    saved = _patch_memory_store(
        monkeypatch,
        {
            "api_keys": [
                {
                    "id": "key_1",
                    "status": "enabled",
                    "revoked_at": None,
                    "usage_count": 0,
                }
            ]
        },
    )

    response = asyncio.run(
        settings_router.delete_api_key(
            "key_1",
            current_user={"sub": "owner_user"},
        )
    )

    stored_keys = saved["raw"]["api_keys"]

    assert response["status"] == "revoked"
    assert response["id"] == "key_1"
    assert response["revoked_at"]

    assert len(stored_keys) == 1
    assert stored_keys[0]["id"] == "key_1"
    assert stored_keys[0]["status"] == "revoked"
    assert stored_keys[0]["revoked_at"] == response["revoked_at"]


def test_api_key_settings_routes_require_admin_settings_scope():
    route_expectations = [
        ('@router.get("/api-keys"', "list_api_keys"),
        ('@router.post("/api-keys"', "create_api_key"),
        ('@router.patch("/api-keys/{key_id}/plan"', "update_api_key_plan"),
        ('@router.patch("/api-keys/{key_id}/quota"', "update_api_key_quota"),
        ('@router.delete("/api-keys/{key_id}"', "delete_api_key"),
    ]

    for route_marker, function_name in route_expectations:
        assert route_marker in SETTINGS_SOURCE
        assert "Depends(require_scope(ADMIN_SETTINGS_SCOPE))" in _function_block(function_name)