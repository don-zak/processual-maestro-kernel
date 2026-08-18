from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from processual_api.admin_governance.invitation_lifecycle_service import (
    AdministratorInvitationCancellationReceipt,
    AdministratorInvitationLifecycleConflictError,
    AdministratorInvitationLifecycleDeniedError,
)
from processual_api.routers.governance import (
    get_administrator_governance_read_service,
    get_administrator_invitation_lifecycle_service,
    platform_admin_step_up_dependency,
    router,
)
from processual_api.services.admin_governance_read import AdministratorAuthorityView

ACTOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
INVITATION_ID = uuid.UUID("00000000-0000-0000-0000-000000000222")
CANCELLED_AT = datetime(2026, 8, 18, 17, 0, tzinfo=UTC)


class _ReadService:
    async def list_administrators(self):
        return (
            AdministratorAuthorityView(
                user_id=uuid.UUID("00000000-0000-0000-0000-000000000123"),
                email="admin@example.com",
                display_name="Admin Example",
                user_status="active",
                authority="platform_admin",
                authority_status="active",
                granted_at=datetime(2026, 8, 18, 8, 0, tzinfo=UTC),
            ),
        )


class _FailingReadService:
    async def list_administrators(self):
        raise RuntimeError("database unavailable")


class _InvitationLifecycleService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def cancel(self, **values):
        self.calls.append(values)
        return AdministratorInvitationCancellationReceipt(
            invitation_id=values["invitation_id"],
            cancelled_by_user_id=values["actor_user_id"],
            cancelled_at=CANCELLED_AT,
        )


class _DeniedInvitationLifecycleService:
    async def cancel(self, **values):
        raise AdministratorInvitationLifecycleDeniedError("denied")


class _ConflictInvitationLifecycleService:
    async def cancel(self, **values):
        raise AdministratorInvitationLifecycleConflictError("conflict")


def _app_with(service) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[platform_admin_step_up_dependency] = lambda: {
        "session_type": "identity_user",
        "user_id": str(ACTOR_ID),
    }
    app.dependency_overrides[get_administrator_governance_read_service] = lambda: service
    return app


def _app_with_invitation_service(service) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[platform_admin_step_up_dependency] = lambda: {
        "session_type": "identity_user",
        "user_id": str(ACTOR_ID),
    }
    app.dependency_overrides[get_administrator_invitation_lifecycle_service] = lambda: service
    return app


def test_administrator_governance_read_returns_authoritative_identity_rows() -> None:
    client = TestClient(_app_with(_ReadService()))

    response = client.get("/governance/administrators")

    assert response.status_code == 200
    assert response.json() == {
        "administrators": [
            {
                "user_id": "00000000-0000-0000-0000-000000000123",
                "email": "admin@example.com",
                "display_name": "Admin Example",
                "user_status": "active",
                "authority": "platform_admin",
                "authority_status": "active",
                "granted_at": "2026-08-18T08:00:00Z",
            }
        ],
        "count": 1,
    }


def test_administrator_governance_read_fails_closed_when_authority_store_fails() -> None:
    client = TestClient(_app_with(_FailingReadService()))

    response = client.get("/governance/administrators")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Administrator governance authority unavailable."
    }


def test_administrator_governance_read_requires_authentication_by_default() -> None:
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.get("/governance/administrators")

    assert response.status_code == 401


def test_cancel_administrator_invitation_returns_durable_receipt() -> None:
    service = _InvitationLifecycleService()
    client = TestClient(_app_with_invitation_service(service))

    response = client.post(
        f"/governance/administrator-invitations/{INVITATION_ID}/cancel",
        json={"reason": "Invitation no longer matches the approved administrator plan"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "invitation_id": str(INVITATION_ID),
        "cancelled_by_user_id": str(ACTOR_ID),
        "cancelled_at": "2026-08-18T17:00:00Z",
        "status": "cancelled",
    }
    assert service.calls == [
        {
            "invitation_id": INVITATION_ID,
            "actor_user_id": ACTOR_ID,
            "reason": "Invitation no longer matches the approved administrator plan",
            "recent_step_up": True,
        }
    ]


def test_cancel_administrator_invitation_maps_denial_and_conflict() -> None:
    denied = TestClient(_app_with_invitation_service(_DeniedInvitationLifecycleService()))
    response = denied.post(
        f"/governance/administrator-invitations/{INVITATION_ID}/cancel",
        json={"reason": "Invitation no longer matches the approved administrator plan"},
    )
    assert response.status_code == 403
    assert response.json() == {
        "detail": "Administrator invitation cancellation denied."
    }

    conflict = TestClient(_app_with_invitation_service(_ConflictInvitationLifecycleService()))
    response = conflict.post(
        f"/governance/administrator-invitations/{INVITATION_ID}/cancel",
        json={"reason": "Invitation no longer matches the approved administrator plan"},
    )
    assert response.status_code == 409
    assert response.json() == {
        "detail": "Administrator invitation is not cancellable."
    }


def test_cancel_administrator_invitation_validates_reason_before_service_call() -> None:
    service = _InvitationLifecycleService()
    client = TestClient(_app_with_invitation_service(service))

    response = client.post(
        f"/governance/administrator-invitations/{INVITATION_ID}/cancel",
        json={"reason": "too short"},
    )

    assert response.status_code == 422
    assert service.calls == []
