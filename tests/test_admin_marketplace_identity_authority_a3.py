from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from processual_api.admin_marketplace.errors import (
    AdminMarketplaceAuthorityDeniedError,
)
from processual_api.admin_marketplace.identity_authority import (
    AdminMarketplaceIdentityAuthorityResolver,
)

NOW = datetime(2026, 8, 4, 15, 0, tzinfo=UTC)
USER_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
SESSION_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")


class FakeExecuteResult:
    def __init__(self, row) -> None:
        self._row = row

    def one_or_none(self):
        return self._row


class FakeSession:
    def __init__(self, row) -> None:
        self.row = row
        self.statements = []
        self.entered = False
        self.exited = False

    async def __aenter__(self):
        self.entered = True
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        self.exited = True

    async def execute(self, statement):
        self.statements.append(statement)
        return FakeExecuteResult(self.row)


def _row(
    *,
    expires_at: datetime = NOW + timedelta(hours=1),
    revoked_at: datetime | None = None,
    mfa_satisfied_at: datetime | None = None,
):
    session = SimpleNamespace(
        expires_at=expires_at,
        revoked_at=revoked_at,
        mfa_satisfied_at=mfa_satisfied_at,
    )
    user = SimpleNamespace(id=USER_ID, status="active")
    authority = SimpleNamespace(
        authority="platform_admin",
        status="active",
    )
    return session, user, authority


def _resolver(row):
    session = FakeSession(row)
    resolver = AdminMarketplaceIdentityAuthorityResolver(
        session_factory=lambda: session,
        clock=lambda: NOW,
        mfa_step_up_max_age=timedelta(minutes=5),
    )
    return resolver, session


@pytest.mark.asyncio
async def test_active_platform_admin_identity_is_resolved() -> None:
    resolver, session = _resolver(_row())

    context = await resolver.resolve(
        user_id=str(USER_ID),
        session_id=str(SESSION_ID),
    )

    assert context.user_id == str(USER_ID)
    assert context.session_id == str(SESSION_ID)
    assert context.platform_authorities == frozenset({"platform_admin"})
    assert context.active_platform_admin is True
    assert context.recent_mfa_step_up is False
    assert session.entered is True
    assert session.exited is True
    assert len(session.statements) == 1


@pytest.mark.asyncio
async def test_recent_mfa_step_up_is_derived_from_session() -> None:
    resolver, _ = _resolver(
        _row(
            mfa_satisfied_at=NOW - timedelta(minutes=4),
        )
    )

    context = await resolver.resolve(
        user_id=str(USER_ID),
        session_id=str(SESSION_ID),
    )

    assert context.recent_mfa_step_up is True


@pytest.mark.asyncio
async def test_stale_mfa_step_up_is_not_recent() -> None:
    resolver, _ = _resolver(
        _row(
            mfa_satisfied_at=NOW - timedelta(minutes=6),
        )
    )

    context = await resolver.resolve(
        user_id=str(USER_ID),
        session_id=str(SESSION_ID),
    )

    assert context.recent_mfa_step_up is False


@pytest.mark.asyncio
async def test_missing_platform_admin_authority_is_denied() -> None:
    resolver, session = _resolver(None)

    with pytest.raises(
        AdminMarketplaceAuthorityDeniedError,
        match="platform administrator",
    ):
        await resolver.resolve(
            user_id=str(USER_ID),
            session_id=str(SESSION_ID),
        )

    assert len(session.statements) == 1


@pytest.mark.asyncio
async def test_revoked_identity_session_is_denied() -> None:
    resolver, _ = _resolver(
        _row(
            revoked_at=NOW - timedelta(minutes=1),
        )
    )

    with pytest.raises(
        AdminMarketplaceAuthorityDeniedError,
        match="identity session",
    ):
        await resolver.resolve(
            user_id=str(USER_ID),
            session_id=str(SESSION_ID),
        )


@pytest.mark.asyncio
async def test_expired_identity_session_is_denied() -> None:
    resolver, _ = _resolver(
        _row(
            expires_at=NOW,
        )
    )

    with pytest.raises(
        AdminMarketplaceAuthorityDeniedError,
        match="identity session",
    ):
        await resolver.resolve(
            user_id=str(USER_ID),
            session_id=str(SESSION_ID),
        )


@pytest.mark.asyncio
async def test_invalid_identifiers_are_denied_before_database_access() -> None:
    factory = MagicMock()
    resolver = AdminMarketplaceIdentityAuthorityResolver(
        session_factory=factory,
        clock=lambda: NOW,
    )

    with pytest.raises(
        AdminMarketplaceAuthorityDeniedError,
        match="Valid identity user",
    ):
        await resolver.resolve(
            user_id="invalid-user",
            session_id="invalid-session",
        )

    factory.assert_not_called()


def test_naive_clock_is_rejected() -> None:
    resolver = AdminMarketplaceIdentityAuthorityResolver(
        session_factory=MagicMock(),
        clock=lambda: datetime(2026, 8, 4, 15, 0),
    )

    with pytest.raises(ValueError, match="timezone-aware"):
        resolver._now()


@pytest.mark.parametrize(
    "maximum_age",
    (
        timedelta(seconds=59),
        timedelta(minutes=31),
    ),
)
def test_invalid_mfa_step_up_lifetime_is_rejected(
    maximum_age: timedelta,
) -> None:
    with pytest.raises(ValueError, match="MFA step-up lifetime"):
        AdminMarketplaceIdentityAuthorityResolver(
            session_factory=MagicMock(),
            mfa_step_up_max_age=maximum_age,
        )
