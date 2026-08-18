from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from processual_api.admin_governance.invitation_onboarding_service import (
    AdministratorInvitationOnboardingDeniedError,
    AdministratorInvitationOnboardingService,
)
from processual_api.auth.passwords import PasswordService


@dataclass
class FakeInvitation:
    id: uuid.UUID
    email_normalized: str
    supervision_level: str
    token_hash: str
    status: str
    expires_at: datetime
    accepted_by_user_id: uuid.UUID | None = None
    accepted_at: datetime | None = None


class FakeRepository:
    def __init__(self, invitation: FakeInvitation | None) -> None:
        self.invitation = invitation
        self.identity_exists_value = False
        self.identity_values: dict[str, object] | None = None

    async def invitation_for_update(self, *, invitation_id: uuid.UUID):
        if self.invitation is None or self.invitation.id != invitation_id:
            return None
        return self.invitation

    async def identity_exists(self, *, email_normalized: str) -> bool:
        del email_normalized
        return self.identity_exists_value

    def add_onboarding_identity(self, **values):
        self.identity_values = values
        return values

    def bind_invitation_to_onboarding_identity(self, invitation, **values) -> None:
        invitation.accepted_by_user_id = values["user_id"]
        invitation.accepted_at = values["bound_at"]


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


def _invitation(*, token: str = "invite-secret") -> FakeInvitation:
    return FakeInvitation(
        id=uuid.UUID("00000000-0000-0000-0000-000000000049"),
        email_normalized="admin@example.com",
        supervision_level="operations_supervisor",
        token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
        status="pending",
        expires_at=datetime(2026, 8, 18, 12, 0, tzinfo=UTC),
    )


def _service(repository: FakeRepository) -> tuple[AdministratorInvitationOnboardingService, FakeUnitOfWork]:
    unit = FakeUnitOfWork(repository)
    service = AdministratorInvitationOnboardingService(
        unit_of_work_factory=lambda: unit,
        password_service=PasswordService(),
        clock=lambda: datetime(2026, 8, 18, 10, 0, tzinfo=UTC),
        user_id_factory=lambda: uuid.UUID("00000000-0000-0000-0000-000000000050"),
    )
    return service, unit


@pytest.mark.asyncio
async def test_start_creates_pending_identity_and_consumes_invitation_once() -> None:
    invitation = _invitation()
    repository = FakeRepository(invitation)
    service, unit = _service(repository)

    receipt = await service.start(
        invitation_id=invitation.id,
        invitation_token="invite-secret",
        display_name="  Admin Example  ",
        password="owner-chosen-password",
    )

    assert unit.committed is True
    assert receipt.next_action == "enroll_mfa"
    assert receipt.user_id == invitation.accepted_by_user_id
    assert receipt.email_normalized == "admin@example.com"
    assert repository.identity_values is not None
    assert repository.identity_values["display_name"] == "Admin Example"
    assert str(repository.identity_values["password_hash"]).startswith("$argon2id$")
    assert repository.identity_values["password_hash"] != "owner-chosen-password"
    assert invitation.accepted_at == datetime(2026, 8, 18, 10, 0, tzinfo=UTC)


@pytest.mark.asyncio
@pytest.mark.parametrize("token", ["", "wrong-token"])
async def test_start_rejects_invalid_token_without_persisting_identity(token: str) -> None:
    invitation = _invitation()
    repository = FakeRepository(invitation)
    service, unit = _service(repository)

    with pytest.raises(AdministratorInvitationOnboardingDeniedError):
        await service.start(
            invitation_id=invitation.id,
            invitation_token=token,
            display_name="Admin Example",
            password="owner-chosen-password",
        )

    assert unit.committed is False
    assert repository.identity_values is None


@pytest.mark.asyncio
async def test_start_rejects_existing_identity_or_already_consumed_invitation() -> None:
    invitation = _invitation()
    repository = FakeRepository(invitation)
    repository.identity_exists_value = True
    service, _unit = _service(repository)

    with pytest.raises(AdministratorInvitationOnboardingDeniedError):
        await service.start(
            invitation_id=invitation.id,
            invitation_token="invite-secret",
            display_name="Admin Example",
            password="owner-chosen-password",
        )

    repository.identity_exists_value = False
    invitation.accepted_by_user_id = uuid.uuid4()
    with pytest.raises(AdministratorInvitationOnboardingDeniedError):
        await service.start(
            invitation_id=invitation.id,
            invitation_token="invite-secret",
            display_name="Admin Example",
            password="owner-chosen-password",
        )


@pytest.mark.asyncio
async def test_start_does_not_grant_platform_authority() -> None:
    invitation = _invitation()
    repository = FakeRepository(invitation)
    service, _unit = _service(repository)

    await service.start(
        invitation_id=invitation.id,
        invitation_token="invite-secret",
        display_name="Admin Example",
        password="owner-chosen-password",
    )

    assert repository.identity_values is not None
    assert "authority" not in repository.identity_values
    assert "supervision_level" not in repository.identity_values
