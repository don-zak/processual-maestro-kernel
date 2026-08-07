from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from processual_api.admin_marketplace.subscription_top_up_order import (
    CreateSubscriptionTopUpOrderCommand,
    SubscriptionTopUpOrderError,
    create_subscription_top_up_order_factory,
)
from processual_api.billing.commercial_settings_top_up_checkout_contracts import (
    TopUpCheckoutChannel,
)
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


class ByIdRepository:
    def __init__(self, value: object | None) -> None:
        self.value = value

    async def get_by_id(self, value: uuid.UUID, *, for_update: bool = False):
        if self.value is None or self.value.id != value:
            return None
        return self.value


class OrderRepository:
    def __init__(self, existing: object | None = None) -> None:
        self.existing = existing
        self.added: list[object] = []

    async def get_by_idempotency_key(self, key: str):
        if self.existing is None or self.existing.idempotency_key != key:
            return None
        return self.existing

    def add(self, order: object) -> None:
        self.added.append(order)


class FakeUow:
    def __init__(
        self,
        *,
        subscription: object,
        plan: object,
        cycle: object,
        existing: object | None = None,
    ) -> None:
        self.subscriptions = ByIdRepository(subscription)
        self.plans = ByIdRepository(plan)
        self.subscription_quota_cycles = ByIdRepository(cycle)
        self.top_up_orders = OrderRepository(existing)
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
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _command(**overrides: object) -> CreateSubscriptionTopUpOrderCommand:
    values = {
        "order_id": ORDER_ID,
        "customer_ref": "customer_001",
        "subscription_id": SUBSCRIPTION_ID,
        "quota_cycle_id": CYCLE_ID,
        "requested_units": 10_000,
        "channel": TopUpCheckoutChannel.LEMON_SQUEEZY,
        "idempotency_key": "top-up-order-001",
        "created_at": NOW,
    }
    values.update(overrides)
    return CreateSubscriptionTopUpOrderCommand(**values)


def _service(
    *,
    subscription: object | None = None,
    plan: object | None = None,
    cycle: object | None = None,
    existing: object | None = None,
):
    uow = FakeUow(
        subscription=subscription or _subscription(),
        plan=plan or _plan(),
        cycle=cycle or _cycle(),
        existing=existing,
    )
    return create_subscription_top_up_order_factory(
        unit_of_work_factory=lambda: uow
    ), uow


@pytest.mark.asyncio
async def test_order_price_and_bundle_are_derived_server_side() -> None:
    service, uow = _service()

    result = await service(_command())

    assert result.plan_code == "starter"
    assert result.requested_units == 10_000
    assert result.bundle_count == 1
    assert result.total_price_usd != "0"
    assert result.channel == "lemon_squeezy"
    assert result.committed is True
    order = uow.top_up_orders.added[0]
    assert order.customer_ref == "customer_001"
    assert order.quota_cycle_id == CYCLE_ID
    assert order.plan_catalog_version == PLAN_FULFILLMENT_CATALOG_VERSION
    assert order.account_id is None
    assert order.state == "awaiting_payment"


@pytest.mark.asyncio
async def test_order_rechecks_eighty_percent_threshold() -> None:
    service, _ = _service(cycle=_cycle(used_units=7_999))

    with pytest.raises(SubscriptionTopUpOrderError, match="at least 80%"):
        await service(_command())


@pytest.mark.asyncio
async def test_order_rejects_cross_customer_attempt() -> None:
    service, _ = _service()

    with pytest.raises(SubscriptionTopUpOrderError, match="customer conflicts"):
        await service(_command(customer_ref="customer_002"))


@pytest.mark.asyncio
async def test_order_rejects_invalid_bundle_without_accepting_client_price() -> None:
    service, _ = _service()

    with pytest.raises(SubscriptionTopUpOrderError, match="not purchasable"):
        await service(_command(requested_units=5_000))


@pytest.mark.asyncio
async def test_order_rejects_local_channel_until_local_wiring_exists() -> None:
    service, _ = _service()

    with pytest.raises(SubscriptionTopUpOrderError, match="Lemon Squeezy only"):
        await service(_command(channel=TopUpCheckoutChannel.LOCAL_TUNISIA))


@pytest.mark.asyncio
async def test_order_cannot_target_prior_month_cycle() -> None:
    service, _ = _service()

    with pytest.raises(SubscriptionTopUpOrderError, match="current monthly"):
        await service(_command(created_at=datetime(2026, 9, 2, tzinfo=UTC)))


@pytest.mark.asyncio
async def test_matching_idempotent_replay_returns_existing_without_commit() -> None:
    existing = SimpleNamespace(
        id=ORDER_ID,
        customer_ref="customer_001",
        subscription_id=SUBSCRIPTION_ID,
        quota_cycle_id=CYCLE_ID,
        plan_code="starter",
        plan_catalog_version=PLAN_FULFILLMENT_CATALOG_VERSION,
        requested_units=10_000,
        bundle_count=1,
        total_price_usd=1,
        channel="lemon_squeezy",
        idempotency_key="top-up-order-001",
    )
    service, uow = _service(existing=existing)

    result = await service(_command())

    assert result.idempotent_replay is True
    assert result.committed is False
    assert uow.commit_count == 0


@pytest.mark.asyncio
async def test_conflicting_idempotent_replay_fails_closed() -> None:
    existing = SimpleNamespace(
        id=ORDER_ID,
        customer_ref="customer_001",
        subscription_id=SUBSCRIPTION_ID,
        quota_cycle_id=CYCLE_ID,
        plan_code="starter",
        plan_catalog_version=PLAN_FULFILLMENT_CATALOG_VERSION,
        requested_units=20_000,
        bundle_count=2,
        total_price_usd=1,
        channel="lemon_squeezy",
        idempotency_key="top-up-order-001",
    )
    service, _ = _service(existing=existing)

    with pytest.raises(SubscriptionTopUpOrderError, match="replay conflicts"):
        await service(_command())
