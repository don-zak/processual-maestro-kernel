from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from processual_api.auth import security

STATIC_TEST_KEY = "pmk_static_env_fallback_test_key"


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "headers": [],
        }
    )


def _run(coro):
    return asyncio.run(coro)


def _patch_static_key_auth(
    monkeypatch,
    *,
    is_production: bool,
    environment: str,
) -> None:
    monkeypatch.setattr(
        security,
        "settings",
        SimpleNamespace(
            api_keys=[STATIC_TEST_KEY],
            environment=environment,
            is_production=is_production,
            jwt_secret="test-jwt-secret",
            jwt_algorithm="HS256",
            jwt_expire_minutes=60,
        ),
    )
    monkeypatch.setattr(security, "verify_dynamic_api_key", lambda api_key: None)
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


def test_env_api_key_fallback_is_allowed_only_in_non_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("ENVIRONMENT", "development")
    _patch_static_key_auth(monkeypatch, is_production=False, environment="development")

    user = _run(
        security.get_current_user(
            _request(),
            bearer=None,
            api_key=STATIC_TEST_KEY,
        )
    )

    assert user["auth_method"] == "api_key"
    assert user["session_type"] == "api_key_env_fallback"
    assert user["api_key_id"] == "env"
    assert user["scopes"] == ["*"]


def test_env_api_key_fallback_is_blocked_when_app_env_is_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ENVIRONMENT", "production")
    _patch_static_key_auth(monkeypatch, is_production=True, environment="production")

    with pytest.raises(HTTPException) as exc:
        _run(
            security.get_current_user(
                _request(),
                bearer=None,
                api_key=STATIC_TEST_KEY,
            )
        )

    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid API key"


def test_env_api_key_fallback_is_blocked_when_environment_is_production_even_without_app_env(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "production")
    _patch_static_key_auth(monkeypatch, is_production=False, environment="development")

    with pytest.raises(HTTPException) as exc:
        _run(
            security.get_current_user(
                _request(),
                bearer=None,
                api_key=STATIC_TEST_KEY,
            )
        )

    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid API key"
