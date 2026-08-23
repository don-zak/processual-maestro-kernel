from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from processual_api.routers.administrator_governance_history import (
    get_administrator_governance_history_service,
    platform_admin_governance_history_step_up_dependency,
)
from processual_api.routers.governance import router

TARGET_ID = uuid.UUID("00000000-0000-0000-0000-000000000722")
ACTOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000721")
INVITATION_ID = uuid.UUID("00000000-0000-0000-0000-000000000723")
NOW = datetime(2026, 8, 23, 5, 15, tzinfo=UTC)


class _Service:
    async def get_history(self, *, user_id: uuid.UUID):
        assert user_id == TARGET_ID
        return SimpleNamespace(
            user_id=TARGET_ID,
            email="supervisor@example.test",
            display_name="Supervisor",
            user_status="active",
            authorities=(
                SimpleNamespace(
                    authority="platform_supervisor",
                    status="revoked",
                    granted_by_user_id=ACTOR_ID,
                    grant_reason="Operations supervision",
                    granted_at=NOW,
                    revoked_by_user_id=ACTOR_ID,
                    revoke_reason="Access no longer required",
                    revoked_at=NOW,
                ),
            ),
            permissions=(
                SimpleNamespace(
                    permission="governance.activity.view",
                    status="revoked",
                    source_invitation_id=INVITATION_ID,
                    granted_by_user_id=ACTOR_ID,
                    grant_reason="Operations supervision",
                    granted_at=NOW,
                    revoked_by_user_id=ACTOR_ID,
                    revocation_reason="Access no longer required",
                    revoked_at=NOW,
                ),
            ),
        )


class _Missing:
    async def get_history(self, *, user_id: uuid.UUID):
        return None


def _app(service) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[platform_admin_governance_history_step_up_dependency] = lambda: {
        "session_type": "identity_user",
        "user_id": str(ACTOR_ID),
    }
    app.dependency_overrides[get_administrator_governance_history_service] = lambda: service
    return app


def test_platform_admin_can_review_revoked_authority_and_permission_history() -> None:
    response = TestClient(_app(_Service())).get(
        f"/governance/administrators/{TARGET_ID}/authority-history"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == str(TARGET_ID)
    assert body["authorities"][0]["status"] == "revoked"
    assert body["authorities"][0]["revoked_by_user_id"] == str(ACTOR_ID)
    assert body["permissions"][0]["permission"] == "governance.activity.view"
    assert body["permissions"][0]["status"] == "revoked"
    assert body["permissions"][0]["source_invitation_id"] == str(INVITATION_ID)


def test_governance_history_returns_404_for_unknown_identity() -> None:
    response = TestClient(_app(_Missing())).get(
        f"/governance/administrators/{TARGET_ID}/authority-history"
    )
    assert response.status_code == 404
