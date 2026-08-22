from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from processual_api.admin_marketplace.subscription_quota_usage import (
    SubscriptionQuotaUsageCommand,
    record_subscription_quota_usage_factory,
)


NOW = datetime(2026, 8, 22, 10, 0, tzinfo=UTC)
SUBSCRIPTION_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
CYCLE_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")


class _SubscriptionRepo:
    async def get_by_id(self, value, *, for_update=False):
        assert value == SUBSCRIPTION_ID
        assert for_update is True
        return SimpleNamespace(
            id=SUBSCRIPTION_ID,
            customer_ref="customer-1",
            status="active",
        )


class _RuntimeRepo:
    async def get_by_subscription_id(self, value, *, for_update=False):
        assert value == SUBSCRIPTION_ID
        assert for_update is True
        return SimpleNamespace(
            subscription_id=SUBSCRIPTION_ID,
            customer_ref="customer-1",
            access_stage="active",
            effective_at=NOW - timedelta(days=1),
            grace_until=None,
            suspended_at=None,
            terminated_at=None,
            version=0,
        )


class _CycleRepo:
    def __init__(self) -> None:
        self.current_calls = []
        self.by_id_calls = []
        self.cycle = SimpleNamespace(
            id=CYCLE_ID,
            subscription_id=SUBSCRIPTION_ID,
            customer_ref="customer-1",
            metric_code="maestro_units",
            period_start=NOW - timedelta(days=2),
            period_end=NOW + timedelta(days=28),
            base_limit_units=100,
            rollover_units=10,
            top_up_units=5,
            rollover_status="available",
            used_units=20,
            version=3,
            available_units=95,
        )

    async def get_current(self, **kwargs):
        self.current_calls.append(kwargs)
        assert kwargs["subscription_id"] == SUBSCRIPTION_ID
        assert kwargs["metric_code"] == "maestro_units"
        assert kwargs["occurred_at"] == NOW
        assert kwargs["for_update"] is True
        return self.cycle

    async def get_by_id(self, value, *, for_update=False):
        self.by_id_calls.append((value, for_update))
        raise AssertionError("client-selected quota cycle must not be used")


class _UsageRepo:
    def __init__(self) -> None:
        self.added = []

    async def get_by_idempotency_hash(self, value, *, for_update=False):
        assert value == "a" * 64
        assert for_update is True
        return None

    def add(self, value) -> None:
        self.added.append(value)


class _Uow:
    def __init__(self) -> None:
        self.subscriptions = _SubscriptionRepo()
        self.subscription_runtime = _RuntimeRepo()
        self.subscription_quota_cycles = _CycleRepo()
        self.subscription_quota_cycle_usage = _UsageRepo()
        self.subscription_delinquency = SimpleNamespace()
        self.commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    async def commit(self):
        self.commits += 1


@pytest.mark.asyncio
async def test_current_cycle_is_selected_server_side_and_credits_alias_is_canonicalized() -> None:
    uow = _Uow()
    record = record_subscription_quota_usage_factory(
        unit_of_work_factory=lambda: uow
    )

    usage = await record(
        SubscriptionQuotaUsageCommand(
            subscription_id=SUBSCRIPTION_ID,
            customer_ref="customer-1",
            metric_code="credits",
            units=7,
            idempotency_key_hash="a" * 64,
            dimensions_digest="b" * 64,
            occurred_at=NOW,
            quota_cycle_id=None,
        )
    )

    assert len(uow.subscription_quota_cycles.current_calls) == 1
    assert uow.subscription_quota_cycles.by_id_calls == []
    assert uow.subscription_quota_cycles.cycle.used_units == 27
    assert uow.subscription_quota_cycles.cycle.version == 4
    assert usage.quota_cycle_id == CYCLE_ID
    assert usage.metric_code == "maestro_units"
    assert usage.units == 7
    assert uow.subscription_quota_cycle_usage.added == [usage]
    assert uow.commits == 1
