from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from processual_api.auth import security
from processual_api.services.evaluation_grant_authority import (
    DurableEvaluationApiKeyDenied,
)


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/qualification",
            "headers": [],
        }
    )


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        api_keys=[],
        environment="test",
        is_production=False,
        jwt_secret="test-jwt-secret",
        jwt_algorithm="HS256",
        jwt_expire_minutes=60,
    )


def _run(coro):
    return asyncio.run(coro)


def _configure_evaluation_only(monkeypatch) -> None:
    monkeypatch.setattr(security, "settings", _settings())
    monkeypatch.setattr(
        security,
        "_durable_sandbox_api_key_authority_enabled",
        lambda: False,
    )
    monkeypatch.setattr(
        security,
        "_durable_evaluation_api_key_authority_enabled",
        lambda: True,
    )


def test_durable_evaluation_acceptance_precedes_legacy(monkeypatch) -> None:
    _configure_evaluation_only(monkeypatch)
    durable_user = {
        "sub": "eval-user",
        "user_id": "eval-user",
        "client_id": "eval-client",
        "role": "client",
        "auth_method": "api_key",
        "session_type": "evaluation_api_key",
        "entitlement_source": "admin_evaluation_grant",
        "subscription_required": False,
        "scopes": ["read:health"],
        "production_allowed": False,
    }

    async def _durable(_api_key: str):
        return durable_user

    monkeypatch.setattr(security, "verify_durable_evaluation_api_key", _durable)
    monkeypatch.setattr(
        security,
        "verify_dynamic_api_key",
        lambda _api_key: (_ for _ in ()).throw(
            AssertionError("legacy verifier must not run after durable evaluation acceptance")
        ),
    )

    user = _run(
        security.get_current_user(
            _request(), bearer=None, api_key="pmk_eval_secret", supervisor_session_key=None
        )
    )
    assert user == durable_user


def test_durable_evaluation_denial_never_falls_through(monkeypatch) -> None:
    _configure_evaluation_only(monkeypatch)

    async def _durable(_api_key: str):
        raise DurableEvaluationApiKeyDenied("durable_evaluation_grant_inactive")

    monkeypatch.setattr(security, "verify_durable_evaluation_api_key", _durable)
    monkeypatch.setattr(
        security,
        "verify_dynamic_api_key",
        lambda _api_key: (_ for _ in ()).throw(
            AssertionError("legacy verifier must not run after durable evaluation denial")
        ),
    )

    with pytest.raises(HTTPException) as exc:
        _run(
            security.get_current_user(
                _request(), bearer=None, api_key="pmk_eval_secret", supervisor_session_key=None
            )
        )
    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid API key"


def test_durable_evaluation_authority_failure_is_503_without_fallback(monkeypatch) -> None:
    _configure_evaluation_only(monkeypatch)

    async def _durable(_api_key: str):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(security, "verify_durable_evaluation_api_key", _durable)
    monkeypatch.setattr(
        security,
        "verify_dynamic_api_key",
        lambda _api_key: (_ for _ in ()).throw(
            AssertionError("legacy verifier must not run after durable evaluation failure")
        ),
    )

    with pytest.raises(HTTPException) as exc:
        _run(
            security.get_current_user(
                _request(), bearer=None, api_key="pmk_eval_secret", supervisor_session_key=None
            )
        )
    assert exc.value.status_code == 503
    assert exc.value.detail == "Evaluation API key authority unavailable"


def test_durable_no_match_can_use_non_evaluation_legacy_identity(monkeypatch) -> None:
    _configure_evaluation_only(monkeypatch)

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
    monkeypatch.setattr(security, "verify_durable_evaluation_api_key", _durable)
    monkeypatch.setattr(security, "verify_dynamic_api_key", lambda _api_key: legacy_user)

    user = _run(
        security.get_current_user(
            _request(), bearer=None, api_key="pmk_legacy_secret", supervisor_session_key=None
        )
    )
    assert user == legacy_user


def test_legacy_evaluation_identity_is_rejected_when_durable_mode_enabled(monkeypatch) -> None:
    _configure_evaluation_only(monkeypatch)

    async def _durable(_api_key: str):
        return None

    legacy_evaluation = {
        "sub": "legacy-eval-user",
        "user_id": "legacy-eval-user",
        "client_id": "legacy-eval-client",
        "role": "client",
        "auth_method": "api_key",
        "session_type": "api_key",
        "entitlement_source": "admin_evaluation_grant",
        "scopes": ["read:health"],
    }
    monkeypatch.setattr(security, "verify_durable_evaluation_api_key", _durable)
    monkeypatch.setattr(
        security,
        "verify_dynamic_api_key",
        lambda _api_key: legacy_evaluation,
    )

    with pytest.raises(HTTPException) as exc:
        _run(
            security.get_current_user(
                _request(), bearer=None, api_key="pmk_old_eval", supervisor_session_key=None
            )
        )
    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid API key"
