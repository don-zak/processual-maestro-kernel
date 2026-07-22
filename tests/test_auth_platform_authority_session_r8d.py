from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import processual_api.auth.session_service as service_module
from processual_api.auth.passwords import PasswordVerification
from processual_api.auth.security import (
    create_access_token,
    verify_access_token,
)
from processual_api.auth.session_service import SessionService
from processual_api.auth.token_material import TokenDigester


class PasswordService:
    def verify_password(self, encoded_hash, password):
        return PasswordVerification(
            valid=encoded_hash == "valid-hash" and password == "correct"
        )

    def hash_password(self, password):
        return f"rehash:{password}"


class Repository:
    def __init__(
        self,
        *,
        user=None,
        principals=None,
        platform_authorities=(),
        mfa_required=False,
    ) -> None:
        self.user = user
        self.principals = principals
        self.platform_authorities = platform_authorities
        self.mfa_required = mfa_required
        self.authority_reads = []
        self.added_session = None
        self.rotated = None

    async def user_for_login(self, email):
        return self.user

    async def active_organization_id(self, user_id):
        return getattr(self.user, "organization_id", None)

    async def active_platform_authorities(self, user_id):
        self.authority_reads.append(user_id)
        return self.platform_authorities

    async def requires_mfa(self, user_id):
        return self.mfa_required

    def add_session(self, **values):
        self.added_session = values

    async def refresh_principals_for_update(self, token_hash):
        return self.principals

    def rotate_refresh_token(self, **values):
        self.rotated = values
        values["previous"].consumed_at = values["rotated_at"]


class UnitOfWork:
    def __init__(self, repository) -> None:
        self.repository = repository
        self.commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    async def commit(self):
        self.commits += 1


def _service(repository, now):
    def factory():
        return UnitOfWork(repository)

    return SessionService(
        unit_of_work_factory=factory,
        password_service=PasswordService(),
        token_digester=TokenDigester(b"a" * 32),
        dummy_password_hash="dummy-hash",
        access_token_seconds=900,
        refresh_token_ttl=timedelta(days=30),
        clock=lambda: now,
    )


def _user():
    return SimpleNamespace(
        id=uuid.uuid4(),
        email_normalized="admin@example.com",
        password_hash="valid-hash",
        password_changed_at=None,
        status="active",
        failed_login_count=0,
        locked_until=None,
        organization_id=None,
    )


def test_create_access_token_serializes_platform_authorities() -> None:
    token = create_access_token(
        subject="user-1",
        role="client",
        session_type="identity_user",
        scopes=["evaluation"],
        platform_authorities=("platform_admin",),
    )

    payload = verify_access_token(token)

    assert payload["platform_authorities"] == ["platform_admin"]
    assert payload["role"] == "client"
    assert payload["session_type"] == "identity_user"
    assert payload["scopes"] == ["evaluation"]
    assert payload.get("is_admin") is None


def test_create_access_token_defaults_to_empty_authority_claim() -> None:
    token = create_access_token(
        subject="user-2",
        role="client",
        session_type="identity_user",
        scopes=["evaluation"],
    )

    payload = verify_access_token(token)

    assert payload["platform_authorities"] == []


def test_login_reads_and_propagates_active_platform_authority(
    monkeypatch,
) -> None:
    now = datetime(2026, 7, 22, 18, tzinfo=UTC)
    user = _user()
    repository = Repository(
        user=user,
        platform_authorities=("platform_admin",),
    )
    captured = {}

    monkeypatch.setattr(
        service_module,
        "create_access_token",
        lambda **values: captured.update(values) or "login-access",
    )

    issued = asyncio.run(
        _service(repository, now).login(
            email="admin@example.com",
            password="correct",
        )
    )

    assert issued.access_token == "login-access"
    assert repository.authority_reads == [user.id]
    assert captured["platform_authorities"] == ("platform_admin",)
    assert captured["role"] == "client"
    assert captured["session_type"] == "identity_user"
    assert captured["scopes"] == ["evaluation"]
    assert "*" not in captured["scopes"]


def test_pending_mfa_authority_does_not_gain_evaluation_scope(
    monkeypatch,
) -> None:
    now = datetime(2026, 7, 22, 18, tzinfo=UTC)
    user = _user()
    repository = Repository(
        user=user,
        platform_authorities=("platform_admin",),
        mfa_required=True,
    )
    captured = {}

    monkeypatch.setattr(
        service_module,
        "create_access_token",
        lambda **values: captured.update(values) or "pending-access",
    )

    issued = asyncio.run(
        _service(repository, now).login(
            email="admin@example.com",
            password="correct",
        )
    )

    assert issued.mfa_required is True
    assert captured["platform_authorities"] == ("platform_admin",)
    assert captured["scopes"] == ["auth:mfa"]
    assert captured["role"] == "client"
    assert captured["session_type"] == "identity_user"


def test_refresh_rereads_authority_instead_of_reusing_stale_claim(
    monkeypatch,
) -> None:
    now = datetime(2026, 7, 22, 18, tzinfo=UTC)
    user = _user()
    session_id = uuid.uuid4()

    previous = SimpleNamespace(
        consumed_at=None,
        revoked_at=None,
        expires_at=now + timedelta(days=2),
    )
    auth_session = SimpleNamespace(
        id=session_id,
        organization_id=None,
        revoked_at=None,
        expires_at=now + timedelta(days=2),
        last_seen_at=None,
    )

    repository = Repository(
        principals=(previous, auth_session, user),
        platform_authorities=(),
    )
    captured = {}

    monkeypatch.setattr(
        service_module,
        "create_access_token",
        lambda **values: captured.update(values) or "refresh-access",
    )

    issued = asyncio.run(
        _service(repository, now).refresh("old-refresh-token")
    )

    assert issued.access_token == "refresh-access"
    assert repository.authority_reads == [user.id]
    assert captured["platform_authorities"] == ()
    assert captured["role"] == "client"
    assert captured["session_type"] == "identity_user"
    assert captured["scopes"] == ["evaluation"]


def test_platform_authority_claim_never_changes_operational_session_shape(
    monkeypatch,
) -> None:
    now = datetime(2026, 7, 22, 18, tzinfo=UTC)
    user = _user()
    repository = Repository(
        user=user,
        platform_authorities=("platform_admin",),
    )
    captured = {}

    monkeypatch.setattr(
        service_module,
        "create_access_token",
        lambda **values: captured.update(values) or "safe-access",
    )

    asyncio.run(
        _service(repository, now).login(
            email="admin@example.com",
            password="correct",
        )
    )

    assert captured["role"] != "admin"
    assert captured["session_type"] != "ui_admin"
    assert captured["scopes"] != ["*"]
    assert all(not scope.startswith("admin:") for scope in captured["scopes"])
