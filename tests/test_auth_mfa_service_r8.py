from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

import processual_api.auth.mfa_service as service_module
from processual_api.auth.mfa_crypto import MfaSecretCipher
from processual_api.auth.mfa_service import (
    InvalidMfaCredentialError,
    MfaConflictError,
    MfaService,
    MfaStepUpRequiredError,
)
from processual_api.auth.token_material import TokenDigester
from processual_api.auth.totp import totp_code_for_step

TOTP_SECRET = b"12345678901234567890"


class FakeRepository:
    def __init__(self, *, user_id, now) -> None:
        self.user_id = user_id
        self.now = now
        self.factor = None
        self.session = SimpleNamespace(
            id=uuid.uuid4(),
            user_id=user_id,
            revoked_at=None,
            expires_at=now + timedelta(hours=1),
            mfa_satisfied_at=None,
        )
        self.recovery = {}
        self.other_sessions_revoked = False

    async def active_factor_for_update(self, user_id):
        if self.factor is not None and self.factor.status == "active":
            return self.factor
        return None

    async def pending_factor_for_update(self, user_id):
        if self.factor is not None and self.factor.status == "pending":
            return self.factor
        return None

    async def user_email(self, user_id):
        return "person@example.com"

    async def disable_pending_factors(self, user_id, *, disabled_at):
        if self.factor is not None and self.factor.status == "pending":
            self.factor.status = "disabled"

    def add_pending_factor(self, **values):
        self.factor = SimpleNamespace(
            id=values["factor_id"],
            user_id=values["user_id"],
            label=values["label"],
            status="pending",
            secret_ciphertext=values["ciphertext"],
            secret_key_version=values["key_version"],
            verified_at=None,
            disabled_at=None,
            last_used_step=None,
        )

    async def replace_recovery_codes(self, factor_id, *, code_hashes):
        self.recovery = {
            code_hash: SimpleNamespace(code_hash=code_hash, used_at=None)
            for code_hash in code_hashes
        }

    async def unused_recovery_code_for_update(self, factor_id, code_hash):
        stored = self.recovery.get(code_hash)
        return stored if stored is not None and stored.used_at is None else None

    async def session_for_update(self, *, session_id, user_id):
        if session_id == self.session.id and user_id == self.user_id:
            return self.session
        return None

    async def factor_statuses(self, user_id):
        return (
            self.factor is not None and self.factor.status == "active",
            self.factor is not None and self.factor.status == "pending",
        )

    async def recovery_codes_remaining(self, factor_id):
        return sum(stored.used_at is None for stored in self.recovery.values())

    async def revoke_other_sessions(self, **values):
        self.other_sessions_revoked = True

    async def is_required_by_role(self, user_id):
        return False


class FakeUnitOfWork:
    def __init__(self, repository) -> None:
        self.repository = repository
        self.commits = 0

    async def __aenter__(self):
        return self

    async def commit(self):
        self.commits += 1

    async def __aexit__(self, exc_type, exc, traceback):
        return None


def _service(repository, now):
    return MfaService(
        unit_of_work_factory=lambda: FakeUnitOfWork(repository),
        cipher=MfaSecretCipher(current_key_version="v1", keys={"v1": b"m" * 32}),
        token_digester=TokenDigester(b"p" * 32),
        recovery_code_count=6,
        step_up_ttl=timedelta(minutes=5),
        clock=lambda: now,
    )


def test_enroll_confirm_returns_codes_once_and_blocks_totp_replay(monkeypatch):
    now = datetime(2026, 7, 22, 18, tzinfo=UTC)
    user_id = uuid.uuid4()
    repository = FakeRepository(user_id=user_id, now=now)
    service = _service(repository, now)
    monkeypatch.setattr(
        service_module,
        "generate_totp_secret",
        lambda: TOTP_SECRET,
    )

    asyncio.run(service.enroll(user_id=user_id, label="Primary"))
    code = totp_code_for_step(TOTP_SECRET, int(now.timestamp()) // 30)
    recovery_codes = asyncio.run(
        service.confirm_enrollment(
            user_id=user_id,
            session_id=repository.session.id,
            code=code,
        )
    )

    assert len(recovery_codes) == 6
    assert all(raw not in repository.recovery for raw in recovery_codes)
    assert repository.factor.status == "active"
    assert repository.session.mfa_satisfied_at == now
    with pytest.raises(InvalidMfaCredentialError):
        asyncio.run(
            service.verify(
                user_id=user_id,
                session_id=repository.session.id,
                code=code,
                recovery_code=None,
            )
        )


def test_recovery_code_is_hashed_and_consumed_once(monkeypatch):
    now = datetime(2026, 7, 22, 18, tzinfo=UTC)
    user_id = uuid.uuid4()
    repository = FakeRepository(user_id=user_id, now=now)
    service = _service(repository, now)
    monkeypatch.setattr(
        service_module,
        "generate_totp_secret",
        lambda: TOTP_SECRET,
    )
    asyncio.run(service.enroll(user_id=user_id, label="Primary"))
    codes = asyncio.run(
        service.confirm_enrollment(
            user_id=user_id,
            session_id=repository.session.id,
            code=totp_code_for_step(TOTP_SECRET, int(now.timestamp()) // 30),
        )
    )
    repository.session.mfa_satisfied_at = None

    asyncio.run(
        service.verify(
            user_id=user_id,
            session_id=repository.session.id,
            code=None,
            recovery_code=codes[0].lower(),
        )
    )
    assert repository.session.mfa_satisfied_at == now
    with pytest.raises(InvalidMfaCredentialError):
        asyncio.run(
            service.verify(
                user_id=user_id,
                session_id=repository.session.id,
                code=None,
                recovery_code=codes[0],
            )
        )


def test_sensitive_mfa_changes_require_recent_step_up(monkeypatch):
    now = datetime(2026, 7, 22, 18, tzinfo=UTC)
    user_id = uuid.uuid4()
    repository = FakeRepository(user_id=user_id, now=now)
    service = _service(repository, now)
    monkeypatch.setattr(
        service_module,
        "generate_totp_secret",
        lambda: TOTP_SECRET,
    )
    asyncio.run(service.enroll(user_id=user_id, label="Primary"))
    asyncio.run(
        service.confirm_enrollment(
            user_id=user_id,
            session_id=repository.session.id,
            code=totp_code_for_step(TOTP_SECRET, int(now.timestamp()) // 30),
        )
    )
    repository.session.mfa_satisfied_at = now - timedelta(minutes=6)

    with pytest.raises(MfaStepUpRequiredError):
        asyncio.run(service.disable(user_id=user_id, session_id=repository.session.id))

    repository.session.mfa_satisfied_at = now
    asyncio.run(service.disable(user_id=user_id, session_id=repository.session.id))
    assert repository.factor.status == "disabled"
    assert repository.recovery == {}
    assert repository.other_sessions_revoked is True


def test_active_factor_cannot_be_reenrolled():
    now = datetime(2026, 7, 22, 18, tzinfo=UTC)
    user_id = uuid.uuid4()
    repository = FakeRepository(user_id=user_id, now=now)
    repository.factor = SimpleNamespace(status="active")
    service = _service(repository, now)

    with pytest.raises(MfaConflictError):
        asyncio.run(service.enroll(user_id=user_id, label="Replacement"))
