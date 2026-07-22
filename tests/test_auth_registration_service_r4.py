from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime

import pytest

from processual_api.auth.delivery_crypto import (
    DeliveryPayloadCipher,
    EncryptedDeliveryPayload,
)
from processual_api.auth.registration_contracts import RegistrationMode
from processual_api.auth.registration_repository import RegistrationConflictError
from processual_api.auth.registration_service import (
    RegistrationCommand,
    RegistrationService,
)
from processual_api.auth.token_material import TokenDigester

NOW = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)


class FakePasswordService:
    def __init__(self) -> None:
        self.seen: list[str] = []

    def hash_password(self, password: str) -> str:
        self.seen.append(password)
        return "$argon2id$test-only-encoded-hash"


class FakeRepository:
    def __init__(self, *, exists: bool = False) -> None:
        self.exists = exists
        self.lookups: list[str] = []
        self.added: list[dict] = []
        self.outbox: list[dict] = []

    async def email_exists(self, email_normalized: str) -> bool:
        self.lookups.append(email_normalized)
        return self.exists

    def add_registration(self, **values) -> None:
        self.added.append(values)

    def add_delivery_outbox(self, **values) -> None:
        self.outbox.append(values)


class FakeUnitOfWork:
    def __init__(self, repository: FakeRepository, *, conflict: bool = False) -> None:
        self.repository = repository
        self.conflict = conflict
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

    async def commit(self) -> None:
        if self.conflict:
            self.repository.added.clear()
            self.repository.outbox.clear()
            raise RegistrationConflictError("duplicate")
        self.committed = True


def _service(repository: FakeRepository, *, conflict: bool = False):
    password_service = FakePasswordService()
    unit = FakeUnitOfWork(repository, conflict=conflict)
    service = RegistrationService(
        unit_of_work_factory=lambda: unit,
        password_service=password_service,
        token_digester=TokenDigester(b"p" * 32),
        delivery_cipher=DeliveryPayloadCipher(
            current_key_version="delivery-v1",
            keys={"delivery-v1": b"d" * 32},
        ),
        clock=lambda: NOW,
        slug_suffix_factory=lambda: "a1b2c3d4",
    )
    return service, password_service, unit


@pytest.mark.asyncio
async def test_individual_registration_is_atomic_and_hash_only() -> None:
    repository = FakeRepository()
    service, password_service, unit = _service(repository)

    outcome = await service.register(
        RegistrationCommand(
            mode=RegistrationMode.INDIVIDUAL,
            email=" User@Example.com ",
            display_name=" Example   User ",
            password="a sufficiently long password",
            accepted_terms_version="2026-07",
        )
    )

    assert unit.committed is True
    assert password_service.seen == ["a sufficiently long password"]
    assert asdict(outcome.receipt) == {"status": "accepted", "next_action": "check_email"}
    persisted = repository.added[0]
    assert persisted["password_hash"].startswith("$argon2id$")
    assert len(persisted["action_token_hash"]) == 64
    assert persisted["organization_id"] is None
    queued = repository.outbox[0]
    assert queued["user_id"] == persisted["user_id"]
    assert queued["action_token_id"] == persisted["action_token_id"]
    assert queued["event_type"] == "verify_email"
    raw_token = DeliveryPayloadCipher(
        current_key_version="delivery-v1",
        keys={"delivery-v1": b"d" * 32},
    ).decrypt(
        EncryptedDeliveryPayload(
            ciphertext=queued["payload_ciphertext"],
            key_version=queued["payload_key_version"],
        ),
        outbox_id=str(queued["outbox_id"]),
        user_id=str(queued["user_id"]),
        action_token_id=str(queued["action_token_id"]),
        purpose="verify_email",
    )
    assert TokenDigester(b"p" * 32).matches(
        raw_token,
        persisted["action_token_hash"],
        purpose="verify_email",
    )
    assert raw_token.encode() not in queued["payload_ciphertext"]


@pytest.mark.asyncio
async def test_organization_owner_authority_is_server_derived() -> None:
    repository = FakeRepository()
    service, _, unit = _service(repository)

    outcome = await service.register(
        RegistrationCommand(
            mode=RegistrationMode.ORGANIZATION,
            email="owner@example.com",
            display_name="Owner",
            password="a sufficiently long password",
            accepted_terms_version="2026-07",
            organization_name="Example Telecom",
        )
    )

    assert unit.committed is True
    assert asdict(outcome.receipt) == {"status": "accepted", "next_action": "check_email"}
    persisted = repository.added[0]
    assert persisted["organization_name"] == "Example Telecom"
    assert persisted["organization_slug"] == "example-telecom-a1b2c3d4"
    assert persisted["organization_id"] is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("conflict", (False, True))
async def test_existing_email_and_uniqueness_race_return_same_generic_receipt(conflict: bool) -> None:
    repository = FakeRepository(exists=not conflict)
    service, password_service, _ = _service(repository, conflict=conflict)

    outcome = await service.register(
        RegistrationCommand(
            mode=RegistrationMode.INDIVIDUAL,
            email="existing@example.com",
            display_name="Existing",
            password="a sufficiently long password",
            accepted_terms_version="2026-07",
        )
    )

    assert asdict(outcome.receipt) == {"status": "accepted", "next_action": "check_email"}
    assert repository.outbox == []
    assert password_service.seen == ["a sufficiently long password"]


@pytest.mark.asyncio
async def test_non_public_mode_and_client_organization_in_individual_mode_are_rejected() -> None:
    service, _, _ = _service(FakeRepository())
    base = {
        "email": "user@example.com",
        "display_name": "User",
        "password": "a sufficiently long password",
        "accepted_terms_version": "2026-07",
    }
    with pytest.raises(ValueError):
        await service.register(RegistrationCommand(mode=RegistrationMode.PLATFORM_ADMIN_BOOTSTRAP, **base))
    with pytest.raises(ValueError):
        await service.register(
            RegistrationCommand(
                mode=RegistrationMode.INDIVIDUAL,
                organization_name="Injected Organization",
                **base,
            )
        )
