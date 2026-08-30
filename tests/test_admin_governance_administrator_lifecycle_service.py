from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from processual_api.admin_governance.administrator_lifecycle_service import (
    AdministratorLifecycleConflictError,
    AdministratorLifecycleDeniedError,
    AdministratorLifecycleService,
)
from processual_api.admin_governance.permission_authority import (
    AdministratorGovernanceAuthorityContext,
)

NOW = datetime(2026, 8, 18, 16, 45, tzinfo=UTC)
ACTOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000081")
TARGET_ID = uuid.UUID("00000000-0000-0000-0000-000000000082")
SESSION_ID = uuid.UUID("00000000-0000-0000-0000-000000000083")


@dataclass
class FakeUser:
    status: str = "active"
    updated_at: datetime | None = None


@dataclass
class FakeAuthority:
    status: str = "active"


@dataclass
class FakeSession:
    id: uuid.UUID = SESSION_ID
    user_id: uuid.UUID = TARGET_ID
    expires_at: datetime = NOW + timedelta(hours=2)
    revoked_at: datetime | None = None
    revoke_reason: str | None = None


class FakeRepository:
    def __init__(self) -> None:
        self.user: FakeUser | None = FakeUser()
        self.authority: FakeAuthority | None = FakeAuthority()
        self.session: FakeSession | None = FakeSession()
        self.revocations: list[dict[str, object]] = []
        self.session_revocations: list[dict[str, object]] = []
        self.audit_events: list[dict[str, object]] = []

    async def administrator_for_update(self, *, user_id: uuid.UUID):
        return self.user if user_id == TARGET_ID else None

    async def platform_supervisor_for_update(self, *, user_id: uuid.UUID):
        return self.authority if user_id == TARGET_ID else None

    async def administrator_session_for_update(
        self,
        *,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
    ):
        if self.session is None:
            return None
        if self.session.id != session_id or self.session.user_id != user_id:
            return None
        return self.session

    async def revoke_session(
        self,
        *,
        session: FakeSession,
        revoked_at: datetime,
        reason: str,
    ) -> None:
        session.revoked_at = revoked_at
        session.revoke_reason = reason
        self.session_revocations.append(
            {
                "session_id": session.id,
                "revoked_at": revoked_at,
                "reason": reason,
            }
        )

    async def revoke_all_sessions(
        self,
        *,
        user_id: uuid.UUID,
        revoked_at: datetime,
        reason: str,
    ) -> None:
        self.revocations.append(
            {
                "user_id": user_id,
                "revoked_at": revoked_at,
                "reason": reason,
            }
        )

    def add_governance_audit_event(self, **values):
        self.audit_events.append(values)
        return values


class FakeUnitOfWork:
    def __init__(self, repository: FakeRepository) -> None:
        self.repository = repository
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True


def _context(*, permission: str, recent_step_up: bool = True):
    return AdministratorGovernanceAuthorityContext(
        user_id=str(ACTOR_ID),
        session_id=str(uuid.uuid4()),
        identity_active=True,
        platform_authorities=frozenset({"platform_supervisor"}),
        active_permissions=frozenset({permission}),
        recent_mfa_step_up=recent_step_up,
    )


def _service(repository: FakeRepository):
    unit = FakeUnitOfWork(repository)
    return (
        AdministratorLifecycleService(
            unit_of_work_factory=lambda: unit,
            clock=lambda: NOW,
        ),
        unit,
    )


@pytest.mark.asyncio
async def test_revoke_session_revokes_exact_session_and_audits() -> None:
    repository = FakeRepository()
    service, unit = _service(repository)

    receipt = await service.revoke_session(
        target_user_id=TARGET_ID,
        session_id=SESSION_ID,
        authority_context=_context(permission="governance.session.revoke"),
        reason="Security review requires revoking this administrator session",
    )

    assert unit.committed is True
    assert repository.session is not None
    assert repository.session.revoked_at == NOW
    assert repository.session.revoke_reason == "administrator_session_revoked"
    assert repository.session_revocations == [
        {
            "session_id": SESSION_ID,
            "revoked_at": NOW,
            "reason": "administrator_session_revoked",
        }
    ]
    assert repository.audit_events[0]["event_type"] == "administrator_session_revoked"
    assert repository.audit_events[0]["subject_user_id"] == TARGET_ID
    assert repository.audit_events[0]["permission"] == "governance.session.revoke"
    assert receipt.session_id == SESSION_ID
    assert receipt.revoked_at == NOW


@pytest.mark.asyncio
async def test_revoke_session_requires_exact_permission_and_recent_step_up() -> None:
    repository = FakeRepository()
    service, unit = _service(repository)

    with pytest.raises(AdministratorLifecycleDeniedError, match="exact_permission_required"):
        await service.revoke_session(
            target_user_id=TARGET_ID,
            session_id=SESSION_ID,
            authority_context=_context(permission="governance.sessions.view"),
            reason="Security review requires revoking this administrator session",
        )

    with pytest.raises(AdministratorLifecycleDeniedError, match="recent_mfa_step_up_required"):
        await service.revoke_session(
            target_user_id=TARGET_ID,
            session_id=SESSION_ID,
            authority_context=_context(
                permission="governance.session.revoke",
                recent_step_up=False,
            ),
            reason="Security review requires revoking this administrator session",
        )

    assert unit.committed is False
    assert repository.session_revocations == []
    assert repository.audit_events == []


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["missing", "revoked", "expired"])
async def test_revoke_session_rejects_non_revocable_session(state: str) -> None:
    repository = FakeRepository()
    assert repository.session is not None
    if state == "missing":
        repository.session = None
    elif state == "revoked":
        repository.session.revoked_at = NOW - timedelta(minutes=1)
    else:
        repository.session.expires_at = NOW
    service, unit = _service(repository)

    with pytest.raises(AdministratorLifecycleConflictError, match="not revocable"):
        await service.revoke_session(
            target_user_id=TARGET_ID,
            session_id=SESSION_ID,
            authority_context=_context(permission="governance.session.revoke"),
            reason="Security review requires revoking this administrator session",
        )

    assert unit.committed is False
    assert repository.session_revocations == []


@pytest.mark.asyncio
async def test_revoke_session_requires_active_target_supervisor() -> None:
    repository = FakeRepository()
    assert repository.user is not None
    repository.user.status = "locked"
    service, unit = _service(repository)

    with pytest.raises(AdministratorLifecycleConflictError, match="active state"):
        await service.revoke_session(
            target_user_id=TARGET_ID,
            session_id=SESSION_ID,
            authority_context=_context(permission="governance.session.revoke"),
            reason="Security review requires revoking this administrator session",
        )

    assert unit.committed is False


@pytest.mark.asyncio
async def test_freeze_locks_identity_revokes_sessions_and_audits() -> None:
    repository = FakeRepository()
    service, unit = _service(repository)

    receipt = await service.freeze(
        target_user_id=TARGET_ID,
        authority_context=_context(permission="governance.administrator.freeze"),
        reason="Security investigation requires temporary administrator suspension",
    )

    assert unit.committed is True
    assert repository.user is not None
    assert repository.user.status == "locked"
    assert repository.user.updated_at == NOW
    assert repository.revocations == [
        {
            "user_id": TARGET_ID,
            "revoked_at": NOW,
            "reason": "administrator_frozen",
        }
    ]
    assert repository.audit_events[0]["event_type"] == "administrator_frozen"
    assert repository.audit_events[0]["actor_user_id"] == ACTOR_ID
    assert repository.audit_events[0]["subject_user_id"] == TARGET_ID
    assert receipt.status == "locked"


@pytest.mark.asyncio
async def test_restore_activates_frozen_identity_without_restoring_sessions() -> None:
    repository = FakeRepository()
    assert repository.user is not None
    repository.user.status = "locked"
    service, unit = _service(repository)

    receipt = await service.restore(
        target_user_id=TARGET_ID,
        authority_context=_context(permission="governance.administrator.restore"),
        reason="Security review completed and administrator access is approved",
    )

    assert unit.committed is True
    assert repository.user.status == "active"
    assert repository.user.updated_at == NOW
    assert repository.revocations == []
    assert repository.audit_events[0]["event_type"] == "administrator_restored"
    assert receipt.status == "active"


@pytest.mark.asyncio
async def test_freeze_requires_exact_permission_and_recent_mfa_step_up() -> None:
    repository = FakeRepository()
    service, unit = _service(repository)

    with pytest.raises(AdministratorLifecycleDeniedError, match="exact_permission_required"):
        await service.freeze(
            target_user_id=TARGET_ID,
            authority_context=_context(permission="governance.activity.view"),
            reason="Security investigation requires temporary administrator suspension",
        )

    with pytest.raises(AdministratorLifecycleDeniedError, match="recent_mfa_step_up_required"):
        await service.freeze(
            target_user_id=TARGET_ID,
            authority_context=_context(
                permission="governance.administrator.freeze",
                recent_step_up=False,
            ),
            reason="Security investigation requires temporary administrator suspension",
        )

    assert unit.committed is False
    assert repository.revocations == []
    assert repository.audit_events == []


@pytest.mark.asyncio
async def test_freeze_rejects_self_target_and_non_active_supervisor() -> None:
    repository = FakeRepository()
    service, unit = _service(repository)

    with pytest.raises(AdministratorLifecycleDeniedError, match="self_freeze_denied"):
        await service.freeze(
            target_user_id=ACTOR_ID,
            authority_context=_context(permission="governance.administrator.freeze"),
            reason="Security investigation requires temporary administrator suspension",
        )

    assert repository.user is not None
    repository.user.status = "locked"
    with pytest.raises(AdministratorLifecycleConflictError, match="active state"):
        await service.freeze(
            target_user_id=TARGET_ID,
            authority_context=_context(permission="governance.administrator.freeze"),
            reason="Security investigation requires temporary administrator suspension",
        )

    assert unit.committed is False


@pytest.mark.asyncio
async def test_restore_only_accepts_frozen_active_platform_supervisor() -> None:
    repository = FakeRepository()
    service, unit = _service(repository)

    with pytest.raises(AdministratorLifecycleConflictError, match="not frozen"):
        await service.restore(
            target_user_id=TARGET_ID,
            authority_context=_context(permission="governance.administrator.restore"),
            reason="Security review completed and administrator access is approved",
        )

    assert repository.authority is not None
    repository.authority.status = "revoked"
    assert repository.user is not None
    repository.user.status = "locked"
    with pytest.raises(AdministratorLifecycleConflictError, match="active platform supervisor"):
        await service.restore(
            target_user_id=TARGET_ID,
            authority_context=_context(permission="governance.administrator.restore"),
            reason="Security review completed and administrator access is approved",
        )

    assert unit.committed is False


@pytest.mark.asyncio
async def test_lifecycle_reason_must_be_bounded() -> None:
    repository = FakeRepository()
    service, unit = _service(repository)

    with pytest.raises(ValueError, match="reason"):
        await service.freeze(
            target_user_id=TARGET_ID,
            authority_context=_context(permission="governance.administrator.freeze"),
            reason="too short",
        )

    assert unit.committed is False
