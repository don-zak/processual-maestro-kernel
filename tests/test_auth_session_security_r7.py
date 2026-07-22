from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from starlette.requests import Request

import processual_api.auth.security as security_module
import processual_api.db.session as db_session_module


class FakeResult:
    def __init__(self, row) -> None:
        self.row = row

    def one_or_none(self):
        return self.row


class FakeDatabaseSession:
    def __init__(self, row) -> None:
        self.row = row

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    async def execute(self, statement):
        return FakeResult(self.row)


def _request():
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/protected",
            "headers": [],
            "client": ("127.0.0.1", 40000),
            "server": ("test", 443),
            "scheme": "https",
        }
    )


def _identity_payload(user_id, session_id):
    return {
        "sub": str(user_id),
        "sid": str(session_id),
        "session_type": "identity_user",
        "organization_id": None,
        "role": "admin",
        "scopes": ["*"],
    }


def test_identity_bearer_rechecks_postgresql_and_ignores_elevated_claims(monkeypatch):
    now = datetime.now(UTC)
    user_id = uuid.uuid4()
    session_id = uuid.uuid4()
    auth_session = SimpleNamespace(
        id=session_id,
        user_id=user_id,
        organization_id=None,
        expires_at=now + timedelta(hours=1),
        revoked_at=None,
    )
    user = SimpleNamespace(id=user_id, status="active")
    monkeypatch.setattr(
        db_session_module,
        "get_session_factory",
        lambda: lambda: FakeDatabaseSession((auth_session, user)),
    )
    monkeypatch.setattr(
        security_module,
        "verify_access_token",
        lambda token: _identity_payload(user_id, session_id),
    )

    current_user = asyncio.run(
        security_module.get_current_user(
            _request(),
            bearer=HTTPAuthorizationCredentials(scheme="Bearer", credentials="signed-token"),
            api_key=None,
            supervisor_session_key=None,
        )
    )

    assert current_user["session_id"] == str(session_id)
    assert current_user["role"] == "client"
    assert current_user["scopes"] == ["evaluation"]


def test_revoked_database_session_invalidates_unexpired_bearer(monkeypatch):
    now = datetime.now(UTC)
    user_id = uuid.uuid4()
    session_id = uuid.uuid4()
    auth_session = SimpleNamespace(
        id=session_id,
        user_id=user_id,
        organization_id=None,
        expires_at=now + timedelta(hours=1),
        revoked_at=now,
    )
    user = SimpleNamespace(id=user_id, status="active")
    monkeypatch.setattr(
        db_session_module,
        "get_session_factory",
        lambda: lambda: FakeDatabaseSession((auth_session, user)),
    )
    monkeypatch.setattr(
        security_module,
        "verify_access_token",
        lambda token: _identity_payload(user_id, session_id),
    )

    with pytest.raises(HTTPException) as raised:
        asyncio.run(
            security_module.get_current_user(
                _request(),
                bearer=HTTPAuthorizationCredentials(scheme="Bearer", credentials="signed-token"),
                api_key=None,
                supervisor_session_key=None,
            )
        )

    assert raised.value.status_code == 401
