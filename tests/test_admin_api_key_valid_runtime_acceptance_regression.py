from __future__ import annotations

import asyncio
import json
import warnings

import pytest

warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated.*",
)

from fastapi.testclient import TestClient  # noqa: E402

import processual_api.middleware.rate_limit as rate_module  # noqa: E402
from processual_api.main import app  # noqa: E402
from processual_api.routers import settings as settings_router  # noqa: E402
from processual_api.services import api_key_store, quota_store  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    async def no_redis():
        return None

    monkeypatch.setattr(rate_module, "get_redis", no_redis)

    app.dependency_overrides.clear()
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def _admin_user() -> dict:
    return {
        "sub": "owner-admin",
        "client_id": "owner-admin",
        "role": "security_admin",
        "session_type": "ui_admin",
        "scopes": ["*"],
    }


def _bind_api_key_runtime_store(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(api_key_store, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(quota_store, "DATA_DIR", tmp_path)


def _create_valid_runtime_api_key(monkeypatch, tmp_path) -> dict:
    _bind_api_key_runtime_store(monkeypatch, tmp_path)

    body = settings_router.ApiKeyCreateRequest(
        category="pilot_client",
        role="client",
        scopes=[
            "read:health",
            "read:adapters",
            "read:governor",
            "run:govern",
        ],
        label="02E valid runtime acceptance key",
        purpose="real valid API key runtime acceptance",
        issued_to="external-runtime-acceptance-pilot",
        quota_limit_override=25,
        expires_at="2026-12-31T00:00:00+00:00",
        client_id="external-runtime-acceptance-client",
        user_id="external-runtime-acceptance-user",
    )

    return asyncio.run(
        settings_router.create_api_key(
            body=body,
            current_user=_admin_user(),
        )
    )


def _stored_owner_key() -> dict:
    raw = settings_router._load_raw("owner-admin")
    keys = raw["api_keys"]

    assert len(keys) == 1
    return keys[0]


def test_valid_generated_api_key_runs_externally_then_fails_after_revoke(
    client,
    monkeypatch,
    tmp_path,
):
    created = _create_valid_runtime_api_key(monkeypatch, tmp_path)
    raw_key = created["api_key"]
    key_id = created["id"]

    assert raw_key.startswith("pmk_")
    assert created["onboarding_usage"]["header"] == "X-API-Key"
    assert created["onboarding_usage"]["example_endpoint"] == "/adapters/status"

    stored_before_use = _stored_owner_key()

    assert stored_before_use["id"] == key_id
    assert stored_before_use["status"] == "enabled"
    assert stored_before_use["usage_count"] == 0
    assert stored_before_use["last_used_at"] is None
    assert stored_before_use["scopes"] == [
        "read:health",
        "read:adapters",
        "read:governor",
        "run:govern",
    ]

    accepted = client.get(
        "/adapters/status",
        headers={
            "X-API-Key": raw_key,
            "X-Request-ID": "admin-apikeys-02e-valid-runtime",
        },
    )

    assert accepted.status_code == 200
    assert "Bearer" not in accepted.request.headers
    assert accepted.request.headers["X-API-Key"] == raw_key
    assert accepted.request.headers["X-Request-ID"] == (
        "admin-apikeys-02e-valid-runtime"
    )

    payload = accepted.json()
    assert "providers" in payload
    assert isinstance(payload["providers"], list)

    stored_after_use = _stored_owner_key()

    assert stored_after_use["id"] == key_id
    assert stored_after_use["status"] == "enabled"
    assert stored_after_use["usage_count"] == 1
    assert stored_after_use["last_used_at"]

    stored_after_use_json = json.dumps(stored_after_use, ensure_ascii=False)
    assert raw_key not in stored_after_use_json
    assert "api_key" not in stored_after_use
    assert stored_after_use["hashed"]

    revoked = asyncio.run(
        settings_router.delete_api_key(
            key_id=key_id,
            current_user=_admin_user(),
        )
    )

    assert revoked["id"] == key_id
    assert revoked["status"] == "revoked"
    assert revoked["revoked_at"]

    rejected = client.get(
        "/adapters/status",
        headers={
            "X-API-Key": raw_key,
            "X-Request-ID": "admin-apikeys-02e-revoked-runtime",
        },
    )

    assert rejected.status_code in {401, 403}
    assert "Bearer" not in rejected.request.headers
    assert rejected.request.headers["X-API-Key"] == raw_key

    stored_after_revoke = _stored_owner_key()

    assert stored_after_revoke["id"] == key_id
    assert stored_after_revoke["status"] == "revoked"
    assert stored_after_revoke["revoked_at"] == revoked["revoked_at"]
    assert stored_after_revoke["usage_count"] == 1
    assert stored_after_revoke["last_used_at"] == stored_after_use["last_used_at"]

    stored_after_revoke_json = json.dumps(stored_after_revoke, ensure_ascii=False)
    assert raw_key not in stored_after_revoke_json
