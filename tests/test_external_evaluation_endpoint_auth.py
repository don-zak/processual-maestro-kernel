from __future__ import annotations

import pytest
from fastapi import HTTPException, Request

from processual_api.auth import security


def _request(method: str, path: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": method,
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
            "scheme": "http",
            "root_path": "",
        }
    )


def _evaluation_identity() -> dict:
    return {
        "sub": "owner-user",
        "user_id": "owner-user",
        "client_id": "external-evaluator",
        "auth_method": "api_key",
        "session_type": "api_key",
        "entitlement_source": "admin_evaluation_grant",
        "evaluation_grant_id": "eval_contract",
        "subscription_required": False,
        "registration_required": False,
        "commercial_quota_required": False,
        "evaluation_access": True,
        "execution_mode": "evaluation_runtime",
        "real_runtime_execution": True,
        "production_allowed": False,
        "allowed_endpoints": [{"method": "GET", "path": "/health/live"}],
        "scopes": ["read:health"],
    }


@pytest.mark.asyncio
async def test_canonical_auth_allows_granted_evaluation_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(
        security,
        "verify_dynamic_api_key",
        lambda raw_key: _evaluation_identity(),
    )
    request = _request("GET", "/health/live")
    identity = await security.get_current_user(
        request,
        bearer=None,
        api_key="pmk_test",
        supervisor_session_key=None,
    )
    assert identity["evaluation_access"] is True
    assert identity["execution_mode"] == "evaluation_runtime"
    assert identity["subscription_required"] is False
    assert identity["commercial_quota_required"] is False
    assert request.state.current_user is identity


@pytest.mark.asyncio
async def test_canonical_auth_rejects_non_granted_evaluation_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(
        security,
        "verify_dynamic_api_key",
        lambda raw_key: _evaluation_identity(),
    )
    request = _request("GET", "/settings")
    with pytest.raises(HTTPException) as exc_info:
        await security.get_current_user(
            request,
            bearer=None,
            api_key="pmk_test",
            supervisor_session_key=None,
        )
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Evaluation API key is not allowed for this endpoint."


@pytest.mark.asyncio
async def test_non_evaluation_api_key_keeps_existing_authentication_path(monkeypatch) -> None:
    ordinary_identity = {
        "sub": "ordinary-user",
        "user_id": "ordinary-user",
        "auth_method": "api_key",
        "session_type": "api_key",
        "entitlement_source": "subscription",
        "scopes": ["read:health"],
    }
    monkeypatch.setattr(
        security,
        "verify_dynamic_api_key",
        lambda raw_key: ordinary_identity,
    )
    request = _request("GET", "/settings")
    identity = await security.get_current_user(
        request,
        bearer=None,
        api_key="pmk_test",
        supervisor_session_key=None,
    )
    assert identity is ordinary_identity
