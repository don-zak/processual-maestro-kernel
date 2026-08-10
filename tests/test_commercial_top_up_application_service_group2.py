from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from types import TracebackType
from typing import Self

import pytest

from processual_api.billing.commercial_event_contracts import CommercialEvent
from processual_api.billing.commercial_settings_top_up_checkout_contracts import (
    TopUpCheckoutChannel,
)
from processual_api.billing.commercial_top_up_application_service import (
    CommercialTopUpApplicationService,
    CreateTopUpOrderCommand,
    RecordPaymentAndGrantCommand,
    TopUpApplicationConflictError,
    TopUpApplicationOutcome,
    TopUpApplicationPolicy,
    TopUpApplicationServiceDisabledError,
    build_top_up_application_service_status,
)
from processual_api.billing.commercial_top_up_models import (
    CommercialTopUpAuditRecord,
    CommercialTopUpGrant,
    CommercialTopUpOrder,
    CommercialTopUpPaymentEvidence,
)
from processual_api.billing.commercial_top_up_order_grant_contracts import (
    TopUpOrderState,
    UnitGrantOutcome,
)


class FakeOrderRepository:
    def __init__(self) -> None:
        self.items: dict[uuid.UUID, CommercialTopUpOrder] = {}

    async def get_by_id(
        self,
        order_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> CommercialTopUpOrder | None:
        assert isinstance(for_update, bool)
        return self.items.get(order_id)

    async def get_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> CommercialTopUpOrder | None:
        return next(
            (item for item in self.items.values() if item.idempotency_key == idempotency_key),
            None,
        )

    def add(self, order: CommercialTopUpOrder) -> None:
        self.items[order.id] = order


class FakePaymentRepository:
    def __init__(self) -> None:
        self.items: list[CommercialTopUpPaymentEvidence] = []

    async def get_for_order(
        self,
        order_id: uuid.UUID,
    ) -> CommercialTopUpPaymentEvidence | None:
        return next((item for item in self.items if item.order_id == order_id), None)

    async def get_by_provider_reference(
        self,
        provider_reference: str,
    ) -> CommercialTopUpPaymentEvidence | None:
        return next(
            (item for item in self.items if item.provider_reference == provider_reference),
            None,
        )

    def add(self, payment: CommercialTopUpPaymentEvidence) -> None:
        self.items.append(payment)


class FakeGrantRepository:
    def __init__(self) -> None:
        self.items: list[CommercialTopUpGrant] = []

    async def get_for_order(
        self,
        order_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> CommercialTopUpGrant | None:
        assert isinstance(for_update, bool)
        return next((item for item in self.items if item.order_id == order_id), None)

    async def get_by_idempotency_key(
        self,
        grant_idempotency_key: str,
    ) -> CommercialTopUpGrant | None:
        return next(
            (
                item
                for item in self.items
                if item.grant_idempotency_key == grant_idempotency_key
            ),
            None,
        )

    def add(self, grant: CommercialTopUpGrant) -> None:
        self.items.append(grant)


class FakeAuditRepository:
    def __init__(self) -> None:
        self.items: list[CommercialTopUpAuditRecord] = []

    def append(self, record: CommercialTopUpAuditRecord) -> None:
        self.items.append(record)


class FakeEventLedgerRepository:
    def __init__(self) -> None:
        self.items: dict[str, CommercialEvent] = {}
        self.pending: dict[str, CommercialEvent] = {}

    async def get_by_idempotency_key(self, canonical_key: str) -> CommercialEvent | None:
        return self.pending.get(canonical_key) or self.items.get(canonical_key)

    def append(self, event: CommercialEvent) -> None:
        self.pending[event.idempotency_key.canonical] = event

    def commit(self) -> None:
        self.items.update(self.pending)
        self.pending.clear()

    def rollback(self) -> None:
        self.pending.clear()


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.orders = FakeOrderRepository()
        self.payments = FakePaymentRepository()
        self.grants = FakeGrantRepository()
        self.audit = FakeAuditRepository()
        self.event_ledger = FakeEventLedgerRepository()
        self.commits = 0
        self.rollbacks = 0

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if exc_type is not None or self.commits == 0:
            self.event_ledger.rollback()
            self.rollbacks += 1

    async def commit(self) -> None:
        self.event_ledger.commit()
        self.commits += 1

    async def rollback(self) -> None:
        self.event_ledger.rollback()
        self.rollbacks += 1


def enabled_policy(*, event_ledger_enabled: bool = True) -> TopUpApplicationPolicy:
    return TopUpApplicationPolicy(
        order_creation_enabled=True,
        payment_verification_enabled=True,
        grant_execution_enabled=True,
        order_storage_enabled=True,
        payment_storage_enabled=True,
        grant_storage_enabled=True,
        audit_storage_enabled=True,
        event_ledger_enabled=event_ledger_enabled,
    )


def create_command(*, order_id: uuid.UUID | None = None) -> CreateTopUpOrderCommand:
    return CreateTopUpOrderCommand(
        order_id=order_id or uuid.uuid4(),
        account_id=uuid.uuid4(),
        subscription_id=uuid.uuid4(),
        plan_code="starter",
        requested_units=20_000,
        bundle_count=2,
        total_price_usd=Decimal("118.00"),
        channel=TopUpCheckoutChannel.LEMON_SQUEEZY,
        idempotency_key="client-order-001",
        actor_reference="customer:test",
        evidence_reference="checkout://confirmation/001",
    )


def payment_command(order_id: uuid.UUID) -> RecordPaymentAndGrantCommand:
    return RecordPaymentAndGrantCommand(
        order_id=order_id,
        provider_reference="provider-payment-001",
        verified_amount=Decimal("118.00"),
        verified_currency="USD",
        immutable_evidence_reference="audit://payment/001",
        actor_reference="payment-verifier:test",
    )


async def create_and_grant(
    *,
    uow: FakeUnitOfWork,
    fixed_time: datetime | None = None,
) -> tuple[
    CommercialTopUpApplicationService,
    CreateTopUpOrderCommand,
    RecordPaymentAndGrantCommand,
]:
    command = create_command()
    payment = payment_command(command.order_id)
    service = CommercialTopUpApplicationService(
        unit_of_work_factory=lambda: uow,
        policy=enabled_policy(),
        clock=(lambda: fixed_time) if fixed_time is not None else None,
    )
    await service.create_order(command)
    await service.record_payment_and_grant(payment)
    return service, command, payment


@pytest.mark.asyncio
async def test_default_policy_fails_closed_before_opening_uow() -> None:
    uow = FakeUnitOfWork()
    service = CommercialTopUpApplicationService(unit_of_work_factory=lambda: uow)

    with pytest.raises(TopUpApplicationServiceDisabledError, match="order creation"):
        await service.create_order(create_command())

    assert uow.commits == 0
    assert uow.rollbacks == 0


@pytest.mark.asyncio
async def test_order_creation_and_audit_commit_once() -> None:
    uow = FakeUnitOfWork()
    fixed_time = datetime(2026, 7, 29, 16, 0, tzinfo=UTC)
    command = create_command()
    service = CommercialTopUpApplicationService(
        unit_of_work_factory=lambda: uow,
        policy=enabled_policy(),
        clock=lambda: fixed_time,
    )

    result = await service.create_order(command)

    assert result.outcome is TopUpApplicationOutcome.CREATED
    assert result.committed is True
    assert uow.commits == 1
    assert uow.rollbacks == 0
    assert uow.orders.items[command.order_id].state == "awaiting_payment"
    assert [item.action for item in uow.audit.items] == ["order_created"]
    assert uow.event_ledger.items == {}


@pytest.mark.asyncio
async def test_order_replay_is_idempotent_without_second_commit() -> None:
    uow = FakeUnitOfWork()
    command = create_command()
    service = CommercialTopUpApplicationService(
        unit_of_work_factory=lambda: uow,
        policy=enabled_policy(),
    )

    first = await service.create_order(command)
    second = await service.create_order(command)

    assert first.committed is True
    assert second.outcome is TopUpApplicationOutcome.IDEMPOTENT_REPLAY
    assert second.committed is False
    assert uow.commits == 1
    assert len(uow.audit.items) == 1


@pytest.mark.asyncio
async def test_idempotency_conflict_rolls_back() -> None:
    uow = FakeUnitOfWork()
    first = create_command()
    conflicting = CreateTopUpOrderCommand(
        order_id=first.order_id,
        account_id=first.account_id,
        subscription_id=first.subscription_id,
        plan_code="business",
        requested_units=first.requested_units,
        bundle_count=first.bundle_count,
        total_price_usd=first.total_price_usd,
        channel=first.channel,
        idempotency_key=first.idempotency_key,
        actor_reference=first.actor_reference,
        evidence_reference=first.evidence_reference,
    )
    service = CommercialTopUpApplicationService(
        unit_of_work_factory=lambda: uow,
        policy=enabled_policy(),
    )
    await service.create_order(first)

    with pytest.raises(TopUpApplicationConflictError):
        await service.create_order(conflicting)

    assert uow.commits == 1
    assert uow.rollbacks == 1


@pytest.mark.asyncio
async def test_payment_grant_audit_and_authority_events_commit_atomically() -> None:
    uow = FakeUnitOfWork()
    _, command, _ = await create_and_grant(uow=uow)

    assert uow.commits == 2
    assert len(uow.payments.items) == 1
    assert len(uow.grants.items) == 1
    assert len(uow.event_ledger.items) == 4
    assert uow.event_ledger.pending == {}
    events = tuple(uow.event_ledger.items.values())
    assert [(event.current_state, event.next_state) for event in events] == [
        ("awaiting_payment", "payment_pending"),
        ("payment_pending", "payment_verified"),
        ("payment_verified", "grant_pending"),
        ("grant_pending", "granted"),
    ]
    assert [item.action for item in uow.audit.items] == [
        "order_created",
        "payment_verified",
        "grant_applied",
    ]
    assert uow.orders.items[command.order_id].state == "granted"


@pytest.mark.asyncio
async def test_payment_replay_does_not_duplicate_grant_audit_or_events() -> None:
    uow = FakeUnitOfWork()
    service, command, payment = await create_and_grant(uow=uow)

    replay = await service.record_payment_and_grant(payment)

    assert replay.outcome is TopUpApplicationOutcome.IDEMPOTENT_REPLAY
    assert replay.committed is False
    assert len(uow.payments.items) == 1
    assert len(uow.grants.items) == 1
    assert len(uow.audit.items) == 3
    assert len(uow.event_ledger.items) == 4
    assert uow.event_ledger.pending == {}
    assert uow.commits == 2
    assert uow.orders.items[command.order_id].state == "granted"


@pytest.mark.asyncio
async def test_event_ledger_disabled_fails_before_payment_unit_of_work() -> None:
    uow = FakeUnitOfWork()
    command = create_command()
    creator = CommercialTopUpApplicationService(
        unit_of_work_factory=lambda: uow,
        policy=enabled_policy(),
    )
    await creator.create_order(command)
    service = CommercialTopUpApplicationService(
        unit_of_work_factory=lambda: uow,
        policy=enabled_policy(event_ledger_enabled=False),
    )

    with pytest.raises(TopUpApplicationServiceDisabledError, match="event ledger"):
        await service.record_payment_and_grant(payment_command(command.order_id))

    assert uow.commits == 1
    assert uow.rollbacks == 0
    assert uow.event_ledger.items == {}
    assert uow.payments.items == []
    assert uow.grants.items == []


@pytest.mark.asyncio
async def test_unexpected_order_state_fails_before_event_staging() -> None:
    uow = FakeUnitOfWork()
    command = create_command()
    service = CommercialTopUpApplicationService(
        unit_of_work_factory=lambda: uow,
        policy=enabled_policy(),
    )
    await service.create_order(command)
    uow.orders.items[command.order_id].state = TopUpOrderState.PAYMENT_PENDING.value

    with pytest.raises(TopUpApplicationConflictError, match="awaiting_payment"):
        await service.record_payment_and_grant(payment_command(command.order_id))

    assert uow.commits == 1
    assert uow.rollbacks == 1
    assert uow.event_ledger.items == {}
    assert uow.event_ledger.pending == {}
    assert uow.payments.items == []
    assert uow.grants.items == []


@pytest.mark.asyncio
async def test_ledger_only_replay_fails_closed_without_domain_mutation() -> None:
    uow = FakeUnitOfWork()
    fixed_time = datetime(2026, 8, 10, 10, 0, tzinfo=UTC)
    service, command, payment = await create_and_grant(
        uow=uow,
        fixed_time=fixed_time,
    )
    authoritative_events = dict(uow.event_ledger.items)

    uow.payments.items.clear()
    uow.grants.items.clear()
    uow.orders.items[command.order_id].state = TopUpOrderState.AWAITING_PAYMENT.value

    with pytest.raises(TopUpApplicationConflictError, match="replay exists"):
        await service.record_payment_and_grant(payment)

    assert uow.commits == 2
    assert uow.rollbacks == 1
    assert uow.event_ledger.items == authoritative_events
    assert uow.event_ledger.pending == {}
    assert uow.payments.items == []
    assert uow.grants.items == []
    assert uow.orders.items[command.order_id].state == "awaiting_payment"


@pytest.mark.asyncio
async def test_ledger_conflict_rolls_back_without_partial_domain_records() -> None:
    uow = FakeUnitOfWork()
    fixed_time = datetime(2026, 8, 10, 10, 0, tzinfo=UTC)
    service, command, payment = await create_and_grant(
        uow=uow,
        fixed_time=fixed_time,
    )
    first_key = next(iter(uow.event_ledger.items))
    uow.event_ledger.items[first_key] = replace(
        uow.event_ledger.items[first_key],
        actor_reference="different-actor",
    )
    uow.payments.items.clear()
    uow.grants.items.clear()
    uow.orders.items[command.order_id].state = TopUpOrderState.AWAITING_PAYMENT.value

    with pytest.raises(TopUpApplicationConflictError, match="ledger conflict"):
        await service.record_payment_and_grant(payment)

    assert uow.commits == 2
    assert uow.rollbacks == 1
    assert len(uow.event_ledger.items) == 4
    assert uow.event_ledger.pending == {}
    assert uow.payments.items == []
    assert uow.grants.items == []
    assert uow.orders.items[command.order_id].state == "awaiting_payment"


@pytest.mark.asyncio
async def test_amount_mismatch_rolls_back_without_partial_records_or_events() -> None:
    uow = FakeUnitOfWork()
    command = create_command()
    service = CommercialTopUpApplicationService(
        unit_of_work_factory=lambda: uow,
        policy=enabled_policy(),
    )
    await service.create_order(command)
    mismatch = RecordPaymentAndGrantCommand(
        order_id=command.order_id,
        provider_reference="provider-payment-mismatch",
        verified_amount=Decimal("117.99"),
        verified_currency="USD",
        immutable_evidence_reference="audit://payment/mismatch",
        actor_reference="payment-verifier:test",
    )

    with pytest.raises(
        TopUpApplicationConflictError,
        match="verified amount does not match",
    ):
        await service.record_payment_and_grant(mismatch)

    assert len(uow.payments.items) == 0
    assert len(uow.grants.items) == 0
    assert len(uow.audit.items) == 1
    assert len(uow.event_ledger.items) == 0
    assert uow.event_ledger.pending == {}
    assert uow.commits == 1
    assert uow.rollbacks == 1


def test_runtime_status_remains_fully_disabled() -> None:
    status = build_top_up_application_service_status()

    assert status["status"] == "draft_review"
    assert status["fail_closed_by_default"] is True
    assert status["atomic_payment_grant_audit_required"] is True
    assert status["atomic_payment_grant_audit_event_ledger_required"] is True
    for key in (
        "order_creation_enabled",
        "payment_verification_enabled",
        "grant_execution_enabled",
        "order_storage_enabled",
        "payment_storage_enabled",
        "grant_storage_enabled",
        "audit_storage_enabled",
        "event_ledger_enabled",
    ):
        assert status[key] is False
