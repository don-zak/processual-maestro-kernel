from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from processual_api.admin_governance.administrator_lifecycle_service import (
    AdministratorLifecycleConflictError,
    AdministratorLifecycleDeniedError,
    AdministratorLifecycleReceipt,
    AdministratorSessionRevocationReceipt,
)
from processual_api.admin_governance.invitation_service import (
    AdministratorInvitationConflictError,
    AdministratorInvitationDeniedError,
    AdministratorInvitationReceipt,
)
from processual_api.admin_governance.permission_authority import (
    AdministratorGovernanceAuthorityContext,
)
from processual_api.routers.governance import (
    get_administrator_invitation_service,
    get_administrator_lifecycle_service,
    get_delegated_governance_authority_context,
    platform_admin_step_up_dependency,
    router,
)

ACTOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000701")
TARGET_ID = uuid.UUID("00000000-0000-0000-0000-000000000702")
SESSION_ID = uuid.UUID("00000000-0000-0000-0000-000000000703")
INVITATION_ID = uuid.UUID("00000000-0000-0000-0000-000000000704")
OUTBOX_ID = uuid.UUID("00000000-0000-0000-0000-000000000705")
NOW = datetime(2026, 8, 18, 18, 30, tzinfo=UTC)


class _InvitationService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def issue(self, **values):
        self.calls.append(values)
        command = values["command"]
        return AdministratorInvitationReceipt(
            invitation_id=INVITATION_ID,
            delivery_outbox_id=OUTBOX_ID,
            email_normalized="supervisor@example.com",
            supervision_level=command.supervision_level,
            expires_at=NOW,
            invitation_token="must-not-leak",
        )


class _InvitationDenied:
    async def issue(self, **values):
        raise AdministratorInvitationDeniedError("denied")


class _InvitationConflict:
    async def issue(self, **values):
        raise AdministratorInvitationConflictError("conflict")


class _LifecycleService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def freeze(self, **values):
        self.calls.append(("freeze", values))
        return AdministratorLifecycleReceipt(TARGET_ID, "locked", NOW)

    async def restore(self, **values):
        self.calls.append(("restore", values))
        return AdministratorLifecycleReceipt(TARGET_ID, "active", NOW)

    async def revoke_session(self, **values):
        self.calls.append(("revoke", values))
        return AdministratorSessionRevocationReceipt(TARGET_ID, SESSION_ID, NOW)


class _LifecycleDenied(_LifecycleService):
    async def freeze(self, **values):
        raise AdministratorLifecycleDeniedError("denied")


class _LifecycleConflict(_LifecycleService):
    async def restore(self, **values):
        raise AdministratorLifecycleConflictError("conflict")


AUTHORITY_CONTEXT = AdministratorGovernanceAuthorityContext(
    user_id=str(ACTOR_ID),
    session_id=str(uuid.uuid4()),
    identity_active=True,
    platform_authorities=frozenset({"platform_supervisor"}),
    active_permissions=frozenset(
        {
            "governance.administrator.freeze",
            "governance.administrator.restore",
            "governance.session.revoke",
        }
    ),
    recent_mfa_step_up=True,
)


def _app(*, invitation_service=None, lifecycle_service=None) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[platform_admin_step_up_dependency] = lambda: {
        "session_type": "identity_user",
        "user_id": str(ACTOR_ID),
    }
    app.dependency_overrides[get_delegated_governance_authority_context] = (
        lambda: AUTHORITY_CONTEXT
    )
    if invitation_service is not None:
        app.dependency_overrides[get_administrator_invitation_service] = (
            lambda: invitation_service
        )
    if lifecycle_service is not None:
        app.dependency_overrides[get_administrator_lifecycle_service] = (
            lambda: lifecycle_service
        )
    return app


def test_issue_invitation_returns_metadata_without_raw_token() -> None:
    service = _InvitationService()
    client = TestClient(_app(invitation_service=service))

    response = client.post(
        "/governance/administrator-invitations",
        json={
            "email": "Supervisor@Example.com",
            "supervision_level": "operations_supervisor",
            "reason": "Approved operations supervision onboarding request",
            "expires_in_hours": 48,
        },
    )

    assert response.status_code == 201
    assert response.json() == {
        "invitation_id": str(INVITATION_ID),
        "delivery_outbox_id": str(OUTBOX_ID),
        "email_normalized": "supervisor@example.com",
        "supervision_level": "operations_supervisor",
        "expires_at": "2026-08-18T18:30:00Z",
        "status": "pending",
    }
    assert "invitation_token" not in response.json()
    command = service.calls[0]["command"]
    assert command.email == "Supervisor@Example.com"
    assert service.calls[0]["recent_step_up"] is True


def test_issue_invitation_maps_denial_conflict_and_validation() -> None:
    payload = {
        "email": "supervisor@example.com",
        "supervision_level": "review_supervisor",
        "reason": "Approved review supervision onboarding request",
    }
    denied = TestClient(_app(invitation_service=_InvitationDenied()))
    assert denied.post("/governance/administrator-invitations", json=payload).status_code == 403

    conflict = TestClient(_app(invitation_service=_InvitationConflict()))
    assert conflict.post("/governance/administrator-invitations", json=payload).status_code == 409

    service = _InvitationService()
    invalid = TestClient(_app(invitation_service=service)).post(
        "/governance/administrator-invitations",
        json={**payload, "reason": "too short"},
    )
    assert invalid.status_code == 422
    assert service.calls == []


def test_freeze_restore_and_revoke_session_return_durable_receipts() -> None:
    service = _LifecycleService()
    client = TestClient(_app(lifecycle_service=service))
    reason = {"reason": "Approved administrator security lifecycle operation"}

    freeze = client.post(f"/governance/administrators/{TARGET_ID}/freeze", json=reason)
    restore = client.post(f"/governance/administrators/{TARGET_ID}/restore", json=reason)
    revoke = client.post(
        f"/governance/administrators/{TARGET_ID}/sessions/{SESSION_ID}/revoke",
        json=reason,
    )

    assert freeze.status_code == 200
    assert freeze.json()["status"] == "locked"
    assert restore.status_code == 200
    assert restore.json()["status"] == "active"
    assert revoke.status_code == 200
    assert revoke.json() == {
        "user_id": str(TARGET_ID),
        "session_id": str(SESSION_ID),
        "revoked_at": "2026-08-18T18:30:00Z",
    }
    assert [name for name, _values in service.calls] == ["freeze", "restore", "revoke"]


def test_lifecycle_http_maps_denial_conflict_and_reason_validation() -> None:
    reason = {"reason": "Approved administrator security lifecycle operation"}
    denied = TestClient(_app(lifecycle_service=_LifecycleDenied()))
    assert denied.post(f"/governance/administrators/{TARGET_ID}/freeze", json=reason).status_code == 403

    conflict = TestClient(_app(lifecycle_service=_LifecycleConflict()))
    assert conflict.post(f"/governance/administrators/{TARGET_ID}/restore", json=reason).status_code == 409

    service = _LifecycleService()
    invalid = TestClient(_app(lifecycle_service=service)).post(
        f"/governance/administrators/{TARGET_ID}/freeze",
        json={"reason": "short"},
    )
    assert invalid.status_code == 422
    assert service.calls == []
