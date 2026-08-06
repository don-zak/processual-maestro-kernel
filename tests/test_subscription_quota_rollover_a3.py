from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from processual_api.admin_marketplace.subscription_quota_rollover import (
    SubscriptionQuotaRolloverCommand,
    SubscriptionQuotaRolloverError,
    rollover_subscription_quota_factory,
)
from processual_api.billing.plan_fulfillment_catalog import (
    PLAN_FULFILLMENT_CATALOG_VERSION,
    PLAN_FULFILLMENT_SPECS,
    get_plan_fulfillment_spec,
    monthly_unit_allowance,
)

START = datetime(2026, 8, 1, tzinfo=UTC)
NEXT = datetime(2026, 9, 1, tzinfo=UTC)
END = datetime(2026, 10, 1, tzinfo=UTC)
SUBSCRIPTION_ID = uuid.uuid4()
SOURCE_ID = uuid.uuid4()
PLAN_ID = uuid.uuid4()


class SingleRepo:
    def __init__(self, value: object | None) -> None:
        self.value = value

    async def get_by_id(self, value_id: uuid.UUID, *, for_update: bool = False):
        if self.value is None or self.value.id != value_id:
            return None
        return self.value


class CycleRepo:
    def __init__(self, source: object | None, existing: object | None = None) -> None:
        self.source = source
        self.existing = existing
        self.added: list[object] = []

    async def get_by_source_cycle_id(
        self,
        value: uuid.UUID,
        *,
        for_update: bool = False,
    ):
        if self.existing and self.existing.source_cycle_id == value:
            return self.existing
        return None

    async def get_by_id(self, value: uuid.UUID, *, for_update: bool = False):
        if self.source and self.source.id == value:
            return self.source
        return None

    def add(self, cycle: object) -> None:
        self.added.append(cycle)


class FakeUow:
    def __init__(
        self,
        subscription: object | None,
        source: object | None,
        *,
        plan: object | None = None,
        existing: object | None = None,
    ) -> None:
        self.subscriptions = SingleRepo(subscription)
        self.plans = SingleRepo(plan or _plan())
        self.subscription_quota_cycles = CycleRepo(source, existing)
        self.commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1


def _plan(plan_code: str = "starter") -> SimpleNamespace:
    return SimpleNamespace(
        id=PLAN_ID,
        plan_code=plan_code,
        quota_profile_ref=f"quota.{plan_code}.v1",
        entitlement_profile_ref=f"entitlement.{plan_code}.v1",
    )


def _subscription(status: str = "active") -> SimpleNamespace:
    return SimpleNamespace(
        id=SUBSCRIPTION_ID,
        customer_ref="customer_001",
        status=status,
        plan_id=PLAN_ID,
    )


def _source(**overrides: object) -> SimpleNamespace:
    spec = get_plan_fulfillment_spec("starter")
    values = {
        "id": SOURCE_ID,
        "subscription_id": SUBSCRIPTION_ID,
        "customer_ref": "customer_001",
        "plan_code": spec.plan_code,
        "plan_catalog_version": PLAN_FULFILLMENT_CATALOG_VERSION,
        "entitlement_codes": list(spec.entitlement_codes),
        "quota_profile_ref": "quota.starter.v1",
        "metric_code": "credits",
        "period_start": START,
        "period_end": NEXT,
        "base_limit_units": spec.monthly_unit_allowance,
        "rollover_units": 2_000,
        "used_units": 7_000,
        "available_units": 5_000,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _command(**overrides: object) -> SubscriptionQuotaRolloverCommand:
    values = {
        "subscription_id": SUBSCRIPTION_ID,
        "source_cycle_id": SOURCE_ID,
        "metric_code": "credits",
        "period_start": NEXT,
        "period_end": END,
        "base_limit_units": 10_000,
    }
    values.update(overrides)
    return SubscriptionQuotaRolloverCommand(**values)


@pytest.mark.asyncio
async def test_active_subscription_rolls_authoritative_plan_quota() -> None:
    uow = FakeUow(_subscription(), _source())
    rollover = rollover_subscription_quota_factory(unit_of_work_factory=lambda: uow)

    cycle = await rollover(_command())

    assert cycle.plan_code == "starter"
    assert cycle.plan_catalog_version == PLAN_FULFILLMENT_CATALOG_VERSION
    assert cycle.base_limit_units == 10_000
    assert cycle.rollover_units == 5_000
    assert cycle.available_units == 15_000
    assert cycle.entitlement_codes == list(
        PLAN_FULFILLMENT_SPECS["starter"].entitlement_codes
    )
    assert uow.commits == 1


@pytest.mark.asyncio
async def test_base_limit_must_match_authoritative_plan() -> None:
    uow = FakeUow(_subscription(), _source())
    rollover = rollover_subscription_quota_factory(unit_of_work_factory=lambda: uow)

    with pytest.raises(SubscriptionQuotaRolloverError, match="base limit conflicts"):
        await rollover(_command(base_limit_units=100_000))

    assert uow.commits == 0


@pytest.mark.asyncio
async def test_metric_must_match_authoritative_plan() -> None:
    uow = FakeUow(_subscription(), _source())
    rollover = rollover_subscription_quota_factory(unit_of_work_factory=lambda: uow)

    with pytest.raises(SubscriptionQuotaRolloverError, match="metric conflicts"):
        await rollover(_command(metric_code="seats"))


@pytest.mark.asyncio
async def test_consumption_is_quota_based_not_seat_based() -> None:
    starter = get_plan_fulfillment_spec("starter")
    business = get_plan_fulfillment_spec("business")

    assert starter.seat_based_consumption is False
    assert business.seat_based_consumption is False
    assert monthly_unit_allowance("starter") == 10_000
    assert monthly_unit_allowance("business") == 100_000


@pytest.mark.parametrize(
    ("plan_code", "expected_units"),
    [
        ("academic", 5_000),
        ("starter", 10_000),
        ("enterprise_integration_starter", 50_000),
        ("business", 100_000),
        ("enterprise_pilot", 500_000),
        ("enterprise_core", 1_500_000),
        ("enterprise_scale", 3_000_000),
        ("enterprise_strategic", 5_000_000),
    ],
)
def test_authoritative_catalog_contains_expected_quota(
    plan_code: str,
    expected_units: int,
) -> None:
    spec = get_plan_fulfillment_spec(plan_code)

    assert spec.monthly_unit_allowance == expected_units
    assert spec.entitlement_codes
    assert spec.seat_based_consumption is False


@pytest.mark.asyncio
async def test_inactive_subscription_cannot_roll_quota() -> None:
    uow = FakeUow(_subscription("suspended"), _source())
    rollover = rollover_subscription_quota_factory(unit_of_work_factory=lambda: uow)

    with pytest.raises(SubscriptionQuotaRolloverError, match="active subscription"):
        await rollover(_command())


@pytest.mark.asyncio
async def test_replay_returns_existing_cycle_without_commit() -> None:
    existing = SimpleNamespace(
        subscription_id=SUBSCRIPTION_ID,
        source_cycle_id=SOURCE_ID,
        metric_code="credits",
        plan_code="starter",
        plan_catalog_version=PLAN_FULFILLMENT_CATALOG_VERSION,
        period_start=NEXT,
        period_end=END,
        base_limit_units=10_000,
    )
    uow = FakeUow(_subscription(), _source(), existing=existing)
    rollover = rollover_subscription_quota_factory(unit_of_work_factory=lambda: uow)

    assert await rollover(_command()) is existing
    assert uow.commits == 0


@pytest.mark.asyncio
async def test_conflicting_replay_fails_closed() -> None:
    existing = SimpleNamespace(
        subscription_id=SUBSCRIPTION_ID,
        source_cycle_id=SOURCE_ID,
        metric_code="credits",
        plan_code="starter",
        plan_catalog_version=PLAN_FULFILLMENT_CATALOG_VERSION,
        period_start=NEXT,
        period_end=END,
        base_limit_units=100_000,
    )
    uow = FakeUow(_subscription(), _source(), existing=existing)
    rollover = rollover_subscription_quota_factory(unit_of_work_factory=lambda: uow)

    with pytest.raises(SubscriptionQuotaRolloverError, match="replay conflicts"):
        await rollover(_command())


@pytest.mark.asyncio
async def test_noncontiguous_period_is_rejected() -> None:
    source = _source(period_end=NEXT - timedelta(seconds=1))
    uow = FakeUow(_subscription(), source)
    rollover = rollover_subscription_quota_factory(unit_of_work_factory=lambda: uow)

    with pytest.raises(SubscriptionQuotaRolloverError, match="not contiguous"):
        await rollover(_command())
