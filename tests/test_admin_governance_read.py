from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from processual_api.routers.governance import (
    get_administrator_governance_read_service,
    platform_admin_step_up_dependency,
    router,
)
from processual_api.services.admin_governance_read import AdministratorAuthorityView


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


def _app_with(service) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[platform_admin_step_up_dependency] = lambda: {
        "session_type": "identity_user",
        "user_id": "00000000-0000-0000-0000-000000000001",
    }
    app.dependency_overrides[get_administrator_governance_read_service] = lambda: service
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
