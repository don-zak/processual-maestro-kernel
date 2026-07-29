from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from types import TracebackType
from typing import Self

import pytest

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
        return next(
            (item for item in self.items if item.order_id == order_id),
            None,
        )

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
        return next(
            (item for item in self.items if item.order_id == order_id),
            None,
        )

    async def get_by_idempotency_key(
        self,
        grant_idempotency_key: str,
    ) -> CommercialTopUpGrant | None:
        return next(
            (item for item in self.items if item.grant_idempotency_key == grant_idempotency_key),
            None,
        )

    def add(self, grant: CommercialTopUpGrant) -> None:
        self.items.append(grant)


class FakeAuditRepository:
    def __init__(self) -> None:
        self.items: list[CommercialTopUpAuditRecord] = []

    def append(self, record: CommercialTopUpAuditRecord) -> None:
        self.items.append(record)


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.orders = FakeOrderRepository()
        self.payments = FakePaymentRepository()
        self.grants = FakeGrantRepository()
        self.audit = FakeAuditRepository()
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
            self.rollbacks += 1

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


def enabled_policy() -> TopUpApplicationPolicy:
    return TopUpApplicationPolicy(
        order_creation_enabled=True,
        payment_verification_enabled=True,
        grant_execution_enabled=True,
        order_storage_enabled=True,
        payment_storage_enabled=True,
        grant_storage_enabled=True,
        audit_storage_enabled=True,
    )


def create_command(
    *,
    order_id: uuid.UUID | None = None,
) -> CreateTopUpOrderCommand:
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
        verified_amount_usd=Decimal("118.00"),
        verified_currency="USD",
        immutable_evidence_reference="audit://payment/001",
        actor_reference="payment-verifier:test",
    )


@pytest.mark.asyncio
async def test_default_policy_fails_closed_before_opening_uow() -> None:
    uow = FakeUnitOfWork()
    service = CommercialTopUpApplicationService(
        unit_of_work_factory=lambda: uow,
    )

    with pytest.raises(
        TopUpApplicationServiceDisabledError,
        match="order creation",
    ):
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
async def test_payment_grant_and_two_audits_commit_atomically() -> None:
    uow = FakeUnitOfWork()
    command = create_command()
    service = CommercialTopUpApplicationService(
        unit_of_work_factory=lambda: uow,
        policy=enabled_policy(),
    )
    await service.create_order(command)

    result = await service.record_payment_and_grant(payment_command(command.order_id))

    assert result.outcome is TopUpApplicationOutcome.PAYMENT_AND_GRANT_RECORDED
    assert result.grant_outcome is UnitGrantOutcome.GRANTED
    assert result.committed is True
    assert uow.commits == 2
    assert len(uow.payments.items) == 1
    assert len(uow.grants.items) == 1
    assert [item.action for item in uow.audit.items] == [
        "order_created",
        "payment_verified",
        "grant_applied",
    ]
    assert uow.orders.items[command.order_id].state == "granted"


@pytest.mark.asyncio
async def test_payment_replay_does_not_duplicate_grant_or_audit() -> None:
    uow = FakeUnitOfWork()
    command = create_command()
    service = CommercialTopUpApplicationService(
        unit_of_work_factory=lambda: uow,
        policy=enabled_policy(),
    )
    await service.create_order(command)
    payment = payment_command(command.order_id)
    await service.record_payment_and_grant(payment)

    replay = await service.record_payment_and_grant(payment)

    assert replay.outcome is TopUpApplicationOutcome.IDEMPOTENT_REPLAY
    assert replay.committed is False
    assert len(uow.payments.items) == 1
    assert len(uow.grants.items) == 1
    assert len(uow.audit.items) == 3
    assert uow.commits == 2


@pytest.mark.asyncio
async def test_amount_mismatch_rolls_back_without_partial_records() -> None:
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
        verified_amount_usd=Decimal("117.99"),
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
    assert uow.commits == 1
    assert uow.rollbacks == 1


def test_runtime_status_remains_fully_disabled() -> None:
    status = build_top_up_application_service_status()

    assert status["status"] == "draft_review"
    assert status["fail_closed_by_default"] is True
    assert status["atomic_payment_grant_audit_required"] is True
    for key in (
        "order_creation_enabled",
        "payment_verification_enabled",
        "grant_execution_enabled",
        "order_storage_enabled",
        "payment_storage_enabled",
        "grant_storage_enabled",
        "audit_storage_enabled",
    ):
        assert status[key] is False
