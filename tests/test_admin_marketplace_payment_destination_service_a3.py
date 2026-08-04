from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from processual_api.admin_marketplace.authority import (
    PLATFORM_ADMIN_AUTHORITY,
    authority_context,
)
from processual_api.admin_marketplace.errors import (
    AdminMarketplaceStepUpRequiredError,
    PaymentDestinationConflictError,
    PaymentDestinationNotFoundError,
)
from processual_api.admin_marketplace.models import (
    AdminMarketPaymentDestination,
)
from processual_api.admin_marketplace.payment_destination_contracts import (
    PaymentDestinationCreateContract,
    PaymentDestinationStatus,
    PaymentDestinationType,
)
from processual_api.admin_marketplace.payment_destination_crypto import (
    EncryptedPaymentDestinationIdentifier,
)
from processual_api.admin_marketplace.payment_destination_service import (
    PaymentDestinationAdministrationService,
)

NOW = datetime(2026, 8, 4, 18, 0, tzinfo=UTC)

DESTINATION_ID = uuid.UUID(
    "10000000-0000-0000-0000-000000000001"
)
AUDIT_ID = uuid.UUID(
    "20000000-0000-0000-0000-000000000001"
)
EVENT_ID = uuid.UUID(
    "30000000-0000-0000-0000-000000000001"
)


class FakeCipher:
    def __init__(self) -> None:
        self.encrypt_calls: list[dict[str, str]] = []
        self.decrypt_calls = 0

    def encrypt(
        self,
        raw_identifier: str,
        *,
        payment_destination_id: str,
        destination_ref: str,
    ) -> EncryptedPaymentDestinationIdentifier:
        self.encrypt_calls.append(
            {
                "raw_identifier": raw_identifier,
                "payment_destination_id": payment_destination_id,
                "destination_ref": destination_ref,
            }
        )
        return EncryptedPaymentDestinationIdentifier(
            ciphertext=b"nonce-and-authenticated-ciphertext",
            key_version="key-v1",
        )

    def decrypt(self, *args, **kwargs):  # pragma: no cover
        self.decrypt_calls += 1
        raise AssertionError(
            "Administration service must not decrypt destination identifiers."
        )


class FakePaymentDestinationRepository:
    def __init__(
        self,
        destinations: list[AdminMarketPaymentDestination] | None = None,
    ) -> None:
        self.destinations = {
            destination.destination_ref: destination
            for destination in (destinations or [])
        }
        self.get_calls: list[tuple[str, bool]] = []
        self.default_lock_calls: list[bool] = []
        self.added: list[AdminMarketPaymentDestination] = []

    async def list_all(self):
        return tuple(self.destinations.values())

    async def get_by_ref(
        self,
        destination_ref: str,
        *,
        for_update: bool = False,
    ):
        normalized = destination_ref.strip().lower()
        self.get_calls.append((normalized, for_update))
        return self.destinations.get(normalized)

    async def get_by_creation_idempotency_key_hash(
        self,
        key_hash: str,
        *,
        for_update: bool = False,
    ):
        del for_update
        return next(
            (
                destination
                for destination in self.destinations.values()
                if destination.creation_idempotency_key_hash == key_hash
            ),
            None,
        )

    async def get_by_id(
        self,
        destination_id: uuid.UUID,
        *,
        for_update: bool = False,
    ):
        for destination in self.destinations.values():
            if destination.id == destination_id:
                return destination
        return None

    async def get_active_default(
        self,
        *,
        for_update: bool = False,
    ):
        self.default_lock_calls.append(for_update)
        for destination in self.destinations.values():
            if (
                destination.sales_channel == "maestro_direct"
                and destination.country_code == "TN"
                and destination.currency == "TND"
                and destination.status == "active"
                and destination.is_active
                and destination.is_default
            ):
                return destination
        return None

    def add(
        self,
        destination: AdminMarketPaymentDestination,
    ) -> None:
        self.added.append(destination)
        self.destinations[destination.destination_ref] = destination


class FakeAuditRepository:
    def __init__(self) -> None:
        self.records = []

    def append(self, record) -> None:
        self.records.append(record)


class FakeUnitOfWork:
    def __init__(
        self,
        payment_destinations: FakePaymentDestinationRepository,
    ) -> None:
        self.payment_destinations = payment_destinations
        self.commercial_audit = FakeAuditRepository()
        self.enter_calls = 0
        self.exit_calls = 0
        self.commit_calls = 0
        self.rollback_calls = 0

    async def __aenter__(self):
        self.enter_calls += 1
        return self

    async def __aexit__(
        self,
        exc_type,
        exc,
        traceback,
    ) -> None:
        self.exit_calls += 1

    async def commit(self) -> None:
        self.commit_calls += 1

    async def rollback(self) -> None:
        self.rollback_calls += 1


def _authority(
    *,
    step_up: bool = True,
):
    return authority_context(
        user_id="admin_001",
        session_id="session_001",
        platform_authorities={PLATFORM_ADMIN_AUTHORITY},
        active_platform_admin=True,
        recent_mfa_step_up=step_up,
    )


def _command(
    *,
    destination_ref: str = "bank-primary",
    raw_identifier: str = "TN5901000000000000000000",
):
    return PaymentDestinationCreateContract(
        destination_ref=destination_ref,
        display_name="Primary Tunisian bank",
        destination_type=PaymentDestinationType.BANK_ACCOUNT,
        institution_name="Example Tunisian Bank",
        account_holder_name="Processual Maestro",
        raw_account_identifier=raw_identifier,
        instructions="Include the unique payment reference.",
    )


def _destination(
    *,
    destination_id: uuid.UUID = DESTINATION_ID,
    destination_ref: str = "bank-primary",
    status: str = "draft",
    is_active: bool = False,
    is_default: bool = False,
):
    validated = status != "draft"
    effective_at = NOW if status in {"active", "inactive"} else None
    expires_at = NOW if status == "inactive" else None

    return AdminMarketPaymentDestination(
        id=destination_id,
        destination_ref=destination_ref,
        display_name="Primary Tunisian bank",
        destination_type="bank_account",
        institution_name="Example Tunisian Bank",
        account_holder_name="Processual Maestro",
        identifier_ciphertext=b"nonce-and-authenticated-ciphertext",
        identifier_key_version="key-v1",
        masked_identifier="********************0000",
        country_code="TN",
        currency="TND",
        sales_channel="maestro_direct",
        status=status,
        validation_method="structural" if validated else None,
        validation_reason_code=(
            "structurally_validated" if validated else None
        ),
        validated_at=NOW if validated else None,
        is_active=is_active,
        is_default=is_default,
        effective_at=effective_at,
        expires_at=expires_at,
        instructions="Include the unique payment reference.",
        created_at=NOW,
        updated_at=NOW,
    )


def _id_factory():
    values = iter(
        (
            DESTINATION_ID,
            AUDIT_ID,
            uuid.UUID("20000000-0000-0000-0000-000000000002"),
            uuid.UUID("20000000-0000-0000-0000-000000000003"),
            uuid.UUID("20000000-0000-0000-0000-000000000004"),
            uuid.UUID("20000000-0000-0000-0000-000000000005"),
        )
    )

    def factory() -> uuid.UUID:
        return next(values)

    return factory


def _service(
    destinations: list[AdminMarketPaymentDestination] | None = None,
):
    repository = FakePaymentDestinationRepository(destinations)
    unit = FakeUnitOfWork(repository)
    cipher = FakeCipher()

    service = PaymentDestinationAdministrationService(
        unit_of_work_factory=lambda: unit,
        cipher=cipher,  # type: ignore[arg-type]
        clock=lambda: NOW,
        id_factory=_id_factory(),
        event_id_factory=lambda: EVENT_ID,
    )

    return service, repository, unit, cipher


@pytest.mark.asyncio
async def test_create_encrypts_identifier_and_appends_safe_audit() -> None:
    service, repository, unit, cipher = _service()

    result = await service.create(
        authority=_authority(),
        command=_command(),
        correlation_id="correlation-create-001",
    )

    assert result.destination_id == DESTINATION_ID
    assert result.status is PaymentDestinationStatus.DRAFT
    assert result.is_active is False
    assert result.is_default is False

    assert len(repository.added) == 1
    destination = repository.added[0]

    assert destination.identifier_ciphertext != (
        _command().raw_account_identifier.encode()
    )
    assert destination.identifier_key_version == "key-v1"
    assert destination.masked_identifier.endswith("0000")

    assert cipher.encrypt_calls == [
        {
            "raw_identifier": "TN5901000000000000000000",
            "payment_destination_id": str(DESTINATION_ID),
            "destination_ref": "bank-primary",
        }
    ]
    assert cipher.decrypt_calls == 0

    assert unit.commit_calls == 1
    assert len(unit.commercial_audit.records) == 1

    audit = unit.commercial_audit.records[0]
    assert audit.action == "payment_destination_created"
    assert audit.resource_type == "payment_destination"
    assert audit.resource_id == "bank-primary"
    assert audit.previous_state_digest is None
    assert len(audit.new_state_digest) == 64

    serialized_audit = repr(
        {
            "metadata": audit.metadata_json,
            "new_state_digest": audit.new_state_digest,
        }
    )

    assert "TN5901000000000000000000" not in serialized_audit
    assert "ciphertext" not in serialized_audit.lower()
    assert "masked_identifier" not in serialized_audit.lower()
    assert "key-v1" not in serialized_audit


@pytest.mark.asyncio
async def test_invalid_identifier_is_rejected_before_unit_of_work() -> None:
    factory = MagicMock()
    cipher = FakeCipher()

    service = PaymentDestinationAdministrationService(
        unit_of_work_factory=factory,
        cipher=cipher,  # type: ignore[arg-type]
        clock=lambda: NOW,
    )

    with pytest.raises(
        PaymentDestinationConflictError,
        match="identifier rejected",
    ):
        await service.create(
            authority=_authority(),
            command=_command(raw_identifier="12345678"),
            correlation_id="correlation-create-invalid",
        )

    factory.assert_not_called()
    assert cipher.encrypt_calls == []


@pytest.mark.asyncio
async def test_recent_mfa_is_required_before_database_access() -> None:
    factory = MagicMock()

    service = PaymentDestinationAdministrationService(
        unit_of_work_factory=factory,
        cipher=FakeCipher(),  # type: ignore[arg-type]
        clock=lambda: NOW,
    )

    with pytest.raises(AdminMarketplaceStepUpRequiredError):
        await service.create(
            authority=_authority(step_up=False),
            command=_command(),
            correlation_id="correlation-no-mfa",
        )

    factory.assert_not_called()


@pytest.mark.asyncio
async def test_create_rejects_duplicate_reference_atomically() -> None:
    existing = _destination()
    service, repository, unit, cipher = _service([existing])

    with pytest.raises(
        PaymentDestinationConflictError,
        match="reference already exists",
    ):
        await service.create(
            authority=_authority(),
            command=_command(),
            correlation_id="correlation-duplicate",
        )

    assert repository.added == []
    assert unit.commercial_audit.records == []
    assert unit.commit_calls == 0

    # The duplicate is rejected before encryption or persistence.
    assert len(cipher.encrypt_calls) == 0


@pytest.mark.asyncio
async def test_create_and_validate_is_atomic_and_audits_both_states() -> None:
    service, repository, unit, cipher = _service()

    result = await service.create_and_validate(
        authority=_authority(),
        command=_command(),
        correlation_id="correlation-create-validate-001",
    )

    assert result.status is PaymentDestinationStatus.VALIDATED
    assert result.validation_method == "structural"
    assert result.validation_reason_code == "structurally_validated"
    assert result.masked_identifier.endswith("0000")
    assert result.is_active is False
    assert result.is_default is False
    assert len(repository.added) == 1
    assert len(cipher.encrypt_calls) == 1
    assert unit.commit_calls == 1
    assert [record.action for record in unit.commercial_audit.records] == [
        "payment_destination_created",
        "payment_destination_validated",
    ]
    assert {
        record.correlation_id
        for record in unit.commercial_audit.records
    } == {"correlation-create-validate-001"}


@pytest.mark.asyncio
async def test_create_and_validate_retry_is_idempotent() -> None:
    service, repository, unit, cipher = _service()
    idempotency_key = "payment-destination-create-validate-001"

    first = await service.create_and_validate(
        authority=_authority(),
        command=_command(),
        correlation_id="correlation-first",
        idempotency_key=idempotency_key,
    )
    second = await service.create_and_validate(
        authority=_authority(),
        command=_command(),
        correlation_id="correlation-retry",
        idempotency_key=idempotency_key,
    )

    assert first.destination_id == second.destination_id
    assert second.reason_code == "payment_destination_create_validate_idempotent"
    assert len(repository.added) == 1
    assert len(cipher.encrypt_calls) == 1
    assert unit.commit_calls == 1
    assert len(unit.commercial_audit.records) == 2


@pytest.mark.asyncio
async def test_idempotency_key_cannot_be_rebound_to_another_reference() -> None:
    service, repository, unit, _ = _service()
    idempotency_key = "payment-destination-create-validate-001"

    await service.create_and_validate(
        authority=_authority(),
        command=_command(),
        correlation_id="correlation-first",
        idempotency_key=idempotency_key,
    )

    with pytest.raises(PaymentDestinationConflictError, match="Idempotency"):
        await service.create_and_validate(
            authority=_authority(),
            command=_command(destination_ref="bank-secondary"),
            correlation_id="correlation-conflict",
            idempotency_key=idempotency_key,
        )

    assert len(repository.added) == 1
    assert unit.commit_calls == 1


@pytest.mark.asyncio
async def test_payment_destination_reads_do_not_require_recent_mfa() -> None:
    destination = _destination(status="active", is_active=True, is_default=True)
    service, _, _, _ = _service([destination])
    authority = _authority(step_up=False)

    listed = await service.list_destinations(authority=authority)
    selected = await service.get_destination(
        authority=authority,
        destination_ref="bank-primary",
    )
    default = await service.get_default_destination(authority=authority)

    assert len(listed) == 1
    assert selected.destination_ref == "bank-primary"
    assert default.is_default is True


@pytest.mark.asyncio
async def test_validate_activate_and_deactivate_lifecycle() -> None:
    destination = _destination()
    service, repository, unit, cipher = _service([destination])

    validated = await service.validate(
        authority=_authority(),
        destination_ref="bank-primary",
        correlation_id="correlation-validate",
    )

    assert validated.status is PaymentDestinationStatus.VALIDATED
    assert destination.validation_method == "structural"
    assert destination.validation_reason_code == "structurally_validated"
    assert destination.validated_at == NOW

    activated = await service.activate(
        authority=_authority(),
        destination_ref="bank-primary",
        correlation_id="correlation-activate",
    )

    assert activated.status is PaymentDestinationStatus.ACTIVE
    assert destination.is_active is True
    assert destination.is_default is False
    assert destination.effective_at == NOW

    deactivated = await service.deactivate(
        authority=_authority(),
        destination_ref="bank-primary",
        correlation_id="correlation-deactivate",
    )

    assert deactivated.status is PaymentDestinationStatus.INACTIVE
    assert destination.is_active is False
    assert destination.is_default is False
    assert destination.expires_at == NOW

    assert unit.commit_calls == 3
    assert [
        record.action
        for record in unit.commercial_audit.records
    ] == [
        "payment_destination_validated",
        "payment_destination_activated",
        "payment_destination_deactivated",
    ]

    assert repository.get_calls == [
        ("bank-primary", True),
        ("bank-primary", True),
        ("bank-primary", True),
    ]
    assert cipher.decrypt_calls == 0


@pytest.mark.asyncio
async def test_set_default_switches_destinations_in_one_commit() -> None:
    old_default = _destination(
        destination_id=uuid.UUID(
            "10000000-0000-0000-0000-000000000010"
        ),
        destination_ref="bank-old",
        status="active",
        is_active=True,
        is_default=True,
    )
    new_default = _destination(
        destination_id=uuid.UUID(
            "10000000-0000-0000-0000-000000000011"
        ),
        destination_ref="bank-new",
        status="active",
        is_active=True,
        is_default=False,
    )

    service, repository, unit, _ = _service(
        [old_default, new_default]
    )

    result = await service.set_default(
        authority=_authority(),
        destination_ref="bank-new",
        correlation_id="correlation-default",
    )

    assert result.is_default is True
    assert old_default.is_default is False
    assert new_default.is_default is True
    assert unit.commit_calls == 1
    assert repository.default_lock_calls == [True]

    audit = unit.commercial_audit.records[0]
    assert audit.action == "payment_destination_default_set"
    assert audit.metadata_json["previous_default_present"] == "true"


@pytest.mark.asyncio
async def test_set_default_is_idempotent_for_current_default() -> None:
    destination = _destination(
        status="active",
        is_active=True,
        is_default=True,
    )
    service, repository, unit, _ = _service([destination])

    result = await service.set_default(
        authority=_authority(),
        destination_ref="bank-primary",
        correlation_id="correlation-already-default",
    )

    assert result.reason_code == "payment_destination_already_default"
    assert result.is_default is True
    assert unit.commit_calls == 0
    assert unit.commercial_audit.records == []
    assert repository.default_lock_calls == [True]


@pytest.mark.asyncio
async def test_missing_destination_and_invalid_transition_fail_closed() -> None:
    service, _, unit, _ = _service()

    with pytest.raises(PaymentDestinationNotFoundError):
        await service.activate(
            authority=_authority(),
            destination_ref="missing",
            correlation_id="correlation-missing",
        )

    assert unit.commit_calls == 0
    assert unit.commercial_audit.records == []

    draft = _destination()
    service, _, unit, _ = _service([draft])

    with pytest.raises(
        PaymentDestinationConflictError,
        match="validated",
    ):
        await service.activate(
            authority=_authority(),
            destination_ref="bank-primary",
            correlation_id="correlation-invalid-transition",
        )

    assert unit.commit_calls == 0
    assert unit.commercial_audit.records == []
