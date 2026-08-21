from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from processual_api.auth.mfa_crypto import MfaSecretCipher
from processual_api.auth.mfa_repository import SqlAlchemyMfaRepository
from processual_api.auth.mfa_service import MfaConflictError, MfaService
from processual_api.auth.token_material import TokenDigester


class _ScalarSession:
    def __init__(self, values):
        self.values = list(values)
        self.statements = []

    async def scalar(self, statement):
        self.statements.append(str(statement))
        return self.values.pop(0) if self.values else None


class _RecoveryRequiredRepository:
    def __init__(self, *, user_id: uuid.UUID, now: datetime) -> None:
        self.user_id = user_id
        self.factor = SimpleNamespace(
            id=uuid.uuid4(),
            user_id=user_id,
            status="active",
            disabled_at=None,
        )
        self.session = SimpleNamespace(
            id=uuid.uuid4(),
            user_id=user_id,
            revoked_at=None,
            expires_at=now + timedelta(hours=1),
            mfa_satisfied_at=now,
        )
        self.recovery_codes_replaced = False
        self.other_sessions_revoked = False

    async def session_for_update(self, *, session_id, user_id):
        if session_id == self.session.id and user_id == self.user_id:
            return self.session
        return None

    async def is_required_by_role(self, user_id):
        assert user_id == self.user_id
        return True

    async def active_factor_for_update(self, user_id):
        assert user_id == self.user_id
        return self.factor

    async def replace_recovery_codes(self, factor_id, *, code_hashes):
        self.recovery_codes_replaced = True

    async def revoke_other_sessions(self, **values):
        self.other_sessions_revoked = True


class _UnitOfWork:
    def __init__(self, repository) -> None:
        self.repository = repository
        self.commits = 0

    async def __aenter__(self):
        return self

    async def commit(self):
        self.commits += 1

    async def __aexit__(self, exc_type, exc, traceback):
        return None


def test_completed_account_recovery_makes_mfa_required_without_privileged_role() -> None:
    user_id = uuid.uuid4()
    completed_recovery_id = uuid.uuid4()
    session = _ScalarSession([None, completed_recovery_id])
    repository = SqlAlchemyMfaRepository(session)

    assert asyncio.run(repository.is_required_by_role(user_id)) is True
    assert len(session.statements) == 2
    assert "organization_memberships" in session.statements[0].lower()
    assert "auth_account_recovery_requests" in session.statements[1].lower()
    assert "completed" in session.statements[1].lower()


def test_mfa_disable_is_rejected_when_recovery_policy_requires_mfa() -> None:
    now = datetime(2026, 8, 21, 14, 0, tzinfo=UTC)
    user_id = uuid.uuid4()
    repository = _RecoveryRequiredRepository(user_id=user_id, now=now)
    service = MfaService(
        unit_of_work_factory=lambda: _UnitOfWork(repository),
        cipher=MfaSecretCipher(current_key_version="v1", keys={"v1": b"m" * 32}),
        token_digester=TokenDigester(b"p" * 32),
        recovery_code_count=6,
        clock=lambda: now,
    )

    with pytest.raises(MfaConflictError, match="required for this identity role"):
        asyncio.run(
            service.disable(
                user_id=user_id,
                session_id=repository.session.id,
            )
        )

    assert repository.factor.status == "active"
    assert repository.factor.disabled_at is None
    assert repository.recovery_codes_replaced is False
    assert repository.other_sessions_revoked is False
