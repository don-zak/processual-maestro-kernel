from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from processual_api.routers.governance import (
    get_administrator_governance_read_service,
    platform_admin_step_up_dependency,
    router,
)

ACTOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000401")
INVITATION_ID = uuid.UUID("00000000-0000-0000-0000-000000000402")
NOW = datetime(2026, 8, 18, 18, 30, tzinfo=UTC)


class _ReadService:
    async def list_invitations(self, *, limit: int = 100):
        assert limit == 25
        return (
            SimpleNamespace(
                invitation_id=INVITATION_ID,
                email_normalized="supervisor@example.com",
                supervision_level="operations_supervisor",
                status="pending",
                invited_by_user_id=ACTOR_ID,
                invite_reason="Operations coverage requires an additional supervisor",
                expires_at=NOW + timedelta(hours=24),
                accepted_by_user_id=None,
                accepted_at=None,
                cancelled_by_user_id=None,
                cancelled_at=None,
                cancellation_reason=None,
                created_at=NOW,
            ),
        )


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[platform_admin_step_up_dependency] = lambda: {
        "session_type": "identity_user",
        "user_id": str(ACTOR_ID),
    }
    app.dependency_overrides[get_administrator_governance_read_service] = lambda: _ReadService()
    return TestClient(app)


def test_invitation_read_returns_provenance_without_secret_material() -> None:
    response = _client().get("/governance/administrator-invitations?limit=25")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    invitation = payload["invitations"][0]
    assert invitation["invitation_id"] == str(INVITATION_ID)
    assert invitation["email_normalized"] == "supervisor@example.com"
    assert invitation["status"] == "pending"
    assert invitation["cancellation_reason"] is None
    assert "invitation_token" not in invitation
    assert "token_hash" not in invitation
    assert "payload_ciphertext" not in invitation


def test_invitation_read_requires_platform_admin_step_up_by_default() -> None:
    app = FastAPI()
    app.include_router(router)
    response = TestClient(app).get("/governance/administrator-invitations")

    assert response.status_code == 401
