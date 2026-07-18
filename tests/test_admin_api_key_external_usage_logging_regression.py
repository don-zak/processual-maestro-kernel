from __future__ import annotations

import asyncio
import json
import warnings
from pathlib import Path

import pytest

warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated.*",
)

from fastapi.testclient import TestClient  # noqa: E402

import processual_api.middleware.rate_limit as rate_module  # noqa: E402
from processual_api.main import app  # noqa: E402
from processual_api.routers import settings as settings_router  # noqa: E402
from processual_api.services import (  # noqa: E402
    api_key_store,
    quota_store,
    usage_log_store,  # noqa: E402
)


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


def _bind_runtime_stores(monkeypatch, tmp_path: Path) -> Path:
    usage_log_path = tmp_path / "usage_logs.jsonl"

    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(api_key_store, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(quota_store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(usage_log_store, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(usage_log_store, "_USAGE_LOG_PATH", usage_log_path)

    return usage_log_path


def _create_integration_api_key(monkeypatch, tmp_path: Path) -> tuple[dict, Path]:
    usage_log_path = _bind_runtime_stores(monkeypatch, tmp_path)

    body = settings_router.ApiKeyCreateRequest(
        category="service_integration",
        role="client",
        scopes=[
            "read:health",
            "read:adapters",
            "read:governor",
            "run:govern",
        ],
        label="02F service integration API key",
        purpose="server-to-server integration usage logging proof",
        issued_to="external-service-integration-client",
        quota_limit_override=25,
        expires_at="2026-12-31T00:00:00+00:00",
        client_id="integration-client-02f",
        user_id="integration-user-02f",
    )

    created = asyncio.run(
        settings_router.create_api_key(
            body=body,
            current_user=_admin_user(),
        )
    )

    return created, usage_log_path


def _stored_owner_key() -> dict:
    raw = settings_router._load_raw("owner-admin")
    keys = raw["api_keys"]

    assert len(keys) == 1
    return keys[0]


def _load_usage_records(path: Path) -> list[dict]:
    assert path.exists()
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_service_integration_api_key_records_safe_external_usage_log(
    client,
    monkeypatch,
    tmp_path,
):
    created, usage_log_path = _create_integration_api_key(monkeypatch, tmp_path)
    raw_key = created["api_key"]
    key_id = created["id"]

    assert raw_key.startswith("pmk_")
    assert created["category"] == "service_integration"
    assert created["role"] == "client"
    assert created["purpose"] == "server-to-server integration usage logging proof"
    assert created["issued_to"] == "external-service-integration-client"
    assert created["onboarding_usage"]["header"] == "X-API-Key"

    stored_before_use = _stored_owner_key()
    stored_hash = stored_before_use["hashed"]

    assert stored_before_use["id"] == key_id
    assert stored_before_use["status"] == "enabled"
    assert stored_before_use["client_id"] == "integration-client-02f"
    assert stored_before_use["user_id"] == "integration-user-02f"
    assert stored_before_use["usage_count"] == 0
    assert stored_before_use["last_used_at"] is None
    assert raw_key not in json.dumps(stored_before_use, ensure_ascii=False)
    assert "api_key" not in stored_before_use
    assert stored_hash

    accepted = client.get(
        "/adapters/status",
        headers={
            "X-API-Key": raw_key,
            "X-Request-ID": "admin-apikeys-02f-integration-usage",
        },
    )

    assert accepted.status_code == 200
    assert "Bearer" not in accepted.request.headers
    assert accepted.request.headers["X-API-Key"] == raw_key

    payload = accepted.json()
    assert "providers" in payload
    assert isinstance(payload["providers"], list)

    stored_after_use = _stored_owner_key()

    assert stored_after_use["usage_count"] == 1
    assert stored_after_use["last_used_at"]

    records = _load_usage_records(usage_log_path)

    assert len(records) == 1

    record = records[0]
    record_json = json.dumps(record, ensure_ascii=False)

    assert record["request_id"] == "admin-apikeys-02f-integration-usage"
    assert record["client_id"] == "integration-client-02f"
    assert record["user_id"] == "owner-admin"
    assert record["api_key_id"] == key_id
    assert record["api_key_prefix"] == created["prefix"]
    assert record["auth_method"] == "api_key"
    assert record["session_type"] == "api_key"
    assert record["method"] == "GET"
    assert record["endpoint"] == "/adapters/status"
    assert record["status_code"] == 200
    assert record["role"] == "client"
    assert isinstance(record["latency_ms"], float)

    assert raw_key not in record_json
    assert stored_hash not in record_json
    assert "hashed" not in record
    assert "api_key" not in record

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
            "X-Request-ID": "admin-apikeys-02f-revoked-integration-usage",
        },
    )

    assert rejected.status_code in {401, 403}
    assert "Bearer" not in rejected.request.headers
    assert rejected.request.headers["X-API-Key"] == raw_key

    records_after_revoke = _load_usage_records(usage_log_path)
    records_after_revoke_json = json.dumps(records_after_revoke, ensure_ascii=False)

    assert len(records_after_revoke) == 1
    assert raw_key not in records_after_revoke_json
    assert stored_hash not in records_after_revoke_json

    stored_after_revoke = _stored_owner_key()

    assert stored_after_revoke["status"] == "revoked"
    assert stored_after_revoke["usage_count"] == 1
    assert stored_after_revoke["last_used_at"] == stored_after_use["last_used_at"]
