from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from processual_api.auth.mfa_repository import SqlAlchemyMfaRepository, SqlAlchemyMfaUnitOfWork
from processual_api.auth.recovery_email_verification_repository import (
    SqlAlchemyRecoveryEmailVerificationRepository,
    SqlAlchemyRecoveryEmailVerificationUnitOfWork,
)
from processual_api.auth.session_repository import (
    SqlAlchemySessionRepository,
    SqlAlchemySessionUnitOfWork,
)


class ScalarResult:
    def __init__(self, values):
        self._values = list(values)

    def all(self):
        return list(self._values)


class ExecuteResult:
    def __init__(self, row=None):
        self._row = row

    def one_or_none(self):
        return self._row


class FakeAsyncSession:
    def __init__(self, *, scalar_values=(), scalars_values=(), execute_rows=()):
        self.scalar_values = list(scalar_values)
        self.scalars_values = list(scalars_values)
        self.execute_rows = list(execute_rows)
        self.scalar_statements = []
        self.scalars_statements = []
        self.execute_statements = []
        self.added = []
        self.added_many = []
        self.commits = 0
        self.rollbacks = 0
        self.closes = 0

    async def scalar(self, statement):
        self.scalar_statements.append(statement)
        return self.scalar_values.pop(0) if self.scalar_values else None

    async def scalars(self, statement):
        self.scalars_statements.append(statement)
        values = self.scalars_values.pop(0) if self.scalars_values else ()
        return ScalarResult(values)

    async def execute(self, statement):
        self.execute_statements.append(statement)
        row = self.execute_rows.pop(0) if self.execute_rows else None
        return ExecuteResult(row)

    def add(self, value):
        self.added.append(value)

    def add_all(self, values):
        self.added_many.extend(list(values))

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1

    async def close(self):
        self.closes += 1


def test_mfa_repository_statuses_counts_and_mutations() -> None:
    user_id = uuid.uuid4()
    factor_id = uuid.uuid4()
    session = FakeAsyncSession(
        scalar_values=[uuid.uuid4(), 0],
        scalars_values=[("pending", "active", "active")],
    )
    repository = SqlAlchemyMfaRepository(session)

    assert asyncio.run(repository.is_required_by_role(user_id)) is True
    assert asyncio.run(repository.factor_statuses(user_id)) == (True, True)
    assert asyncio.run(repository.recovery_codes_remaining(factor_id)) == 0

    disabled_at = datetime(2026, 8, 13, tzinfo=UTC)
    asyncio.run(repository.disable_pending_factors(user_id, disabled_at=disabled_at))
    asyncio.run(
        repository.revoke_other_sessions(
            user_id=user_id,
            current_session_id=uuid.uuid4(),
            revoked_at=disabled_at,
            reason="mfa_enrolled",
        )
    )
    assert len(session.execute_statements) == 2

    repository.add_pending_factor(
        factor_id=factor_id,
        user_id=user_id,
        label="Authenticator",
        ciphertext=b"secret",
        key_version="v1",
    )
    factor = session.added[-1]
    assert factor.id == factor_id
    assert factor.user_id == user_id
    assert factor.status == "pending"
    assert factor.factor_type == "totp"

    asyncio.run(repository.replace_recovery_codes(factor_id, code_hashes=("h1", "h2")))
    assert len(session.execute_statements) == 3
    assert [row.code_hash for row in session.added_many] == ["h1", "h2"]
    assert all(row.factor_id == factor_id for row in session.added_many)


def test_mfa_unit_of_work_commit_and_rollback_contracts() -> None:
    session = FakeAsyncSession()
    uow = SqlAlchemyMfaUnitOfWork(lambda: session)

    entered = asyncio.run(uow.__aenter__())
    assert entered is uow
    assert isinstance(uow.repository, SqlAlchemyMfaRepository)
    asyncio.run(uow.commit())
    asyncio.run(uow.__aexit__(None, None, None))
    assert session.commits == 1
    assert session.rollbacks == 0
    assert session.closes == 1

    session2 = FakeAsyncSession()
    uow2 = SqlAlchemyMfaUnitOfWork(lambda: session2)
    asyncio.run(uow2.__aenter__())
    asyncio.run(uow2.__aexit__(RuntimeError, RuntimeError("boom"), None))
    assert session2.rollbacks == 1
    assert session2.closes == 1

    with pytest.raises(RuntimeError, match="not active"):
        asyncio.run(SqlAlchemyMfaUnitOfWork(lambda: session).commit())


def test_session_repository_authority_mfa_and_refresh_rotation() -> None:
    user_id = uuid.uuid4()
    session_id = uuid.uuid4()
    org_id = uuid.uuid4()
    session = FakeAsyncSession(
        scalar_values=[org_id, None, uuid.uuid4(), None],
        scalars_values=[("platform_admin", "platform_supervisor")],
    )
    repository = SqlAlchemySessionRepository(session)

    assert asyncio.run(repository.active_organization_id(user_id)) == org_id
    assert asyncio.run(repository.active_platform_authorities(user_id)) == (
        "platform_admin",
        "platform_supervisor",
    )
    assert asyncio.run(repository.requires_mfa(user_id)) is True

    now = datetime(2026, 8, 13, 10, 0, tzinfo=UTC)
    expires = datetime(2026, 8, 14, 10, 0, tzinfo=UTC)
    repository.add_session(
        session_id=session_id,
        user_id=user_id,
        organization_id=org_id,
        refresh_family_id=uuid.uuid4(),
        refresh_token_id=uuid.uuid4(),
        refresh_token_hash="hash-1",
        authenticated_at=now,
        expires_at=expires,
        mfa_satisfied_at=now,
    )
    assert len(session.added) == 2
    auth_session, refresh = session.added
    assert auth_session.id == session_id
    assert auth_session.organization_id == org_id
    assert auth_session.mfa_satisfied_at == now
    assert refresh.session_id == session_id
    assert refresh.token_hash == "hash-1"

    previous = SimpleNamespace(
        id=uuid.uuid4(),
        session_id=session_id,
        consumed_at=None,
    )
    repository.rotate_refresh_token(
        previous=previous,
        token_id=uuid.uuid4(),
        token_hash="hash-2",
        rotated_at=now,
        expires_at=expires,
    )
    assert previous.consumed_at == now
    rotated = session.added[-1]
    assert rotated.parent_token_id == previous.id
    assert rotated.token_hash == "hash-2"


def test_session_repository_refresh_revoke_and_views() -> None:
    user_id = uuid.uuid4()
    auth_session = SimpleNamespace(
        id=uuid.uuid4(),
        revoked_at=None,
        revoke_reason=None,
    )
    refresh = SimpleNamespace(reuse_detected_at=None)
    row = (SimpleNamespace(id="rt"), auth_session, SimpleNamespace(id=user_id))
    now = datetime(2026, 8, 13, tzinfo=UTC)
    visible = SimpleNamespace(
        id=uuid.uuid4(),
        authenticated_at=now,
        last_seen_at=now,
        expires_at=now,
    )
    session = FakeAsyncSession(
        execute_rows=[row],
        scalars_values=[(visible,)],
    )
    repository = SqlAlchemySessionRepository(session)

    principals = asyncio.run(repository.refresh_principals_for_update("hash"))
    assert principals == row

    asyncio.run(
        repository.revoke_family(
            auth_session,
            revoked_at=now,
            reason="reuse",
            reuse_token=refresh,
        )
    )
    assert auth_session.revoked_at == now
    assert auth_session.revoke_reason == "reuse"
    assert refresh.reuse_detected_at == now

    asyncio.run(
        repository.revoke_all_for_user(
            user_id,
            revoked_at=now,
            reason="security_reset",
        )
    )
    assert len(session.execute_statements) == 3

    views = asyncio.run(repository.sessions_for_user(user_id))
    assert len(views) == 1
    assert views[0].id == visible.id
    assert views[0].authenticated_at == now


def test_session_unit_of_work_lifecycle() -> None:
    committed = FakeAsyncSession()
    uow = SqlAlchemySessionUnitOfWork(lambda: committed)
    asyncio.run(uow.__aenter__())
    asyncio.run(uow.commit())
    asyncio.run(uow.__aexit__(None, None, None))
    assert committed.commits == 1
    assert committed.rollbacks == 0
    assert committed.closes == 1

    uncommitted = FakeAsyncSession()
    uow2 = SqlAlchemySessionUnitOfWork(lambda: uncommitted)
    asyncio.run(uow2.__aenter__())
    asyncio.run(uow2.__aexit__(None, None, None))
    assert uncommitted.rollbacks == 1
    assert uncommitted.closes == 1

    with pytest.raises(RuntimeError, match="not active"):
        asyncio.run(SqlAlchemySessionUnitOfWork(lambda: committed).commit())


def test_recovery_email_repository_invalidates_and_adds_delivery() -> None:
    user_id = uuid.uuid4()
    rows = [SimpleNamespace(consumed_at=None), SimpleNamespace(consumed_at=None)]
    session = FakeAsyncSession(scalars_values=[rows])
    repository = SqlAlchemyRecoveryEmailVerificationRepository(session)
    now = datetime(2026, 8, 13, tzinfo=UTC)

    count = asyncio.run(
        repository.invalidate_active_tokens(user_id=user_id, invalidated_at=now)
    )
    assert count == 2
    assert all(row.consumed_at == now for row in rows)

    token_id = uuid.uuid4()
    outbox_id = uuid.uuid4()
    token, outbox = repository.add_verification(
        token_id=token_id,
        outbox_id=outbox_id,
        user_id=user_id,
        token_hash="token-hash",
        expires_at=now,
        payload_ciphertext="ciphertext",
        payload_key_version="key-v2",
        available_at=now,
    )
    assert session.added[-2:] == [token, outbox]
    assert token.id == token_id
    assert token.purpose == "verify_recovery_email"
    assert token.consumed_at is None
    assert outbox.id == outbox_id
    assert outbox.action_token_id == token_id
    assert outbox.event_type == "verify_recovery_email"
    assert outbox.attempt_count == 0


def test_recovery_email_verification_principals_and_uow_lifecycle() -> None:
    expected = (SimpleNamespace(id="token"), SimpleNamespace(id="address"))
    session = FakeAsyncSession(execute_rows=[expected])
    repository = SqlAlchemyRecoveryEmailVerificationRepository(session)
    assert asyncio.run(repository.verification_principals_for_update(token_hash="hash")) == expected

    clean = FakeAsyncSession()
    uow = SqlAlchemyRecoveryEmailVerificationUnitOfWork(lambda: clean)
    asyncio.run(uow.__aenter__())
    assert isinstance(uow.repository, SqlAlchemyRecoveryEmailVerificationRepository)
    asyncio.run(uow.commit())
    asyncio.run(uow.__aexit__(None, None, None))
    assert clean.commits == 1
    assert clean.rollbacks == 0
    assert clean.closes == 1

    failed = FakeAsyncSession()
    uow2 = SqlAlchemyRecoveryEmailVerificationUnitOfWork(lambda: failed)
    asyncio.run(uow2.__aenter__())
    asyncio.run(uow2.__aexit__(RuntimeError, RuntimeError("boom"), None))
    assert failed.rollbacks == 1
    assert failed.closes == 1

    with pytest.raises(RuntimeError, match="not active"):
        asyncio.run(SqlAlchemyRecoveryEmailVerificationUnitOfWork(lambda: failed).commit())
