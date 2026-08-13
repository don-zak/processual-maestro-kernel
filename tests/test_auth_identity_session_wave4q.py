from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from processual_api.auth import security


class _Result:
    def __init__(self, row):
        self._row = row

    def one_or_none(self):
        return self._row


class _FakeSession:
    def __init__(self, *, row, scalars=None, execute_error: Exception | None = None):
        self.row = row
        self.scalars = iter(scalars or [None, None, None])
        self.execute_error = execute_error

    async def execute(self, _statement):
        if self.execute_error is not None:
            raise self.execute_error
        return _Result(self.row)

    async def scalar(self, _statement):
        return next(self.scalars)


class _SessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _install_session_factory(monkeypatch: pytest.MonkeyPatch, session: _FakeSession) -> None:
    import processual_api.db.session as session_module

    monkeypatch.setattr(session_module, "get_session_factory", lambda: lambda: _SessionContext(session))


def _active_row(*, organization_id=None, revoked_at=None, expires_at=None, status="active", mfa_satisfied_at=None):
    auth_session = SimpleNamespace(
        organization_id=organization_id,
        revoked_at=revoked_at,
        expires_at=expires_at or datetime.now(UTC) + timedelta(hours=1),
        mfa_satisfied_at=mfa_satisfied_at,
    )
    user = SimpleNamespace(id="11111111-1111-1111-1111-111111111111", status=status)
    return auth_session, user


@pytest.mark.asyncio
async def test_validate_identity_session_rejects_invalid_identifiers() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await security._validate_identity_session(
            subject="not-a-uuid",
            session_id="also-not-a-uuid",
            organization_id=None,
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid or expired token"


@pytest.mark.asyncio
async def test_validate_identity_session_maps_backend_failure_to_503(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_session_factory(
        monkeypatch,
        _FakeSession(row=None, execute_error=RuntimeError("database offline")),
    )

    with pytest.raises(HTTPException) as exc_info:
        await security._validate_identity_session(
            subject="11111111-1111-1111-1111-111111111111",
            session_id="22222222-2222-2222-2222-222222222222",
            organization_id=None,
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Session authority unavailable"


@pytest.mark.asyncio
async def test_validate_identity_session_rejects_missing_session(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_session_factory(monkeypatch, _FakeSession(row=None))

    with pytest.raises(HTTPException) as exc_info:
        await security._validate_identity_session(
            subject="11111111-1111-1111-1111-111111111111",
            session_id="22222222-2222-2222-2222-222222222222",
            organization_id=None,
        )

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("row", "organization_id"),
    [
        (_active_row(revoked_at=datetime.now(UTC)), None),
        (_active_row(expires_at=datetime.now(UTC) - timedelta(seconds=1)), None),
        (_active_row(status="disabled"), None),
        (_active_row(organization_id="org-a"), "org-b"),
    ],
)
async def test_validate_identity_session_rejects_non_authoritative_sessions(
    monkeypatch: pytest.MonkeyPatch,
    row,
    organization_id,
) -> None:
    _install_session_factory(monkeypatch, _FakeSession(row=row))

    with pytest.raises(HTTPException) as exc_info:
        await security._validate_identity_session(
            subject="11111111-1111-1111-1111-111111111111",
            session_id="22222222-2222-2222-2222-222222222222",
            organization_id=organization_id,
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid or expired token"


@pytest.mark.asyncio
async def test_validate_identity_session_returns_authoritative_org_without_mfa(monkeypatch: pytest.MonkeyPatch) -> None:
    row = _active_row(organization_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    _install_session_factory(monkeypatch, _FakeSession(row=row, scalars=[None, None, None]))

    subject, organization_id, mfa_pending = await security._validate_identity_session(
        subject="11111111-1111-1111-1111-111111111111",
        session_id="22222222-2222-2222-2222-222222222222",
        organization_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    )

    assert subject == "11111111-1111-1111-1111-111111111111"
    assert organization_id == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    assert mfa_pending is False


@pytest.mark.asyncio
@pytest.mark.parametrize("scalar_values", [[object(), None, None], [None, object(), None], [None, None, object()]])
async def test_validate_identity_session_requires_unsatisfied_mfa_for_any_privileged_signal(
    monkeypatch: pytest.MonkeyPatch,
    scalar_values,
) -> None:
    row = _active_row()
    _install_session_factory(monkeypatch, _FakeSession(row=row, scalars=scalar_values))

    _, _, mfa_pending = await security._validate_identity_session(
        subject="11111111-1111-1111-1111-111111111111",
        session_id="22222222-2222-2222-2222-222222222222",
        organization_id=None,
    )

    assert mfa_pending is True


@pytest.mark.asyncio
async def test_validate_identity_session_respects_satisfied_mfa(monkeypatch: pytest.MonkeyPatch) -> None:
    row = _active_row(mfa_satisfied_at=datetime.now(UTC))
    _install_session_factory(monkeypatch, _FakeSession(row=row, scalars=[object(), None, None]))

    _, _, mfa_pending = await security._validate_identity_session(
        subject="11111111-1111-1111-1111-111111111111",
        session_id="22222222-2222-2222-2222-222222222222",
        organization_id=None,
    )

    assert mfa_pending is False
