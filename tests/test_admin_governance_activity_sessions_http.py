from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from processual_api.admin_governance.permission_authority import (
    AdministratorGovernanceAuthorityContext,
)
from processual_api.routers.governance import (
    get_administrator_governance_read_service,
    get_delegated_governance_authority_context,
    router,
)

ACTOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000301")
TARGET_ID = uuid.UUID("00000000-0000-0000-0000-000000000302")
EVENT_ID = uuid.UUID("00000000-0000-0000-0000-000000000303")
SESSION_ID = uuid.UUID("00000000-0000-0000-0000-000000000304")
NOW = datetime(2026, 8, 18, 18, 0, tzinfo=UTC)


class _ReadService:
    async def list_activity(self, *, limit: int = 50):
        assert limit == 25
        return (
            SimpleNamespace(
                event_id=EVENT_ID,
                event_type="administrator_frozen",
                actor_user_id=ACTOR_ID,
                subject_user_id=TARGET_ID,
                invitation_id=None,
                permission="governance.administrator.freeze",
                reason="Temporary administrator access suspension approved",
                occurred_at=NOW,
            ),
        )

    async def list_sessions(self, *, user_id: uuid.UUID):
        assert user_id == TARGET_ID
        return (
            SimpleNamespace(
                session_id=SESSION_ID,
                user_id=TARGET_ID,
                authenticated_at=NOW - timedelta(hours=1),
                mfa_satisfied_at=NOW - timedelta(minutes=10),
                last_seen_at=NOW - timedelta(minutes=1),
                expires_at=NOW + timedelta(hours=1),
                revoked_at=None,
                revoke_reason=None,
            ),
        )


def _context(*, authorities: set[str], permissions: set[str]):
    return AdministratorGovernanceAuthorityContext(
        user_id=str(ACTOR_ID),
        session_id=str(SESSION_ID),
        identity_active=True,
        platform_authorities=frozenset(authorities),
        active_permissions=frozenset(permissions),
        recent_mfa_step_up=True,
    )


def _client(context: AdministratorGovernanceAuthorityContext) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_delegated_governance_authority_context] = lambda: context
    app.dependency_overrides[get_administrator_governance_read_service] = lambda: _ReadService()
    return TestClient(app)


def test_platform_admin_can_read_activity_and_sessions() -> None:
    client = _client(_context(authorities={"platform_admin"}, permissions=set()))

    activity = client.get("/governance/activity?limit=25")
    sessions = client.get(f"/governance/administrators/{TARGET_ID}/sessions")

    assert activity.status_code == 200
    assert activity.json()["events"][0]["event_id"] == str(EVENT_ID)
    assert sessions.status_code == 200
    assert sessions.json()["sessions"][0]["session_id"] == str(SESSION_ID)
    assert sessions.json()["sessions"][0]["revoked_at"] is None


def test_supervisor_activity_read_requires_exact_permission() -> None:
    allowed = _client(
        _context(
            authorities={"platform_supervisor"},
            permissions={"governance.activity.view"},
        )
    )
    denied = _client(
        _context(
            authorities={"platform_supervisor"},
            permissions={"governance.administrators.view"},
        )
    )

    assert allowed.get("/governance/activity?limit=25").status_code == 200
    assert denied.get("/governance/activity?limit=25").status_code == 403


def test_supervisor_session_read_requires_exact_permission() -> None:
    allowed = _client(
        _context(
            authorities={"platform_supervisor"},
            permissions={"governance.sessions.view"},
        )
    )
    denied = _client(
        _context(
            authorities={"platform_supervisor"},
            permissions={"governance.activity.view"},
        )
    )

    path = f"/governance/administrators/{TARGET_ID}/sessions"
    assert allowed.get(path).status_code == 200
    assert denied.get(path).status_code == 403
