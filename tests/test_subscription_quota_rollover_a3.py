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

START = datetime(2026, 8, 1, tzinfo=UTC)
NEXT = datetime(2026, 9, 1, tzinfo=UTC)
END = datetime(2026, 10, 1, tzinfo=UTC)
SUBSCRIPTION_ID = uuid.uuid4()
SOURCE_ID = uuid.uuid4()


class SubscriptionRepo:
    def __init__(self, subscription: object | None) -> None:
        self.subscription = subscription

    async def get_by_id(self, value: uuid.UUID, *, for_update: bool = False):
        if self.subscription is None or self.subscription.id != value:
            return None
        return self.subscription


class CycleRepo:
    def __init__(self, source: object | None, existing: object | None = None) -> None:
        self.source = source
        self.existing = existing
        self.added: list[object] = []

    async def get_by_source_cycle_id(self, value: uuid.UUID, *, for_update: bool = False):
        return self.existing if self.existing and self.existing.source_cycle_id == value else None

    async def get_by_id(self, value: uuid.UUID, *, for_update: bool = False):
        return self.source if self.source and self.source.id == value else None

    def add(self, cycle: object) -> None:
        self.added.append(cycle)


class FakeUow:
    def __init__(self, subscription: object | None, source: object | None, existing: object | None = None) -> None:
        self.subscriptions = SubscriptionRepo(subscription)
        self.subscription_quota_cycles = CycleRepo(source, existing)
        self.commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1


def _subscription(status: str = "active") -> SimpleNamespace:
    return SimpleNamespace(id=SUBSCRIPTION_ID, customer_ref="customer_001", status=status)


def _source(**overrides: object) -> SimpleNamespace:
    values = {
        "id": SOURCE_ID,
        "subscription_id": SUBSCRIPTION_ID,
        "customer_ref": "customer_001",
        "quota_profile_ref": "quota_pro",
        "metric_code": "credits",
        "period_start": START,
        "period_end": NEXT,
        "base_limit_units": 100,
        "rollover_units": 20,
        "used_units": 70,
        "available_units": 50,
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
        "base_limit_units": 100,
    }
    values.update(overrides)
    return SubscriptionQuotaRolloverCommand(**values)


@pytest.mark.asyncio
async def test_active_subscription_rolls_remaining_units_into_next_cycle() -> None:
    uow = FakeUow(_subscription(), _source())
    rollover = rollover_subscription_quota_factory(unit_of_work_factory=lambda: uow)

    cycle = await rollover(_command())

    assert cycle.base_limit_units == 100
    assert cycle.rollover_units == 50
    assert cycle.available_units == 150
    assert cycle.source_cycle_id == SOURCE_ID
    assert uow.commits == 1


@pytest.mark.asyncio
async def test_inactive_subscription_cannot_roll_quota() -> None:
    uow = FakeUow(_subscription("suspended"), _source())
    rollover = rollover_subscription_quota_factory(unit_of_work_factory=lambda: uow)

    with pytest.raises(SubscriptionQuotaRolloverError, match="active subscription"):
        await rollover(_command())

    assert uow.commits == 0


@pytest.mark.asyncio
async def test_replay_returns_existing_cycle_without_commit() -> None:
    existing = SimpleNamespace(
        subscription_id=SUBSCRIPTION_ID,
        source_cycle_id=SOURCE_ID,
        metric_code="credits",
        period_start=NEXT,
        period_end=END,
        base_limit_units=100,
    )
    uow = FakeUow(_subscription(), _source(), existing)
    rollover = rollover_subscription_quota_factory(unit_of_work_factory=lambda: uow)

    assert await rollover(_command()) is existing
    assert uow.commits == 0


@pytest.mark.asyncio
async def test_conflicting_replay_fails_closed() -> None:
    existing = SimpleNamespace(
        subscription_id=SUBSCRIPTION_ID,
        source_cycle_id=SOURCE_ID,
        metric_code="credits",
        period_start=NEXT,
        period_end=END,
        base_limit_units=200,
    )
    uow = FakeUow(_subscription(), _source(), existing)
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
