from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql

import processual_api.auth.security as security_module
import processual_api.db.session as db_session_module


class Result:
    def __init__(self, row) -> None:
        self.row = row

    def one_or_none(self):
        return self.row


class DatabaseSession:
    def __init__(self, row) -> None:
        self.row = row
        self.statements = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    async def execute(self, statement):
        self.statements.append(statement)
        return Result(self.row)


def _current_user(
    *,
    user_id: uuid.UUID | None = None,
    session_id: uuid.UUID | None = None,
    session_type: str = "identity_user",
) -> dict:
    resolved_user_id = user_id or uuid.uuid4()
    resolved_session_id = session_id or uuid.uuid4()

    return {
        "sub": str(resolved_user_id),
        "user_id": str(resolved_user_id),
        "session_id": str(resolved_session_id),
        "session_type": session_type,
        "role": "client",
        "scopes": ["evaluation"],
        "platform_authorities": ["platform_admin"],
    }


def _compiled_sql(statement) -> str:
    return " ".join(
        str(
            statement.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        ).split()
    )


def test_platform_admin_step_up_accepts_active_authority_and_recent_mfa(
    monkeypatch,
) -> None:
    now = datetime.now(UTC)
    user_id = uuid.uuid4()
    session_id = uuid.uuid4()

    auth_session = SimpleNamespace(
        id=session_id,
        user_id=user_id,
        revoked_at=None,
        expires_at=now + timedelta(hours=1),
        mfa_satisfied_at=now - timedelta(seconds=60),
    )
    authority = SimpleNamespace(
        user_id=user_id,
        authority="platform_admin",
        status="active",
    )

    database_session = DatabaseSession((auth_session, authority))

    monkeypatch.setattr(
        db_session_module,
        "get_session_factory",
        lambda: lambda: database_session,
    )

    dependency = security_module.require_platform_admin_step_up(
        max_age_seconds=300
    )

    current_user = _current_user(
        user_id=user_id,
        session_id=session_id,
    )

    result = asyncio.run(dependency(current_user=current_user))

    assert result is current_user
    assert result["role"] == "client"
    assert result["scopes"] == ["evaluation"]

    sql = _compiled_sql(database_session.statements[0])

    assert "identity_platform_authorities" in sql
    assert (
        "identity_platform_authorities.authority = 'platform_admin'"
        in sql
    )
    assert "identity_platform_authorities.status = 'active'" in sql
    assert str(user_id) in sql
    assert str(session_id) in sql


def test_platform_admin_step_up_rejects_missing_active_authority(
    monkeypatch,
) -> None:
    database_session = DatabaseSession(None)

    monkeypatch.setattr(
        db_session_module,
        "get_session_factory",
        lambda: lambda: database_session,
    )

    dependency = security_module.require_platform_admin_step_up(300)

    with pytest.raises(HTTPException) as raised:
        asyncio.run(
            dependency(
                current_user=_current_user(),
            )
        )

    assert raised.value.status_code == 403
    assert (
        raised.value.detail
        == "Active platform administrator authority required."
    )


def test_platform_admin_step_up_rejects_stale_mfa(
    monkeypatch,
) -> None:
    now = datetime.now(UTC)
    user_id = uuid.uuid4()
    session_id = uuid.uuid4()

    auth_session = SimpleNamespace(
        id=session_id,
        user_id=user_id,
        revoked_at=None,
        expires_at=now + timedelta(hours=1),
        mfa_satisfied_at=now - timedelta(seconds=301),
    )
    authority = SimpleNamespace(
        user_id=user_id,
        authority="platform_admin",
        status="active",
    )

    monkeypatch.setattr(
        db_session_module,
        "get_session_factory",
        lambda: lambda: DatabaseSession(
            (auth_session, authority)
        ),
    )

    dependency = security_module.require_platform_admin_step_up(300)

    with pytest.raises(HTTPException) as raised:
        asyncio.run(
            dependency(
                current_user=_current_user(
                    user_id=user_id,
                    session_id=session_id,
                )
            )
        )

    assert raised.value.status_code == 403
    assert raised.value.detail == "Recent MFA verification required."


def test_platform_admin_step_up_rejects_unsatisfied_mfa(
    monkeypatch,
) -> None:
    now = datetime.now(UTC)
    user_id = uuid.uuid4()
    session_id = uuid.uuid4()

    auth_session = SimpleNamespace(
        id=session_id,
        user_id=user_id,
        revoked_at=None,
        expires_at=now + timedelta(hours=1),
        mfa_satisfied_at=None,
    )
    authority = SimpleNamespace(
        user_id=user_id,
        authority="platform_admin",
        status="active",
    )

    monkeypatch.setattr(
        db_session_module,
        "get_session_factory",
        lambda: lambda: DatabaseSession(
            (auth_session, authority)
        ),
    )

    dependency = security_module.require_platform_admin_step_up(300)

    with pytest.raises(HTTPException) as raised:
        asyncio.run(
            dependency(
                current_user=_current_user(
                    user_id=user_id,
                    session_id=session_id,
                )
            )
        )

    assert raised.value.status_code == 403
    assert raised.value.detail == "Recent MFA verification required."


@pytest.mark.parametrize(
    "session_updates",
    (
        {"revoked_at": datetime.now(UTC)},
        {"expires_at": datetime.now(UTC) - timedelta(seconds=1)},
    ),
)
def test_platform_admin_step_up_rejects_invalid_session(
    monkeypatch,
    session_updates,
) -> None:
    now = datetime.now(UTC)
    user_id = uuid.uuid4()
    session_id = uuid.uuid4()

    values = {
        "id": session_id,
        "user_id": user_id,
        "revoked_at": None,
        "expires_at": now + timedelta(hours=1),
        "mfa_satisfied_at": now,
    }
    values.update(session_updates)

    auth_session = SimpleNamespace(**values)
    authority = SimpleNamespace(
        user_id=user_id,
        authority="platform_admin",
        status="active",
    )

    monkeypatch.setattr(
        db_session_module,
        "get_session_factory",
        lambda: lambda: DatabaseSession(
            (auth_session, authority)
        ),
    )

    dependency = security_module.require_platform_admin_step_up(300)

    with pytest.raises(HTTPException) as raised:
        asyncio.run(
            dependency(
                current_user=_current_user(
                    user_id=user_id,
                    session_id=session_id,
                )
            )
        )

    assert raised.value.status_code == 403
    assert raised.value.detail == "Recent MFA verification required."


def test_platform_admin_step_up_rejects_non_identity_session() -> None:
    dependency = security_module.require_platform_admin_step_up(300)

    with pytest.raises(HTTPException) as raised:
        asyncio.run(
            dependency(
                current_user=_current_user(
                    session_type="ui_admin",
                )
            )
        )

    assert raised.value.status_code == 403
    assert raised.value.detail == "Identity session required."


def test_platform_admin_step_up_ignores_forged_jwt_authority_claim(
    monkeypatch,
) -> None:
    database_session = DatabaseSession(None)

    monkeypatch.setattr(
        db_session_module,
        "get_session_factory",
        lambda: lambda: database_session,
    )

    current_user = _current_user()
    current_user["platform_authorities"] = ["platform_admin"]
    current_user["role"] = "admin"
    current_user["scopes"] = ["*"]

    dependency = security_module.require_platform_admin_step_up(300)

    with pytest.raises(HTTPException) as raised:
        asyncio.run(
            dependency(current_user=current_user)
        )

    assert raised.value.status_code == 403
    assert (
        raised.value.detail
        == "Active platform administrator authority required."
    )


@pytest.mark.parametrize(
    "unsafe_seconds",
    (
        0,
        30,
        59,
        1801,
        3600,
    ),
)
def test_platform_admin_step_up_rejects_unsafe_lifetime(
    unsafe_seconds,
) -> None:
    with pytest.raises(ValueError):
        security_module.require_platform_admin_step_up(
            unsafe_seconds
        )


def test_platform_admin_step_up_uses_configured_default(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        security_module.settings,
        "auth_mfa_step_up_seconds",
        420,
    )

    dependency = security_module.require_platform_admin_step_up()

    assert callable(dependency)


def test_platform_admin_step_up_never_grants_admin_shape(
    monkeypatch,
) -> None:
    now = datetime.now(UTC)
    user_id = uuid.uuid4()
    session_id = uuid.uuid4()

    auth_session = SimpleNamespace(
        id=session_id,
        user_id=user_id,
        revoked_at=None,
        expires_at=now + timedelta(hours=1),
        mfa_satisfied_at=now,
    )
    authority = SimpleNamespace(
        user_id=user_id,
        authority="platform_admin",
        status="active",
    )

    monkeypatch.setattr(
        db_session_module,
        "get_session_factory",
        lambda: lambda: DatabaseSession(
            (auth_session, authority)
        ),
    )

    current_user = _current_user(
        user_id=user_id,
        session_id=session_id,
    )

    dependency = security_module.require_platform_admin_step_up(300)
    result = asyncio.run(dependency(current_user=current_user))

    assert result["role"] == "client"
    assert result["session_type"] == "identity_user"
    assert result["scopes"] == ["evaluation"]
    assert result["scopes"] != ["*"]
    assert result.get("is_admin") is None
