from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from processual_api.auth import security
from processual_api.services import api_key_store, legacy_api_key_mode

RAW_KEY = "pmk_legacy_cutover_qualification_secret"


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/qualification",
            "headers": [],
        }
    )


def _security_settings(*, production: bool) -> SimpleNamespace:
    return SimpleNamespace(
        api_keys=[],
        environment="production" if production else "test",
        is_production=production,
        jwt_secret="test-jwt-secret",
        jwt_algorithm="HS256",
        jwt_expire_minutes=60,
    )


def _mode_settings(*, production: bool) -> SimpleNamespace:
    return SimpleNamespace(
        environment="production" if production else "test",
        is_production=production,
    )


def _write_legacy_key(tmp_path) -> None:
    payload = {
        "client_id": "legacy-client",
        "api_keys": [
            {
                "id": "legacy-key-1",
                "client_id": "legacy-client",
                "hashed": security._pbkdf2_hash_api_key(RAW_KEY),
                "scopes": ["read:health"],
                "status": "enabled",
                "created_at": datetime.now(UTC).isoformat(),
                "last_used_at": None,
                "usage_count": 0,
                "expires_at": None,
                "revoked_at": None,
            }
        ],
    }
    (tmp_path / "settings_legacy-user.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )


def _configure(monkeypatch, tmp_path, *, production: bool) -> None:
    monkeypatch.setattr(api_key_store, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(security, "settings", _security_settings(production=production))
    monkeypatch.setattr(
        legacy_api_key_mode,
        "settings",
        _mode_settings(production=production),
    )
    monkeypatch.setattr(
        security,
        "_durable_sandbox_api_key_authority_enabled",
        lambda: False,
    )
    monkeypatch.setattr(
        security,
        "_durable_evaluation_api_key_authority_enabled",
        lambda: False,
    )
    monkeypatch.setenv("APP_ENV", "production" if production else "test")
    monkeypatch.setenv("ENVIRONMENT", "production" if production else "test")
    monkeypatch.setenv("PMK_LEGACY_DYNAMIC_API_KEYS", "true")


def test_nonproduction_transition_can_authenticate_legacy_dynamic_key(
    monkeypatch,
    tmp_path,
) -> None:
    _write_legacy_key(tmp_path)
    _configure(monkeypatch, tmp_path, production=False)

    user = asyncio.run(
        security.get_current_user(
            _request(),
            bearer=None,
            api_key=RAW_KEY,
            supervisor_session_key=None,
        )
    )

    assert user["session_type"] == "api_key"
    assert user["client_id"] == "legacy-client"
    saved = json.loads((tmp_path / "settings_legacy-user.json").read_text("utf-8"))
    assert saved["api_keys"][0]["usage_count"] == 1


def test_production_rejects_legacy_dynamic_key_even_when_flag_requests_enable(
    monkeypatch,
    tmp_path,
) -> None:
    _write_legacy_key(tmp_path)
    _configure(monkeypatch, tmp_path, production=True)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            security.get_current_user(
                _request(),
                bearer=None,
                api_key=RAW_KEY,
                supervisor_session_key=None,
            )
        )

    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid API key"
    saved = json.loads((tmp_path / "settings_legacy-user.json").read_text("utf-8"))
    assert saved["api_keys"][0]["usage_count"] == 0
    assert saved["api_keys"][0]["last_used_at"] is None


def test_production_store_direct_call_is_also_fail_closed(monkeypatch, tmp_path) -> None:
    _write_legacy_key(tmp_path)
    _configure(monkeypatch, tmp_path, production=True)

    assert api_key_store.verify_dynamic_api_key(RAW_KEY) is None
