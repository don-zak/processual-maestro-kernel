from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from processual_api.auth import security
from processual_api.services.sandbox_api_key_authority import DurableSandboxApiKeyDenied


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/qualification",
            "headers": [],
        }
    )


def _run(coro):
    return asyncio.run(coro)


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        api_keys=[],
        environment="test",
        is_production=False,
        jwt_secret="test-jwt-secret",
        jwt_algorithm="HS256",
        jwt_expire_minutes=60,
    )


def test_durable_acceptance_precedes_legacy(monkeypatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://maestro:test@127.0.0.1:5432/qualification",
    )
    monkeypatch.setattr(security, "settings", _settings())
    durable_user = {
        "sub": "user-01",
        "user_id": "user-01",
        "client_id": "customer-01",
        "role": "client",
        "auth_method": "api_key",
        "session_type": "sandbox_api_key",
        "environment": "sandbox",
        "scopes": ["read:health"],
        "production_allowed": False,
        "runtime_connector_approved": False,
    }

    async def _durable(_api_key: str):
        return durable_user

    monkeypatch.setattr(security, "verify_durable_sandbox_api_key", _durable)

    def _legacy(_api_key: str):
        raise AssertionError("legacy verifier must not run after durable acceptance")

    monkeypatch.setattr(security, "verify_dynamic_api_key", _legacy)

    user = _run(
        security.get_current_user(
            _request(),
            bearer=None,
            api_key="pmk_sandbox_secret",
            supervisor_session_key=None,
        )
    )

    assert user == durable_user


def test_durable_denial_never_falls_through_to_legacy(monkeypatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://maestro:test@127.0.0.1:5432/qualification",
    )
    monkeypatch.setattr(security, "settings", _settings())

    async def _durable(_api_key: str):
        raise DurableSandboxApiKeyDenied("durable_sandbox_subscription_not_active")

    monkeypatch.setattr(security, "verify_durable_sandbox_api_key", _durable)

    def _legacy(_api_key: str):
        raise AssertionError("legacy verifier must not run after durable denial")

    monkeypatch.setattr(security, "verify_dynamic_api_key", _legacy)

    with pytest.raises(HTTPException) as exc:
        _run(
            security.get_current_user(
                _request(),
                bearer=None,
                api_key="pmk_sandbox_secret",
                supervisor_session_key=None,
            )
        )

    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid API key"


def test_durable_authority_failure_is_service_unavailable_and_fail_closed(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://maestro:test@127.0.0.1:5432/qualification",
    )
    monkeypatch.setattr(security, "settings", _settings())

    async def _durable(_api_key: str):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(security, "verify_durable_sandbox_api_key", _durable)

    def _legacy(_api_key: str):
        raise AssertionError("legacy verifier must not run after durable DB failure")

    monkeypatch.setattr(security, "verify_dynamic_api_key", _legacy)

    with pytest.raises(HTTPException) as exc:
        _run(
            security.get_current_user(
                _request(),
                bearer=None,
                api_key="pmk_sandbox_secret",
                supervisor_session_key=None,
            )
        )

    assert exc.value.status_code == 503
    assert exc.value.detail == "Sandbox API key authority unavailable"


def test_only_durable_no_match_can_fall_through_to_legacy(monkeypatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://maestro:test@127.0.0.1:5432/qualification",
    )
    monkeypatch.setattr(security, "settings", _settings())

    async def _durable(_api_key: str):
        return None

    legacy_user = {
        "sub": "legacy-user",
        "user_id": "legacy-user",
        "client_id": "legacy-client",
        "role": "client",
        "auth_method": "api_key",
        "session_type": "api_key",
        "scopes": ["read:health"],
    }
    monkeypatch.setattr(security, "verify_durable_sandbox_api_key", _durable)
    monkeypatch.setattr(security, "verify_dynamic_api_key", lambda _api_key: legacy_user)

    user = _run(
        security.get_current_user(
            _request(),
            bearer=None,
            api_key="pmk_legacy_secret",
            supervisor_session_key=None,
        )
    )

    assert user == legacy_user


def test_explicit_local_disable_does_not_require_durable_database(monkeypatch) -> None:
    monkeypatch.setenv("PMK_DURABLE_SANDBOX_API_KEYS", "false")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://maestro:test@127.0.0.1:5432/qualification",
    )
    monkeypatch.setattr(security, "settings", _settings())

    async def _durable(_api_key: str):
        raise AssertionError("explicitly disabled durable authority must not run")

    legacy_user = {
        "sub": "legacy-user",
        "user_id": "legacy-user",
        "client_id": "legacy-client",
        "role": "client",
        "auth_method": "api_key",
        "session_type": "api_key",
        "scopes": ["read:health"],
    }
    monkeypatch.setattr(security, "verify_durable_sandbox_api_key", _durable)
    monkeypatch.setattr(security, "verify_dynamic_api_key", lambda _api_key: legacy_user)

    user = _run(
        security.get_current_user(
            _request(),
            bearer=None,
            api_key="pmk_legacy_secret",
            supervisor_session_key=None,
        )
    )

    assert user == legacy_user
