from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

import pytest

from processual_api.admin_governance.invitation_service import (
    AdministratorInvitationCommand,
    AdministratorInvitationConflictError,
    AdministratorInvitationDeniedError,
    AdministratorInvitationService,
)


class FakeInvitationRepository:
    def __init__(self) -> None:
        self.actor_admin = object()
        self.existing_identity = False
        self.active_invitation = None
        self.added: dict[str, object] | None = None

    async def active_platform_admin(self, *, user_id: uuid.UUID):
        del user_id
        return self.actor_admin

    async def identity_exists(self, *, email_normalized: str) -> bool:
        del email_normalized
        return self.existing_identity

    async def active_invitation_for_email(self, *, email_normalized: str):
        del email_normalized
        return self.active_invitation

    def add_invitation(self, **values):
        self.added = values
        return values


class FakeInvitationUnitOfWork:
    def __init__(self, repository: FakeInvitationRepository) -> None:
        self.repository = repository
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True


def _service(
    repository: FakeInvitationRepository,
) -> tuple[AdministratorInvitationService, FakeInvitationUnitOfWork]:
    unit = FakeInvitationUnitOfWork(repository)
    service = AdministratorInvitationService(
        unit_of_work_factory=lambda: unit,
        clock=lambda: datetime(2026, 8, 18, 10, 0, tzinfo=UTC),
        invitation_id_factory=lambda: uuid.UUID("00000000-0000-0000-0000-000000000049"),
    )
    return service, unit


@pytest.mark.asyncio
async def test_issue_persists_hash_only_email_bound_invitation() -> None:
    repository = FakeInvitationRepository()
    service, unit = _service(repository)
    actor_id = uuid.uuid4()

    receipt = await service.issue(
        actor_user_id=actor_id,
        command=AdministratorInvitationCommand(
            email="  ADMIN.EXAMPLE@Example.COM ",
            supervision_level="operations_supervisor",
            reason="Approved for bounded commercial operations supervision.",
            expires_in_hours=48,
        ),
        recent_step_up=True,
    )

    assert unit.committed is True
    assert receipt.email_normalized == "admin.example@example.com"
    assert receipt.supervision_level == "operations_supervisor"
    assert receipt.invitation_token
    assert repository.added is not None
    assert repository.added["email_normalized"] == receipt.email_normalized
    assert repository.added["invited_by_user_id"] == actor_id
    assert repository.added["token_hash"] == hashlib.sha256(
        receipt.invitation_token.encode("utf-8")
    ).hexdigest()
    assert repository.added["token_hash"] != receipt.invitation_token
    assert "invitation_token" not in repository.added


@pytest.mark.asyncio
async def test_issue_requires_recent_platform_admin_mfa_step_up() -> None:
    repository = FakeInvitationRepository()
    service, unit = _service(repository)

    with pytest.raises(AdministratorInvitationDeniedError, match="MFA step-up"):
        await service.issue(
            actor_user_id=uuid.uuid4(),
            command=AdministratorInvitationCommand(
                email="admin@example.com",
                supervision_level="review_supervisor",
                reason="Approved for independent governance review access.",
            ),
            recent_step_up=False,
        )

    assert unit.committed is False
    assert repository.added is None


@pytest.mark.asyncio
async def test_issue_requires_active_platform_admin_actor() -> None:
    repository = FakeInvitationRepository()
    repository.actor_admin = None
    service, unit = _service(repository)

    with pytest.raises(AdministratorInvitationDeniedError, match="authority"):
        await service.issue(
            actor_user_id=uuid.uuid4(),
            command=AdministratorInvitationCommand(
                email="admin@example.com",
                supervision_level="review_supervisor",
                reason="Approved for independent governance review access.",
            ),
            recent_step_up=True,
        )

    assert unit.committed is False


@pytest.mark.asyncio
async def test_issue_rejects_existing_identity_or_active_invitation() -> None:
    repository = FakeInvitationRepository()
    service, _unit = _service(repository)

    repository.existing_identity = True
    with pytest.raises(AdministratorInvitationConflictError, match="identity already exists"):
        await service.issue(
            actor_user_id=uuid.uuid4(),
            command=AdministratorInvitationCommand(
                email="admin@example.com",
                supervision_level="review_supervisor",
                reason="Approved for independent governance review access.",
            ),
            recent_step_up=True,
        )

    repository.existing_identity = False
    repository.active_invitation = object()
    with pytest.raises(AdministratorInvitationConflictError, match="invitation already exists"):
        await service.issue(
            actor_user_id=uuid.uuid4(),
            command=AdministratorInvitationCommand(
                email="admin@example.com",
                supervision_level="review_supervisor",
                reason="Approved for independent governance review access.",
            ),
            recent_step_up=True,
        )


@pytest.mark.asyncio
async def test_issue_does_not_allow_owner_or_platform_admin_invitation_level() -> None:
    repository = FakeInvitationRepository()
    service, _unit = _service(repository)

    for level in ("owner_supervisor", "platform_admin"):
        with pytest.raises(AdministratorInvitationDeniedError, match="not invite-eligible"):
            await service.issue(
                actor_user_id=uuid.uuid4(),
                command=AdministratorInvitationCommand(
                    email="admin@example.com",
                    supervision_level=level,
                    reason="Attempted elevation beyond bounded invitation authority.",
                ),
                recent_step_up=True,
            )
