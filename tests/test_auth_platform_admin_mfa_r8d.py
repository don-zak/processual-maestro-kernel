from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.dialects import postgresql
from starlette.requests import Request

import processual_api.auth.security as security_module
import processual_api.db.session as db_session_module
from processual_api.auth.session_repository import (
    SqlAlchemySessionRepository,
)


class ScalarSession:
    def __init__(self, scalar_values) -> None:
        self.scalar_values = list(scalar_values)
        self.statements = []

    async def scalar(self, statement):
        self.statements.append(statement)
        if not self.scalar_values:
            return None
        return self.scalar_values.pop(0)


class Result:
    def __init__(self, row) -> None:
        self.row = row

    def one_or_none(self):
        return self.row


class IdentityDatabaseSession:
    def __init__(self, row, scalar_values) -> None:
        self.row = row
        self.scalar_values = list(scalar_values)
        self.scalar_statements = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    async def execute(self, statement):
        return Result(self.row)

    async def scalar(self, statement):
        self.scalar_statements.append(statement)
        if not self.scalar_values:
            return None
        return self.scalar_values.pop(0)


def _compiled_sql(statement) -> str:
    return " ".join(
        str(
            statement.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        ).split()
    )


def _request() -> Request:
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
        "role": "client",
        "scopes": ["evaluation"],
        "platform_authorities": ["platform_admin"],
    }


def test_repository_requires_mfa_for_active_platform_admin() -> None:
    platform_authority_id = uuid.uuid4()
    session = ScalarSession((None, None, platform_authority_id))
    repository = SqlAlchemySessionRepository(session)

    required = asyncio.run(
        repository.requires_mfa(
            uuid.UUID("11111111-1111-1111-1111-111111111111")
        )
    )

    assert required is True
    assert len(session.statements) == 3

    sql = _compiled_sql(session.statements[2])

    assert "identity_platform_authorities.id" in sql
    assert (
        "identity_platform_authorities.authority = 'platform_admin'"
        in sql
    )
    assert "identity_platform_authorities.status = 'active'" in sql


def test_repository_does_not_require_mfa_for_revoked_authority_only() -> None:
    session = ScalarSession((None, None, None))
    repository = SqlAlchemySessionRepository(session)

    required = asyncio.run(
        repository.requires_mfa(
            uuid.UUID("22222222-2222-2222-2222-222222222222")
        )
    )

    assert required is False

    sql = _compiled_sql(session.statements[2])

    assert "identity_platform_authorities.status = 'active'" in sql
    assert "status = 'revoked'" not in sql


def test_repository_existing_mfa_factor_still_requires_mfa() -> None:
    session = ScalarSession((uuid.uuid4(), None, None))
    repository = SqlAlchemySessionRepository(session)

    required = asyncio.run(
        repository.requires_mfa(
            uuid.UUID("33333333-3333-3333-3333-333333333333")
        )
    )

    assert required is True


def test_repository_privileged_membership_still_requires_mfa() -> None:
    session = ScalarSession((None, uuid.uuid4(), None))
    repository = SqlAlchemySessionRepository(session)

    required = asyncio.run(
        repository.requires_mfa(
            uuid.UUID("44444444-4444-4444-4444-444444444444")
        )
    )

    assert required is True


def test_active_platform_admin_is_mfa_limited_on_protected_request(
    monkeypatch,
) -> None:
    now = datetime.now(UTC)
    user_id = uuid.uuid4()
    session_id = uuid.uuid4()

    auth_session = SimpleNamespace(
        id=session_id,
        user_id=user_id,
        organization_id=None,
        expires_at=now + timedelta(hours=1),
        revoked_at=None,
        mfa_satisfied_at=None,
    )
    user = SimpleNamespace(id=user_id, status="active")

    database_session = IdentityDatabaseSession(
        (auth_session, user),
        scalar_values=(None, None, uuid.uuid4()),
    )

    monkeypatch.setattr(
        db_session_module,
        "get_session_factory",
        lambda: lambda: database_session,
    )
    monkeypatch.setattr(
        security_module,
        "verify_access_token",
        lambda token: _identity_payload(user_id, session_id),
    )

    current_user = asyncio.run(
        security_module.get_current_user(
            _request(),
            bearer=HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials="signed-token",
            ),
            api_key=None,
            supervisor_session_key=None,
        )
    )

    assert current_user["mfa_pending"] is True
    assert current_user["scopes"] == ["auth:mfa"]
    assert current_user["role"] == "client"
    assert current_user["session_type"] == "identity_user"


def test_satisfied_platform_admin_session_gets_only_evaluation_scope(
    monkeypatch,
) -> None:
    now = datetime.now(UTC)
    user_id = uuid.uuid4()
    session_id = uuid.uuid4()

    auth_session = SimpleNamespace(
        id=session_id,
        user_id=user_id,
        organization_id=None,
        expires_at=now + timedelta(hours=1),
        revoked_at=None,
        mfa_satisfied_at=now,
    )
    user = SimpleNamespace(id=user_id, status="active")

    database_session = IdentityDatabaseSession(
        (auth_session, user),
        scalar_values=(None, None, uuid.uuid4()),
    )

    monkeypatch.setattr(
        db_session_module,
        "get_session_factory",
        lambda: lambda: database_session,
    )
    monkeypatch.setattr(
        security_module,
        "verify_access_token",
        lambda token: _identity_payload(user_id, session_id),
    )

    current_user = asyncio.run(
        security_module.get_current_user(
            _request(),
            bearer=HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials="signed-token",
            ),
            api_key=None,
            supervisor_session_key=None,
        )
    )

    assert current_user["mfa_pending"] is False
    assert current_user["scopes"] == ["evaluation"]
    assert current_user["role"] == "client"
    assert current_user["scopes"] != ["*"]


def test_revoked_platform_authority_claim_cannot_force_or_grant_access(
    monkeypatch,
) -> None:
    now = datetime.now(UTC)
    user_id = uuid.uuid4()
    session_id = uuid.uuid4()

    auth_session = SimpleNamespace(
        id=session_id,
        user_id=user_id,
        organization_id=None,
        expires_at=now + timedelta(hours=1),
        revoked_at=None,
        mfa_satisfied_at=None,
    )
    user = SimpleNamespace(id=user_id, status="active")

    database_session = IdentityDatabaseSession(
        (auth_session, user),
        scalar_values=(None, None, None),
    )

    monkeypatch.setattr(
        db_session_module,
        "get_session_factory",
        lambda: lambda: database_session,
    )
    monkeypatch.setattr(
        security_module,
        "verify_access_token",
        lambda token: _identity_payload(user_id, session_id),
    )

    current_user = asyncio.run(
        security_module.get_current_user(
            _request(),
            bearer=HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials="signed-token",
            ),
            api_key=None,
            supervisor_session_key=None,
        )
    )

    assert current_user["mfa_pending"] is False
    assert current_user["scopes"] == ["evaluation"]
    assert current_user["role"] == "client"
    assert current_user["session_type"] == "identity_user"
