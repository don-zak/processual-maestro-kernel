from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from processual_api.admin_marketplace.subscription_quota_rollover_persistence import (
    AdminMarketSubscriptionQuotaCycle,
)
from processual_api.admin_marketplace.subscription_top_up_grant import (
    SubscriptionTopUpGrantCommand,
    SubscriptionTopUpGrantError,
    grant_verified_subscription_top_up_factory,
)
from processual_api.billing.commercial_quota_top_up_contracts import quote_top_up
from processual_api.billing.plan_fulfillment_catalog import (
    PLAN_FULFILLMENT_CATALOG_VERSION,
)

START = datetime(2026, 8, 1, tzinfo=UTC)
END = datetime(2026, 9, 1, tzinfo=UTC)
NOW = datetime(2026, 8, 24, tzinfo=UTC)
ORDER_ID = uuid.uuid4()
SUBSCRIPTION_ID = uuid.uuid4()
PLAN_ID = uuid.uuid4()
CYCLE_ID = uuid.uuid4()
PROVIDER_REFERENCE = "ls-order-001"


class ByIdRepository:
    def __init__(self, value: object | None) -> None:
        self.value = value

    async def get_by_id(self, value: uuid.UUID, *, for_update: bool = False):
        if self.value is None or self.value.id != value:
            return None
        return self.value


class PaymentRepository:
    def __init__(self, payment: object | None) -> None:
        self.payment = payment

    async def get_by_provider_reference(self, provider_reference: str):
        if self.payment is None or self.payment.provider_reference != provider_reference:
            return None
        return self.payment


class GrantRepository:
    def __init__(self, existing: object | None = None) -> None:
        self.existing = existing
        self.added: list[object] = []

    async def get_by_order_id(self, order_id: uuid.UUID, *, for_update: bool = False):
        if self.existing is None or self.existing.order_id != order_id:
            return None
        return self.existing

    async def get_by_idempotency_key(
        self,
        grant_idempotency_key: str,
        *,
        for_update: bool = False,
    ):
        if (
            self.existing is None
            or self.existing.grant_idempotency_key != grant_idempotency_key
        ):
            return None
        return self.existing

    def add(self, grant: object) -> None:
        self.added.append(grant)


class FakeUow:
    def __init__(
        self,
        *,
        order: object,
        subscription: object,
        plan: object,
        cycle: object,
        payment: object,
        existing_grant: object | None = None,
    ) -> None:
        self.top_up_orders = ByIdRepository(order)
        self.subscriptions = ByIdRepository(subscription)
        self.plans = ByIdRepository(plan)
        self.subscription_quota_cycles = ByIdRepository(cycle)
        self.top_up_payments = PaymentRepository(payment)
        self.subscription_top_up_grants = GrantRepository(existing_grant)
        self.commit_count = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

    async def commit(self) -> None:
        self.commit_count += 1


def _subscription(**overrides: object) -> SimpleNamespace:
    values = {
        "id": SUBSCRIPTION_ID,
        "customer_ref": "customer_001",
        "plan_id": PLAN_ID,
        "status": "active",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _plan(**overrides: object) -> SimpleNamespace:
    values = {"id": PLAN_ID, "plan_code": "starter"}
    values.update(overrides)
    return SimpleNamespace(**values)


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
        "settlement_currency": "USD",
        "settlement_amount": quote.total_price_usd,
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
        "rollover_units": 2_000,
        "top_up_units": 0,
        "used_units": 8_000,
        "version": 4,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _payment(**overrides: object) -> SimpleNamespace:
    quote = quote_top_up("starter", 10_000)
    values = {
        "order_id": ORDER_ID,
        "provider_reference": PROVIDER_REFERENCE,
        "outcome": "verified",
        "verified_amount": quote.total_price_usd,
        "verified_currency": "USD",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _command(**overrides: object) -> SubscriptionTopUpGrantCommand:
    values = {
        "order_id": ORDER_ID,
        "subscription_id": SUBSCRIPTION_ID,
        "quota_cycle_id": CYCLE_ID,
        "customer_ref": "customer_001",
        "provider_reference": PROVIDER_REFERENCE,
        "granted_at": NOW,
    }
    values.update(overrides)
    return SubscriptionTopUpGrantCommand(**values)


def _service(
    *,
    order: object | None = None,
    subscription: object | None = None,
    plan: object | None = None,
    cycle: object | None = None,
    payment: object | None = None,
    existing_grant: object | None = None,
):
    uow = FakeUow(
        order=order or _order(),
        subscription=subscription or _subscription(),
        plan=plan or _plan(),
        cycle=cycle or _cycle(),
        payment=payment or _payment(),
        existing_grant=existing_grant,
    )
    service = grant_verified_subscription_top_up_factory(
        unit_of_work_factory=lambda: uow
    )
    return service, uow


@pytest.mark.asyncio
async def test_verified_top_up_is_added_to_separate_monthly_balance() -> None:
    cycle = _cycle()
    order = _order()
    service, uow = _service(cycle=cycle, order=order)

    result = await service(_command())

    assert result.units == 10_000
    assert result.expires_at == END
    assert result.committed is True
    assert cycle.top_up_units == 10_000
    assert cycle.version == 5
    assert order.state == "granted"
    assert uow.commit_count == 1
    assert len(uow.subscription_top_up_grants.added) == 1


@pytest.mark.asyncio
async def test_grant_rechecks_eighty_percent_threshold() -> None:
    service, _ = _service(cycle=_cycle(used_units=7_999))

    with pytest.raises(SubscriptionTopUpGrantError, match="at least 80%"):
        await service(_command())


@pytest.mark.asyncio
async def test_grant_rejects_cross_customer_attempt() -> None:
    service, _ = _service()

    with pytest.raises(SubscriptionTopUpGrantError, match="ownership snapshot"):
        await service(_command(customer_ref="customer_002"))


@pytest.mark.asyncio
async def test_grant_rejects_tampered_order_ownership_snapshot() -> None:
    service, _ = _service(order=_order(quota_cycle_id=uuid.uuid4()))

    with pytest.raises(SubscriptionTopUpGrantError, match="ownership snapshot"):
        await service(_command())


@pytest.mark.asyncio
async def test_grant_rejects_tampered_order_price() -> None:
    service, _ = _service(order=_order(total_price_usd=Decimal("1.00")))

    with pytest.raises(SubscriptionTopUpGrantError, match="authoritative quote"):
        await service(_command())


@pytest.mark.asyncio
async def test_grant_rejects_payment_amount_mismatch() -> None:
    service, _ = _service(payment=_payment(verified_amount=Decimal("1.00")))

    with pytest.raises(SubscriptionTopUpGrantError, match="payment amount"):
        await service(_command())


@pytest.mark.asyncio
async def test_grant_cannot_target_a_prior_month_cycle() -> None:
    service, _ = _service()

    with pytest.raises(SubscriptionTopUpGrantError, match="current monthly"):
        await service(_command(granted_at=datetime(2026, 9, 2, tzinfo=UTC)))


@pytest.mark.asyncio
async def test_matching_replay_does_not_credit_cycle_twice() -> None:
    existing = SimpleNamespace(
        id=uuid.uuid4(),
        order_id=ORDER_ID,
        subscription_id=SUBSCRIPTION_ID,
        quota_cycle_id=CYCLE_ID,
        customer_ref="customer_001",
        provider_reference=PROVIDER_REFERENCE,
        grant_idempotency_key=f"subscription-top-up:{ORDER_ID}",
        units=10_000,
        expires_at=END,
    )
    cycle = _cycle(top_up_units=10_000)
    service, uow = _service(cycle=cycle, existing_grant=existing)

    result = await service(_command())

    assert result.idempotent_replay is True
    assert result.committed is False
    assert cycle.top_up_units == 10_000
    assert uow.commit_count == 0


@pytest.mark.asyncio
async def test_conflicting_replay_fails_closed() -> None:
    existing = SimpleNamespace(
        id=uuid.uuid4(),
        order_id=ORDER_ID,
        subscription_id=SUBSCRIPTION_ID,
        quota_cycle_id=CYCLE_ID,
        customer_ref="customer_001",
        provider_reference="different-payment",
        grant_idempotency_key=f"subscription-top-up:{ORDER_ID}",
        units=10_000,
        expires_at=END,
    )
    service, _ = _service(existing_grant=existing)

    with pytest.raises(SubscriptionTopUpGrantError, match="replay conflicts"):
        await service(_command())


def test_available_units_include_top_up_but_locked_rollover_stays_excluded() -> None:
    cycle = AdminMarketSubscriptionQuotaCycle(
        base_limit_units=10_000,
        rollover_units=2_000,
        top_up_units=5_000,
        used_units=12_000,
        rollover_status="locked_for_delinquency",
    )

    assert cycle.available_units == 3_000
