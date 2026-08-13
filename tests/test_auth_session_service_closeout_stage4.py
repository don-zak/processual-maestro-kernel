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
    SessionAuthorityUnavailableError,
    SessionService,
)


NOW = datetime(2026, 8, 13, 13, tzinfo=UTC)


class FakePasswordService:
    def __init__(self, *, valid=True, needs_rehash=False) -> None:
        self.valid = valid
        self.needs_rehash = needs_rehash
        self.verified = []
        self.hashed = []

    def verify_password(self, encoded_hash, password):
        self.verified.append((encoded_hash, password))
        return PasswordVerification(valid=self.valid, needs_rehash=self.needs_rehash)

    def hash_password(self, password):
        self.hashed.append(password)
        return "rehash-value"


class Material:
    raw = "new-refresh"
    digest = "new-refresh-hash"


class FakeDigester:
    def digest(self, raw, *, purpose):
        return f"{purpose}:{raw}"

    def generate_token(self, *, purpose):
        assert purpose == "refresh_token"
        return Material()


class FakeRepository:
    def __init__(self) -> None:
        self.user = None
        self.principals = None
        self.organization_id = None
        self.authorities = ()
        self.mfa_required = False
        self.sessions = ()
        self.owned = None
        self.revocations = []
        self.revoked_all = []
        self.rotated = None
        self.added = None

    async def user_for_login(self, email):
        self.email = email
        return self.user

    async def active_organization_id(self, user_id):
        return self.organization_id

    async def active_platform_authorities(self, user_id):
        return self.authorities

    async def requires_mfa(self, user_id):
        return self.mfa_required

    def add_session(self, **values):
        self.added = values

    async def refresh_principals_for_update(self, token_hash):
        self.token_hash = token_hash
        return self.principals

    async def revoke_family(self, auth_session, **values):
        self.revocations.append((auth_session, values))
        auth_session.revoked_at = values["revoked_at"]

    def rotate_refresh_token(self, **values):
        self.rotated = values

    async def revoke_all_for_user(self, user_id, **values):
        self.revoked_all.append((user_id, values))

    async def sessions_for_user(self, user_id):
        return self.sessions

    async def owned_session_for_update(self, **values):
        return self.owned


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


def make_service(
    repository=None,
    *,
    password=None,
    clock=lambda: NOW,
    access_token_seconds=900,
):
    repo = repository if repository is not None else FakeRepository()
    password_service = password or FakePasswordService()
    uows = []

    def factory():
        uow = FakeUow(repo)
        uows.append(uow)
        return uow

    service = SessionService(
        unit_of_work_factory=factory,
        password_service=password_service,
        token_digester=FakeDigester(),
        dummy_password_hash="dummy",
        access_token_seconds=access_token_seconds,
        refresh_token_ttl=timedelta(days=30),
        failed_login_limit=3,
        lockout_duration=timedelta(minutes=15),
        clock=clock,
    )
    return service, repo, password_service, uows


@pytest.mark.parametrize(
    "kwargs",
    [
        {"access_token_seconds": 59},
        {"access_token_seconds": 3601},
        {"refresh_token_ttl": timedelta(minutes=59)},
        {"refresh_token_ttl": timedelta(days=91)},
        {"failed_login_limit": 1},
        {"failed_login_limit": 21},
        {"lockout_duration": timedelta(seconds=30)},
        {"lockout_duration": timedelta(days=2)},
    ],
)
def test_constructor_rejects_unsafe_session_policy(kwargs) -> None:
    defaults = {
        "access_token_seconds": 900,
        "refresh_token_ttl": timedelta(days=30),
        "failed_login_limit": 3,
        "lockout_duration": timedelta(minutes=15),
    }
    defaults.update(kwargs)
    with pytest.raises(ValueError):
        SessionService(
            unit_of_work_factory=lambda: None,
            password_service=FakePasswordService(),
            token_digester=FakeDigester(),
            dummy_password_hash="dummy",
            **defaults,
        )


def test_clock_and_access_token_expiry_fail_closed(monkeypatch) -> None:
    service, _, _, _ = make_service(clock=lambda: datetime(2026, 8, 13, 13))
    with pytest.raises(ValueError, match="timezone-aware"):
        service._now()

    service, _, _, _ = make_service()
    with pytest.raises(InvalidSessionCredentialsError):
        service._issue_access_token(
            user_id=uuid.uuid4(),
            session_id=uuid.uuid4(),
            organization_id=None,
            session_expires_at=NOW,
        )

    captured = {}
    monkeypatch.setattr(
        service_module,
        "create_access_token",
        lambda **values: captured.update(values) or "token",
    )
    token, expires = service._issue_access_token(
        user_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        organization_id=None,
        session_expires_at=NOW + timedelta(seconds=120),
        platform_authorities=("platform_admin",),
    )
    assert token == "token"
    assert expires == 120
    assert captured["platform_authorities"] == ("platform_admin",)


def test_login_invalid_email_and_missing_repository_use_safe_paths() -> None:
    service, _, password, _ = make_service()
    with pytest.raises(InvalidSessionCredentialsError):
        asyncio.run(service.login(email="not-an-email", password="secret"))
    assert password.verified == [("dummy", "secret")]

    service, _, _, _ = make_service()
    service._unit_of_work_factory = lambda: FakeUow(None)
    with pytest.raises(SessionAuthorityUnavailableError, match="repository"):
        asyncio.run(service.login(email="person@example.com", password="secret"))


def test_login_locked_inactive_and_rehash_branches(monkeypatch) -> None:
    user = SimpleNamespace(
        id=uuid.uuid4(),
        password_hash="hash",
        password_changed_at=None,
        status="active",
        failed_login_count=0,
        locked_until=NOW + timedelta(minutes=1),
    )
    repo = FakeRepository()
    repo.user = user
    service, _, password, uows = make_service(repo, password=FakePasswordService(valid=True))
    with pytest.raises(InvalidSessionCredentialsError):
        asyncio.run(service.login(email="person@example.com", password="ok"))
    assert user.failed_login_count == 0
    assert uows[-1].commits == 1

    user.locked_until = None
    user.status = "disabled"
    with pytest.raises(InvalidSessionCredentialsError):
        asyncio.run(service.login(email="person@example.com", password="ok"))

    user.status = "active"
    password.valid = True
    password.needs_rehash = True
    repo.organization_id = uuid.uuid4()
    repo.authorities = ("platform_admin",)
    monkeypatch.setattr(service_module, "create_access_token", lambda **values: "access")
    issued = asyncio.run(service.login(email="person@example.com", password="ok"))
    assert issued.access_token == "access"
    assert user.password_hash == "rehash-value"
    assert user.password_changed_at == NOW
    assert repo.added["organization_id"] == repo.organization_id


def principals(*, previous_overrides=None, session_overrides=None, user_status="active"):
    previous_values = {
        "consumed_at": None,
        "revoked_at": None,
        "expires_at": NOW + timedelta(days=1),
    }
    previous_values.update(previous_overrides or {})
    session_values = {
        "id": uuid.uuid4(),
        "organization_id": None,
        "revoked_at": None,
        "expires_at": NOW + timedelta(days=1),
        "last_seen_at": NOW,
    }
    session_values.update(session_overrides or {})
    user = SimpleNamespace(id=uuid.uuid4(), status=user_status)
    return SimpleNamespace(**previous_values), SimpleNamespace(**session_values), user


def test_refresh_missing_and_invalid_credentials_branches(monkeypatch) -> None:
    service, repo, _, _ = make_service()
    with pytest.raises(InvalidSessionCredentialsError):
        asyncio.run(service.refresh("missing"))

    previous, session, user = principals(previous_overrides={"revoked_at": NOW})
    repo.principals = (previous, session, user)
    with pytest.raises(InvalidSessionCredentialsError):
        asyncio.run(service.refresh("revoked"))
    assert repo.revocations[-1][1]["reason"] == "refresh_credentials_invalid"

    previous, session, user = principals(session_overrides={"revoked_at": NOW})
    repo.principals = (previous, session, user)
    before = len(repo.revocations)
    with pytest.raises(InvalidSessionCredentialsError):
        asyncio.run(service.refresh("already-revoked"))
    assert len(repo.revocations) == before

    previous, session, user = principals(user_status="disabled")
    repo.principals = (previous, session, user)
    with pytest.raises(InvalidSessionCredentialsError):
        asyncio.run(service.refresh("disabled-user"))

    previous, session, user = principals()
    repo.principals = (previous, session, user)
    repo.authorities = ("platform_supervisor",)
    monkeypatch.setattr(service_module, "create_access_token", lambda **values: "access")
    issued = asyncio.run(service.refresh("valid"))
    assert issued.access_token == "access"
    assert repo.rotated["previous"] is previous
    assert session.last_seen_at == NOW


def test_logout_logout_all_listing_and_revoke_session_branches() -> None:
    service, repo, _, uows = make_service()
    asyncio.run(service.logout("unknown"))
    asyncio.run(service.logout_all("unknown"))
    assert not repo.revocations
    assert not repo.revoked_all

    previous, session, user = principals()
    repo.principals = (previous, session, user)
    asyncio.run(service.logout("known"))
    assert repo.revocations[-1][1]["reason"] == "user_logout"
    asyncio.run(service.logout_all("known"))
    assert repo.revoked_all[-1][0] == user.id
    assert repo.revoked_all[-1][1]["reason"] == "user_logout_all"

    repo.sessions = (
        SessionView(uuid.uuid4(), NOW, NOW, NOW + timedelta(minutes=1)),
        SessionView(uuid.uuid4(), NOW, NOW, NOW),
    )
    assert len(asyncio.run(service.list_sessions(user.id))) == 1

    repo.owned = None
    asyncio.run(service.revoke_session(user_id=user.id, session_id=uuid.uuid4()))
    count = len(repo.revocations)
    repo.owned = SimpleNamespace(revoked_at=NOW)
    asyncio.run(service.revoke_session(user_id=user.id, session_id=uuid.uuid4()))
    assert len(repo.revocations) == count
    repo.owned = SimpleNamespace(revoked_at=None)
    asyncio.run(service.revoke_session(user_id=user.id, session_id=uuid.uuid4()))
    assert repo.revocations[-1][1]["reason"] == "user_session_revoked"
    assert uows[-1].commits == 1
