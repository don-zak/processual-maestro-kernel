from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

import pytest

from processual_api.admin_governance.invitation_delivery_crypto import (
    AdministratorInvitationPayloadCipher,
    EncryptedAdministratorInvitationPayload,
)
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
        self.outbox: dict[str, object] | None = None

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

    def add_invitation_delivery_outbox(self, **values):
        self.outbox = values
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


def _service(repository: FakeInvitationRepository):
    unit = FakeInvitationUnitOfWork(repository)
    cipher = AdministratorInvitationPayloadCipher(
        current_key_version="test-v1",
        keys={"test-v1": b"k" * 32},
    )
    service = AdministratorInvitationService(
        unit_of_work_factory=lambda: unit,
        payload_cipher=cipher,
        clock=lambda: datetime(2026, 8, 18, 10, 0, tzinfo=UTC),
        invitation_id_factory=lambda: uuid.UUID("00000000-0000-0000-0000-000000000049"),
        outbox_id_factory=lambda: uuid.UUID("00000000-0000-0000-0000-000000000052"),
    )
    return service, unit, cipher


@pytest.mark.asyncio
async def test_issue_persists_hash_only_invitation_and_encrypted_outbox_atomically() -> None:
    repository = FakeInvitationRepository()
    service, unit, cipher = _service(repository)
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
    assert receipt.invitation_token
    assert repository.added is not None
    assert repository.outbox is not None
    assert repository.added["token_hash"] == hashlib.sha256(
        receipt.invitation_token.encode("utf-8")
    ).hexdigest()
    assert "invitation_token" not in repository.added
    assert receipt.invitation_token.encode() not in repository.outbox["payload_ciphertext"]
    recovered = cipher.decrypt(
        EncryptedAdministratorInvitationPayload(
            ciphertext=repository.outbox["payload_ciphertext"],
            key_version=repository.outbox["payload_key_version"],
        ),
        outbox_id=str(receipt.delivery_outbox_id),
        invitation_id=str(receipt.invitation_id),
        recipient_email=receipt.email_normalized,
    )
    assert recovered == receipt.invitation_token
    assert repository.outbox["idempotency_key"] == (
        f"pmk-admin-governance-invitation-v2:{receipt.invitation_id}"
    )


@pytest.mark.asyncio
async def test_issue_requires_recent_platform_admin_mfa_step_up() -> None:
    repository = FakeInvitationRepository()
    service, unit, _cipher = _service(repository)
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
    assert repository.outbox is None


@pytest.mark.asyncio
async def test_issue_requires_active_platform_admin_actor() -> None:
    repository = FakeInvitationRepository()
    repository.actor_admin = None
    service, unit, _cipher = _service(repository)
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
    assert repository.outbox is None


@pytest.mark.asyncio
async def test_issue_rejects_existing_identity_or_active_invitation() -> None:
    repository = FakeInvitationRepository()
    service, _unit, _cipher = _service(repository)
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
    service, _unit, _cipher = _service(repository)
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
