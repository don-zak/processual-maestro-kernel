from __future__ import annotations

import asyncio
import uuid

from sqlalchemy.dialects import postgresql

from processual_api.auth.session_repository import (
    SqlAlchemySessionRepository,
)


class FakeScalarResult:
    def __init__(self, values: tuple[str, ...]) -> None:
        self._values = values

    def all(self) -> list[str]:
        return list(self._values)


class RecordingSession:
    def __init__(self, values: tuple[str, ...]) -> None:
        self.values = values
        self.statements = []

    async def scalars(self, statement):
        self.statements.append(statement)
        return FakeScalarResult(self.values)


def _compiled_sql(statement) -> str:
    return " ".join(
        str(
            statement.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        ).split()
    )


def test_active_platform_authorities_returns_stable_tuple() -> None:
    user_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    session = RecordingSession(("platform_admin",))
    repository = SqlAlchemySessionRepository(session)

    authorities = asyncio.run(
        repository.active_platform_authorities(user_id)
    )

    assert authorities == ("platform_admin",)
    assert len(session.statements) == 1


def test_active_platform_authorities_reads_only_active_user_rows() -> None:
    user_id = uuid.UUID("22222222-2222-2222-2222-222222222222")
    session = RecordingSession(())
    repository = SqlAlchemySessionRepository(session)

    authorities = asyncio.run(
        repository.active_platform_authorities(user_id)
    )

    assert authorities == ()

    sql = _compiled_sql(session.statements[0])

    assert "identity_platform_authorities.authority" in sql
    assert "identity_platform_authorities.user_id =" in sql
    assert str(user_id) in sql
    assert "identity_platform_authorities.status = 'active'" in sql


def test_active_platform_authorities_has_deterministic_ordering() -> None:
    user_id = uuid.UUID("33333333-3333-3333-3333-333333333333")
    session = RecordingSession(("platform_admin",))
    repository = SqlAlchemySessionRepository(session)

    asyncio.run(repository.active_platform_authorities(user_id))

    sql = _compiled_sql(session.statements[0])

    assert (
        "ORDER BY "
        "identity_platform_authorities.authority, "
        "identity_platform_authorities.created_at"
    ) in sql


def test_active_platform_authority_read_is_organization_independent() -> None:
    user_id = uuid.UUID("44444444-4444-4444-4444-444444444444")
    session = RecordingSession(("platform_admin",))
    repository = SqlAlchemySessionRepository(session)

    asyncio.run(repository.active_platform_authorities(user_id))

    sql = _compiled_sql(session.statements[0])

    assert "identity_memberships" not in sql
    assert "organization_id" not in sql


def test_repository_read_does_not_issue_admin_session_contracts() -> None:
    user_id = uuid.UUID("55555555-5555-5555-5555-555555555555")
    session = RecordingSession(("platform_admin",))
    repository = SqlAlchemySessionRepository(session)

    authorities = asyncio.run(
        repository.active_platform_authorities(user_id)
    )

    assert authorities == ("platform_admin",)
    assert not hasattr(repository, "issue_admin_session")
    assert not hasattr(repository, "grant_admin_scopes")
