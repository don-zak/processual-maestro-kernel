from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

import processual_api.auth.mfa_service as service_module
from processual_api.auth.mfa_crypto import EncryptedMfaSecret
from processual_api.auth.mfa_service import (
    InvalidMfaCredentialError,
    MfaAuthorityUnavailableError,
    MfaConflictError,
    MfaService,
    MfaStepUpRequiredError,
)


NOW = datetime(2026, 8, 13, 12, tzinfo=UTC)


class FakeCipher:
    def __init__(self, *, fail_decrypt: bool = False) -> None:
        self.fail_decrypt = fail_decrypt
        self.encrypt_calls = []
        self.decrypt_calls = []

    def encrypt(self, secret, *, factor_id, user_id):
        self.encrypt_calls.append((secret, factor_id, user_id))
        return EncryptedMfaSecret(ciphertext=b"cipher", key_version="v1")

    def decrypt(self, encrypted, *, factor_id, user_id):
        self.decrypt_calls.append((encrypted, factor_id, user_id))
        if self.fail_decrypt:
            raise ValueError("key unavailable")
        return b"12345678901234567890"


class Material:
    def __init__(self, raw: str, digest: str) -> None:
        self.raw = raw
        self.digest = digest


class FakeDigester:
    def __init__(self) -> None:
        self.generated = 0
        self.digest_calls = []

    def generate_recovery_code(self):
        self.generated += 1
        return Material(f"RAW-{self.generated}", f"HASH-{self.generated}")

    def digest(self, raw, *, purpose):
        self.digest_calls.append((raw, purpose))
        return f"digest:{raw}"


class FakeRepository:
    def __init__(self) -> None:
        self.active_factor = None
        self.pending_factor = None
        self.email = "person@example.com"
        self.session = None
        self.required = False
        self.recovery_match = None
        self.statuses = (False, False)
        self.remaining = 0
        self.disabled_pending = 0
        self.added_factor = None
        self.replaced = []
        self.revoked_other = []

    async def active_factor_for_update(self, user_id):
        return self.active_factor

    async def pending_factor_for_update(self, user_id):
        return self.pending_factor

    async def user_email(self, user_id):
        return self.email

    async def disable_pending_factors(self, user_id, *, disabled_at):
        self.disabled_pending += 1

    def add_pending_factor(self, **values):
        self.added_factor = values

    async def replace_recovery_codes(self, factor_id, *, code_hashes):
        self.replaced.append((factor_id, tuple(code_hashes)))

    async def session_for_update(self, *, user_id, session_id):
        return self.session

    async def unused_recovery_code_for_update(self, factor_id, digest):
        return self.recovery_match

    async def is_required_by_role(self, user_id):
        return self.required

    async def revoke_other_sessions(self, **values):
        self.revoked_other.append(values)

    async def factor_statuses(self, user_id):
        return self.statuses

    async def recovery_codes_remaining(self, factor_id):
        return self.remaining


class FakeUow:
    def __init__(self, repository) -> None:
        self.repository = repository
        self.commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    async def commit(self):
        self.commits += 1


def make_service(repository=None, *, cipher=None, clock=lambda: NOW):
    repo = repository if repository is not None else FakeRepository()
    uows = []

    def factory():
        uow = FakeUow(repo)
        uows.append(uow)
        return uow

    service = MfaService(
        unit_of_work_factory=factory,
        cipher=cipher or FakeCipher(),
        token_digester=FakeDigester(),
        recovery_code_count=6,
        step_up_ttl=timedelta(minutes=5),
        clock=clock,
    )
    return service, repo, uows


@pytest.mark.parametrize(
    "kwargs",
    [
        {"issuer": " "},
        {"recovery_code_count": 5},
        {"recovery_code_count": 21},
        {"step_up_ttl": timedelta(seconds=30)},
        {"step_up_ttl": timedelta(minutes=31)},
    ],
)
def test_constructor_rejects_unsafe_mfa_policy(kwargs) -> None:
    with pytest.raises(ValueError):
        MfaService(
            unit_of_work_factory=lambda: None,
            cipher=FakeCipher(),
            token_digester=FakeDigester(),
            **kwargs,
        )


def test_clock_and_decryption_authority_fail_closed() -> None:
    service, _, _ = make_service(clock=lambda: datetime(2026, 8, 13, 12))
    with pytest.raises(ValueError, match="timezone-aware"):
        service._now()

    failing, _, _ = make_service(cipher=FakeCipher(fail_decrypt=True))
    factor = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        secret_ciphertext=b"cipher",
        secret_key_version="v1",
    )
    with pytest.raises(MfaAuthorityUnavailableError, match="authority"):
        failing._decrypt_factor(factor)


def test_enroll_rejects_missing_authority_and_identity(monkeypatch) -> None:
    service, _, _ = make_service()
    service._unit_of_work_factory = lambda: FakeUow(None)
    with pytest.raises(MfaAuthorityUnavailableError, match="repository"):
        asyncio.run(service.enroll(user_id=uuid.uuid4(), label="Primary"))

    service, repo, _ = make_service()
    repo.email = ""
    with pytest.raises(MfaAuthorityUnavailableError, match="identity"):
        asyncio.run(service.enroll(user_id=uuid.uuid4(), label="Primary"))

    repo.email = "person@example.com"
    repo.active_factor = SimpleNamespace(id=uuid.uuid4())
    with pytest.raises(MfaConflictError, match="active MFA"):
        asyncio.run(service.enroll(user_id=uuid.uuid4(), label="Primary"))

    repo.active_factor = None
    monkeypatch.setattr(service_module, "generate_totp_secret", lambda: b"12345678901234567890")
    enrollment = asyncio.run(service.enroll(user_id=uuid.uuid4(), label="Primary"))
    assert enrollment.secret
    assert repo.disabled_pending == 1
    assert repo.added_factor["label"] == "Primary"


def test_confirm_and_verify_fail_closed_on_missing_state(monkeypatch) -> None:
    service, repo, _ = make_service()
    with pytest.raises(MfaConflictError, match="pending"):
        asyncio.run(
            service.confirm_enrollment(
                user_id=uuid.uuid4(), session_id=uuid.uuid4(), code="123456"
            )
        )

    with pytest.raises(InvalidMfaCredentialError):
        asyncio.run(
            service.verify(
                user_id=uuid.uuid4(),
                session_id=uuid.uuid4(),
                code=None,
                recovery_code=None,
            )
        )

    factor = SimpleNamespace(id=uuid.uuid4())
    repo.active_factor = factor
    with pytest.raises(InvalidMfaCredentialError):
        asyncio.run(
            service.verify(
                user_id=uuid.uuid4(),
                session_id=uuid.uuid4(),
                code=None,
                recovery_code=" missing ",
            )
        )
    assert service._token_digester.digest_calls[-1][0] == "MISSING"


def test_step_up_regeneration_disable_and_status_branches() -> None:
    service, repo, uows = make_service()
    user_id = uuid.uuid4()
    session_id = uuid.uuid4()

    with pytest.raises(MfaStepUpRequiredError):
        asyncio.run(service.require_recent_step_up(user_id=user_id, session_id=session_id))

    repo.session = SimpleNamespace(
        revoked_at=None,
        expires_at=NOW + timedelta(hours=1),
        mfa_satisfied_at=NOW,
    )
    asyncio.run(service.require_recent_step_up(user_id=user_id, session_id=session_id))

    with pytest.raises(MfaConflictError, match="No active"):
        asyncio.run(service.regenerate_recovery_codes(user_id=user_id, session_id=session_id))

    factor = SimpleNamespace(id=uuid.uuid4(), status="active", disabled_at=None)
    repo.active_factor = factor
    codes = asyncio.run(service.regenerate_recovery_codes(user_id=user_id, session_id=session_id))
    assert len(codes) == 6
    assert repo.replaced[-1][0] == factor.id
    assert uows[-1].commits == 1

    repo.required = True
    with pytest.raises(MfaConflictError, match="required"):
        asyncio.run(service.disable(user_id=user_id, session_id=session_id))

    repo.required = False
    repo.active_factor = None
    with pytest.raises(MfaConflictError, match="No active"):
        asyncio.run(service.disable(user_id=user_id, session_id=session_id))

    repo.active_factor = factor
    asyncio.run(service.disable(user_id=user_id, session_id=session_id))
    assert factor.status == "disabled"
    assert factor.disabled_at == NOW
    assert repo.replaced[-1] == (factor.id, ())
    assert repo.revoked_other[-1]["reason"] == "mfa_disabled"

    repo.statuses = (True, False)
    repo.active_factor = factor
    repo.remaining = 4
    status = asyncio.run(service.status(user_id=user_id, session_id=session_id))
    assert status.enabled is True
    assert status.pending_enrollment is False
    assert status.recovery_codes_remaining == 4
    assert status.step_up_satisfied is True
