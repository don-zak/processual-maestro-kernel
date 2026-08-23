from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from processual_api.admin_governance.administrator_deprovision_service import (
    AdministratorDeprovisionConflictError,
    AdministratorDeprovisionDeniedError,
    AdministratorDeprovisionReceipt,
)
from processual_api.routers.administrator_deprovision import (
    get_administrator_deprovision_service,
    platform_admin_deprovision_step_up_dependency,
)
from processual_api.routers.governance import router

ACTOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000711")
TARGET_ID = uuid.UUID("00000000-0000-0000-0000-000000000712")
NOW = datetime(2026, 8, 23, 4, 45, tzinfo=UTC)


class _Service:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def revoke_supervisor_authority(self, **values):
        self.calls.append(values)
        return AdministratorDeprovisionReceipt(
            user_id=TARGET_ID,
            status="revoked",
            revoked_permission_count=3,
            occurred_at=NOW,
        )


class _Denied:
    async def revoke_supervisor_authority(self, **values):
        raise AdministratorDeprovisionDeniedError("denied")


class _Conflict:
    async def revoke_supervisor_authority(self, **values):
        raise AdministratorDeprovisionConflictError("conflict")


def _app(service) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[platform_admin_deprovision_step_up_dependency] = lambda: {
        "session_type": "identity_user",
        "user_id": str(ACTOR_ID),
    }
    app.dependency_overrides[get_administrator_deprovision_service] = lambda: service
    return app


def test_deprovision_http_requires_platform_admin_step_up_and_returns_receipt() -> None:
    service = _Service()
    client = TestClient(_app(service))

    response = client.post(
        f"/governance/administrators/{TARGET_ID}/deprovision",
        json={"reason": "Supervisor access is no longer operationally required."},
    )

    assert response.status_code == 200
    assert response.json() == {
        "user_id": str(TARGET_ID),
        "status": "revoked",
        "revoked_permission_count": 3,
        "occurred_at": "2026-08-23T04:45:00Z",
    }
    assert service.calls == [
        {
            "actor_user_id": ACTOR_ID,
            "target_user_id": TARGET_ID,
            "reason": "Supervisor access is no longer operationally required.",
            "recent_step_up": True,
        }
    ]


def test_deprovision_http_maps_denial_conflict_and_validation() -> None:
    reason = {"reason": "Supervisor access is no longer operationally required."}

    denied = TestClient(_app(_Denied())).post(
        f"/governance/administrators/{TARGET_ID}/deprovision",
        json=reason,
    )
    assert denied.status_code == 403

    conflict = TestClient(_app(_Conflict())).post(
        f"/governance/administrators/{TARGET_ID}/deprovision",
        json=reason,
    )
    assert conflict.status_code == 409

    service = _Service()
    invalid = TestClient(_app(service)).post(
        f"/governance/administrators/{TARGET_ID}/deprovision",
        json={"reason": "too short"},
    )
    assert invalid.status_code == 422
    assert service.calls == []
