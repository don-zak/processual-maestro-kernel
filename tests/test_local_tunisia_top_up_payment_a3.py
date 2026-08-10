from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from processual_api.admin_marketplace.local_tunisia_top_up_payment import (
    LocalTunisiaTopUpPaymentError,
    VerifyLocalTunisiaTopUpPaymentCommand,
    verify_local_tunisia_top_up_payment_factory,
)
from processual_api.billing.commercial_quota_top_up_contracts import quote_top_up
from processual_api.billing.plan_fulfillment_catalog import PLAN_FULFILLMENT_CATALOG_VERSION

NOW = datetime(2026, 8, 24, tzinfo=UTC)
START = datetime(2026, 8, 1, tzinfo=UTC)
END = datetime(2026, 9, 1, tzinfo=UTC)
ORDER_ID = uuid.uuid4()
SUBSCRIPTION_ID = uuid.uuid4()
PLAN_ID = uuid.uuid4()
CYCLE_ID = uuid.uuid4()


class ByIdRepo:
    def __init__(self, value: object | None) -> None:
        self.value = value

    async def get_by_id(self, value_id, *, for_update: bool = False):
        if self.value is None or self.value.id != value_id:
            return None
        return self.value


class PaymentRepo:
    def __init__(self, payment: object | None = None) -> None:
        self.payment = payment

    async def get_by_provider_reference(self, provider_reference: str):
        if self.payment is None or self.payment.provider_reference != provider_reference:
            return None
        return self.payment

    def add(self, payment: object) -> None:
        self.payment = payment


class GrantRepo:
    def __init__(self) -> None:
        self.grant = None

    async def get_by_order_id(self, order_id, *, for_update: bool = False):
        if self.grant is None or self.grant.order_id != order_id:
            return None
        return self.grant

    async def get_by_idempotency_key(self, key: str, *, for_update: bool = False):
        if self.grant is None or self.grant.grant_idempotency_key != key:
            return None
        return self.grant

    def add(self, grant: object) -> None:
        self.grant = grant


class FakeUow:
    def __init__(self, *, order: object, cycle: object, payment: object | None = None) -> None:
        self.top_up_orders = ByIdRepo(order)
        self.subscriptions = ByIdRepo(
            SimpleNamespace(
                id=SUBSCRIPTION_ID,
                customer_ref="customer_001",
                plan_id=PLAN_ID,
                status="active",
            )
        )
        self.plans = ByIdRepo(SimpleNamespace(id=PLAN_ID, plan_code="starter"))
        self.subscription_quota_cycles = ByIdRepo(cycle)
        self.top_up_payments = PaymentRepo(payment)
        self.subscription_top_up_grants = GrantRepo()
        self.commit_count = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

    async def commit(self) -> None:
        self.commit_count += 1


def _order(**overrides: object) -> SimpleNamespace:
    quote = quote_top_up("starter", 10_000)
    values = {
        "id": ORDER_ID,
        "customer_ref": "customer_001",
        "subscription_id": SUBSCRIPTION_ID,
        "quota_cycle_id": CYCLE_ID,
        "plan_code": "starter",
        "plan_catalog_version": PLAN_FULFILLMENT_CATALOG_VERSION,
        "requested_units": quote.total_units,
        "bundle_count": quote.bundle_count,
        "total_price_usd": quote.total_price_usd,
        "settlement_currency": "TND",
        "settlement_amount": Decimal("31.000"),
        "exchange_rate_usd_tnd": Decimal("3.100000"),
        "exchange_rate_source": "central-bank-feed",
        "exchange_rate_reference": "fx-20260824-001",
        "exchange_rate_observed_at": NOW - timedelta(minutes=2),
        "exchange_rate_expires_at": NOW + timedelta(minutes=10),
        "channel": "local_tunisia",
        "state": "awaiting_payment",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _cycle(**overrides: object) -> SimpleNamespace:
    values = {
        "id": CYCLE_ID,
        "subscription_id": SUBSCRIPTION_ID,
        "customer_ref": "customer_001",
        "metric_code": "credits",
        "period_start": START,
        "period_end": END,
        "plan_code": "starter",
        "plan_catalog_version": PLAN_FULFILLMENT_CATALOG_VERSION,
        "base_limit_units": 10_000,
        "used_units": 8_000,
        "top_up_units": 0,
        "version": 1,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _command(**overrides: object) -> VerifyLocalTunisiaTopUpPaymentCommand:
    values = {
        "order_id": ORDER_ID,
        "customer_ref": "customer_001",
        "provider_reference": "tn-local:receipt:001",
        "amount_tnd": Decimal("31.000"),
        "evidence_reference": "evidence:receipt:001",
        "verified_at": NOW,
    }
    values.update(overrides)
    return VerifyLocalTunisiaTopUpPaymentCommand(**values)


@pytest.mark.asyncio
async def test_matching_tnd_payment_grants_once() -> None:
    order = _order()
    cycle = _cycle()
    uow = FakeUow(order=order, cycle=cycle)
    verify = verify_local_tunisia_top_up_payment_factory(unit_of_work_factory=lambda: uow)

    result = await verify(_command())

    assert result.units == 10_000
    assert cycle.top_up_units == 10_000
    assert order.state == "granted"
    assert uow.top_up_payments.payment.verified_currency == "TND"
    assert uow.top_up_payments.payment.verified_amount == Decimal("31.000")
    assert uow.commit_count == 1


@pytest.mark.asyncio
async def test_local_payment_amount_mismatch_fails_closed() -> None:
    cycle = _cycle()
    uow = FakeUow(order=_order(), cycle=cycle)
    verify = verify_local_tunisia_top_up_payment_factory(unit_of_work_factory=lambda: uow)

    with pytest.raises(LocalTunisiaTopUpPaymentError, match="amount conflicts"):
        await verify(_command(amount_tnd=Decimal("30.999")))

    assert cycle.top_up_units == 0
    assert uow.commit_count == 0


@pytest.mark.asyncio
async def test_local_payment_rejects_cross_customer_evidence() -> None:
    uow = FakeUow(order=_order(), cycle=_cycle())
    verify = verify_local_tunisia_top_up_payment_factory(unit_of_work_factory=lambda: uow)

    with pytest.raises(LocalTunisiaTopUpPaymentError, match="customer conflicts"):
        await verify(_command(customer_ref="customer_002"))

    assert uow.commit_count == 0


@pytest.mark.asyncio
async def test_local_payment_requires_complete_fx_snapshot() -> None:
    uow = FakeUow(
        order=_order(exchange_rate_reference=None),
        cycle=_cycle(),
    )
    verify = verify_local_tunisia_top_up_payment_factory(unit_of_work_factory=lambda: uow)

    with pytest.raises(LocalTunisiaTopUpPaymentError, match="fixed exchange-rate snapshot"):
        await verify(_command())


@pytest.mark.asyncio
async def test_same_payment_reference_replays_grant_without_double_credit() -> None:
    order = _order()
    cycle = _cycle()
    uow = FakeUow(order=order, cycle=cycle)
    verify = verify_local_tunisia_top_up_payment_factory(unit_of_work_factory=lambda: uow)

    first = await verify(_command())
    second = await verify(_command())

    assert first.replayed_grant is False
    assert second.replayed_grant is True
    assert cycle.top_up_units == 10_000
    assert uow.commit_count == 1


@pytest.mark.asyncio
async def test_conflicting_existing_payment_reference_fails_closed() -> None:
    existing_payment = SimpleNamespace(
        order_id=ORDER_ID,
        provider_reference="tn-local:receipt:001",
        outcome="verified",
        verified_amount=Decimal("31.000"),
        verified_currency="TND",
        immutable_evidence_reference="different-evidence",
    )
    uow = FakeUow(order=_order(), cycle=_cycle(), payment=existing_payment)
    verify = verify_local_tunisia_top_up_payment_factory(unit_of_work_factory=lambda: uow)

    with pytest.raises(LocalTunisiaTopUpPaymentError, match="conflicts with existing evidence"):
        await verify(_command())

    assert uow.commit_count == 0
