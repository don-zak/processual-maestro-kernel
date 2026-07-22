from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

import processual_api.auth.session_service as service_module
from processual_api.auth.passwords import PasswordVerification
from processual_api.auth.session_contracts import SessionView
from processual_api.auth.session_service import (
    InvalidSessionCredentialsError,
    RefreshTokenReuseError,
    SessionService,
)
from processual_api.auth.token_material import TokenDigester


class FakePasswordService:
    def __init__(self, valid_hash="valid-hash") -> None:
        self.valid_hash = valid_hash
        self.verified = []

    def verify_password(self, encoded_hash, password):
        self.verified.append((encoded_hash, password))
        return PasswordVerification(valid=encoded_hash == self.valid_hash and password == "correct")

    def hash_password(self, password):
        return f"rehash:{password}"


class FakeRepository:
    def __init__(self, *, user=None, principals=None) -> None:
        self.user = user
        self.principals = principals
        self.added_session = None
        self.rotated = None
        self.revocations = []
        self.revoked_all = []
        self.sessions = ()
        self.owned_session = None

    async def user_for_login(self, email):
        self.login_email = email
        return self.user

    async def active_organization_id(self, user_id):
        return getattr(self.user, "organization_id", None)

    def add_session(self, **values):
        self.added_session = values

    async def refresh_principals_for_update(self, token_hash):
        self.token_hash = token_hash
        return self.principals

    def rotate_refresh_token(self, **values):
        self.rotated = values
        values["previous"].consumed_at = values["rotated_at"]

    async def revoke_family(self, auth_session, **values):
        auth_session.revoked_at = values["revoked_at"]
        auth_session.revoke_reason = values["reason"]
        reuse_token = values.get("reuse_token")
        if reuse_token is not None:
            reuse_token.reuse_detected_at = values["revoked_at"]
        self.revocations.append((auth_session, values))

    async def revoke_all_for_user(self, user_id, **values):
        self.revoked_all.append((user_id, values))

    async def sessions_for_user(self, user_id):
        return self.sessions

    async def owned_session_for_update(self, **values):
        return self.owned_session


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


def _user(now, *, password_hash="valid-hash", status="active", failed=0, locked_until=None):
    return SimpleNamespace(
        id=uuid.uuid4(),
        email_normalized="person@example.com",
        password_hash=password_hash,
        password_changed_at=None,
        status=status,
        failed_login_count=failed,
        locked_until=locked_until,
        organization_id=None,
    )


def _service(monkeypatch, repository, *, now, failed_login_limit=3):
    monkeypatch.setattr(service_module, "create_access_token", lambda **values: f"access:{values['session_id']}")
    uows = []

    def factory():
        uow = FakeUnitOfWork(repository)
        uows.append(uow)
        return uow

    service = SessionService(
        unit_of_work_factory=factory,
        password_service=FakePasswordService(),
        token_digester=TokenDigester(b"p" * 32),
        dummy_password_hash="dummy-hash",
        access_token_seconds=900,
        refresh_token_ttl=timedelta(days=30),
        failed_login_limit=failed_login_limit,
        lockout_duration=timedelta(minutes=15),
        clock=lambda: now,
    )
    return service, uows


def test_login_creates_authoritative_session_and_never_returns_password(monkeypatch):
    now = datetime(2026, 7, 22, 17, tzinfo=UTC)
    repository = FakeRepository(user=_user(now))
    service, uows = _service(monkeypatch, repository, now=now)

    issued = asyncio.run(service.login(email=" Person@Example.com ", password="correct"))

    assert repository.login_email == "person@example.com"
    assert repository.added_session["user_id"] == repository.user.id
    assert repository.added_session["refresh_token_hash"] != issued.refresh_token
    assert issued.access_token.startswith("access:")
    assert "correct" not in repr(issued)
    assert uows[0].commits == 1


def test_unknown_login_runs_dummy_password_verification(monkeypatch):
    now = datetime(2026, 7, 22, 17, tzinfo=UTC)
    repository = FakeRepository(user=None)
    service, _ = _service(monkeypatch, repository, now=now)

    with pytest.raises(InvalidSessionCredentialsError):
        asyncio.run(service.login(email="missing@example.com", password="wrong"))

    assert service._password_service.verified == [("dummy-hash", "wrong")]


def test_failed_login_applies_bounded_database_lockout(monkeypatch):
    now = datetime(2026, 7, 22, 17, tzinfo=UTC)
    user = _user(now, failed=2)
    repository = FakeRepository(user=user)
    service, uows = _service(monkeypatch, repository, now=now, failed_login_limit=3)

    with pytest.raises(InvalidSessionCredentialsError):
        asyncio.run(service.login(email=user.email_normalized, password="wrong"))

    assert user.failed_login_count == 3
    assert user.locked_until == now + timedelta(minutes=15)
    assert uows[0].commits == 1


def test_refresh_rotates_token_and_uses_same_session_family(monkeypatch):
    now = datetime(2026, 7, 22, 17, tzinfo=UTC)
    user = _user(now)
    auth_session = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user.id,
        organization_id=None,
        expires_at=now + timedelta(days=30),
        revoked_at=None,
        revoke_reason=None,
        last_seen_at=now,
    )
    previous = SimpleNamespace(
        id=uuid.uuid4(),
        session_id=auth_session.id,
        consumed_at=None,
        revoked_at=None,
        expires_at=auth_session.expires_at,
        reuse_detected_at=None,
    )
    repository = FakeRepository(principals=(previous, auth_session, user))
    service, uows = _service(monkeypatch, repository, now=now)

    issued = asyncio.run(service.refresh("old-refresh-token"))

    assert previous.consumed_at == now
    assert repository.rotated["previous"] is previous
    assert issued.session_id == auth_session.id
    assert issued.refresh_token != "old-refresh-token"
    assert uows[0].commits == 1


def test_consumed_refresh_replay_revokes_entire_family(monkeypatch):
    now = datetime(2026, 7, 22, 17, tzinfo=UTC)
    user = _user(now)
    auth_session = SimpleNamespace(
        id=uuid.uuid4(),
        organization_id=None,
        expires_at=now + timedelta(days=30),
        revoked_at=None,
        revoke_reason=None,
    )
    previous = SimpleNamespace(
        consumed_at=now - timedelta(seconds=1),
        revoked_at=None,
        expires_at=auth_session.expires_at,
        reuse_detected_at=None,
    )
    repository = FakeRepository(principals=(previous, auth_session, user))
    service, uows = _service(monkeypatch, repository, now=now)

    with pytest.raises(RefreshTokenReuseError):
        asyncio.run(service.refresh("replayed-refresh-token"))

    assert auth_session.revoke_reason == "refresh_token_reuse"
    assert previous.reuse_detected_at == now
    assert uows[0].commits == 1


def test_session_listing_filters_expired_rows(monkeypatch):
    now = datetime(2026, 7, 22, 17, tzinfo=UTC)
    repository = FakeRepository()
    repository.sessions = (
        SessionView(uuid.uuid4(), now, now, now + timedelta(hours=1)),
        SessionView(uuid.uuid4(), now, now, now - timedelta(seconds=1)),
    )
    service, _ = _service(monkeypatch, repository, now=now)

    sessions = asyncio.run(service.list_sessions(uuid.uuid4()))

    assert len(sessions) == 1
    assert sessions[0].expires_at > now
