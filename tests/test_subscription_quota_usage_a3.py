from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from processual_api.admin_marketplace.subscription_quota_usage import (
    SubscriptionQuotaUsageCommand,
    SubscriptionQuotaUsageError,
    record_subscription_quota_usage_factory,
)

NOW = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)
SUBSCRIPTION_ID = uuid.uuid4()
CYCLE_ID = uuid.uuid4()


class SingleRepository:
    def __init__(self, value: object | None) -> None:
        self.value = value

    async def get_by_id(self, value_id: uuid.UUID, *, for_update: bool = False):
        if self.value is None or self.value.id != value_id:
            return None
        return self.value


class RuntimeRepository:
    def __init__(self, value: object | None) -> None:
        self.value = value

    async def get_by_subscription_id(
        self,
        subscription_id: uuid.UUID,
        *,
        for_update: bool = False,
    ):
        if self.value is None or self.value.subscription_id != subscription_id:
            return None
        return self.value


class UsageRepository:
    def __init__(self, existing: object | None = None) -> None:
        self.existing = existing
        self.added: list[object] = []

    async def get_by_idempotency_hash(
        self,
        value: str,
        *,
        for_update: bool = False,
    ):
        if self.existing is None:
            return None
        if self.existing.idempotency_key_hash != value:
            return None
        return self.existing

    def add(self, value: object) -> None:
        self.added.append(value)


class FakeUnitOfWork:
    def __init__(
        self,
        *,
        subscription: object | None = None,
        runtime: object | None = None,
        cycle: object | None = None,
        existing: object | None = None,
    ) -> None:
        self.subscriptions = SingleRepository(subscription or _subscription())
        self.subscription_runtime = RuntimeRepository(runtime or _runtime())
        self.subscription_quota_cycles = SingleRepository(cycle or _cycle())
        self.subscription_quota_cycle_usage = UsageRepository(existing)
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True


def _subscription(**overrides: object) -> SimpleNamespace:
    values = {
        "id": SUBSCRIPTION_ID,
        "customer_ref": "customer_001",
        "status": "active",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _runtime(**overrides: object) -> SimpleNamespace:
    values = {
        "subscription_id": SUBSCRIPTION_ID,
        "customer_ref": "customer_001",
        "access_stage": "active",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _cycle(**overrides: object) -> SimpleNamespace:
    values = {
        "id": CYCLE_ID,
        "subscription_id": SUBSCRIPTION_ID,
        "customer_ref": "customer_001",
        "metric_code": "credits",
        "period_start": NOW - timedelta(days=5),
        "period_end": NOW + timedelta(days=25),
        "base_limit_units": 100,
        "rollover_units": 30,
        "used_units": 20,
        "version": 0,
    }
    values.update(overrides)
    cycle = SimpleNamespace(**values)
    cycle.__class__.available_units = property(
        lambda self: self.base_limit_units + self.rollover_units - self.used_units
    )
    return cycle


def _command(**overrides: object) -> SubscriptionQuotaUsageCommand:
    values = {
        "subscription_id": SUBSCRIPTION_ID,
        "quota_cycle_id": CYCLE_ID,
        "customer_ref": "customer_001",
        "metric_code": "credits",
        "units": 25,
        "idempotency_key_hash": "a" * 64,
        "dimensions_digest": "b" * 64,
        "occurred_at": NOW,
    }
    values.update(overrides)
    return SubscriptionQuotaUsageCommand(**values)


@pytest.mark.asyncio
async def test_active_runtime_consumes_base_and_rollover_balance() -> None:
    cycle = _cycle()
    uow = FakeUnitOfWork(cycle=cycle)
    record = record_subscription_quota_usage_factory(
        unit_of_work_factory=lambda: uow
    )

    usage = await record(_command())

    assert cycle.used_units == 45
    assert cycle.version == 1
    assert usage.units == 25
    assert usage.quota_cycle_id == CYCLE_ID
    assert uow.subscription_quota_cycle_usage.added == [usage]
    assert uow.committed is True


@pytest.mark.asyncio
async def test_suspended_runtime_cannot_consume_quota() -> None:
    cycle = _cycle()
    uow = FakeUnitOfWork(runtime=_runtime(access_stage="suspended"), cycle=cycle)
    record = record_subscription_quota_usage_factory(
        unit_of_work_factory=lambda: uow
    )

    with pytest.raises(SubscriptionQuotaUsageError, match="active runtime"):
        await record(_command())

    assert cycle.used_units == 20
    assert uow.committed is False


@pytest.mark.asyncio
async def test_usage_cannot_exceed_available_units() -> None:
    cycle = _cycle()
    uow = FakeUnitOfWork(cycle=cycle)
    record = record_subscription_quota_usage_factory(
        unit_of_work_factory=lambda: uow
    )

    with pytest.raises(SubscriptionQuotaUsageError, match="insufficient"):
        await record(_command(units=111))

    assert cycle.used_units == 20
    assert uow.committed is False


@pytest.mark.asyncio
async def test_matching_replay_returns_existing_without_commit() -> None:
    command = _command()
    existing = SimpleNamespace(
        quota_cycle_id=command.quota_cycle_id,
        subscription_id=command.subscription_id,
        customer_ref=command.customer_ref,
        metric_code=command.metric_code,
        units=command.units,
        idempotency_key_hash=command.idempotency_key_hash,
        dimensions_digest=command.dimensions_digest,
        occurred_at=command.occurred_at,
    )
    uow = FakeUnitOfWork(existing=existing)
    record = record_subscription_quota_usage_factory(
        unit_of_work_factory=lambda: uow
    )

    result = await record(command)

    assert result is existing
    assert uow.committed is False


@pytest.mark.asyncio
async def test_conflicting_replay_fails_closed() -> None:
    command = _command()
    existing = SimpleNamespace(
        quota_cycle_id=command.quota_cycle_id,
        subscription_id=command.subscription_id,
        customer_ref=command.customer_ref,
        metric_code=command.metric_code,
        units=1,
        idempotency_key_hash=command.idempotency_key_hash,
        dimensions_digest=command.dimensions_digest,
        occurred_at=command.occurred_at,
    )
    uow = FakeUnitOfWork(existing=existing)
    record = record_subscription_quota_usage_factory(
        unit_of_work_factory=lambda: uow
    )

    with pytest.raises(SubscriptionQuotaUsageError, match="replay conflicts"):
        await record(command)

    assert uow.committed is False
