from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from processual_api.admin_marketplace.subscription_top_up_reversal import (
    ReverseSubscriptionTopUpCommand,
    SubscriptionTopUpReversalError,
    reverse_subscription_top_up_factory,
)

NOW = datetime(2026, 8, 25, tzinfo=UTC)
ORDER_ID = uuid.uuid4()
GRANT_ID = uuid.uuid4()
SUBSCRIPTION_ID = uuid.uuid4()
CYCLE_ID = uuid.uuid4()


class ByIdRepo:
    def __init__(self, value: object | None) -> None:
        self.value = value

    async def get_by_id(self, value_id, *, for_update: bool = False):
        if self.value is None or self.value.id != value_id:
            return None
        return self.value


class GrantRepo:
    def __init__(self, grant: object | None) -> None:
        self.grant = grant

    async def get_by_order_id(self, order_id, *, for_update: bool = False):
        if self.grant is None or self.grant.order_id != order_id:
            return None
        return self.grant


class ReversalRepo:
    def __init__(self) -> None:
        self.reversal = None

    async def get_by_provider_event_ref(self, provider_event_ref: str, *, for_update: bool = False):
        if self.reversal is None or self.reversal.provider_event_ref != provider_event_ref:
            return None
        return self.reversal

    async def get_by_grant_id(self, grant_id, *, for_update: bool = False):
        if self.reversal is None or self.reversal.grant_id != grant_id:
            return None
        return self.reversal

    def add(self, reversal: object) -> None:
        self.reversal = reversal


class FakeUow:
    def __init__(self, *, used_units: int = 8_000) -> None:
        self.order = SimpleNamespace(
            id=ORDER_ID,
            subscription_id=SUBSCRIPTION_ID,
            quota_cycle_id=CYCLE_ID,
            customer_ref="customer_001",
            state="granted",
        )
        self.grant = SimpleNamespace(
            id=GRANT_ID,
            order_id=ORDER_ID,
            subscription_id=SUBSCRIPTION_ID,
            quota_cycle_id=CYCLE_ID,
            customer_ref="customer_001",
            units=10_000,
        )
        self.cycle = SimpleNamespace(
            id=CYCLE_ID,
            subscription_id=SUBSCRIPTION_ID,
            customer_ref="customer_001",
            base_limit_units=10_000,
            spendable_rollover_units=0,
            top_up_units=10_000,
            used_units=used_units,
            version=1,
        )
        self.top_up_orders = ByIdRepo(self.order)
        self.subscription_top_up_grants = GrantRepo(self.grant)
        self.subscription_quota_cycles = ByIdRepo(self.cycle)
        self.subscription_top_up_reversals = ReversalRepo()
        self.commit_count = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

    async def commit(self) -> None:
        self.commit_count += 1


def _command(*, event_ref: str = "lemon:refund:7001") -> ReverseSubscriptionTopUpCommand:
    return ReverseSubscriptionTopUpCommand(
        order_id=ORDER_ID,
        provider_event_ref=event_ref,
        reason_code="provider_refund",
        reversed_at=NOW,
    )


@pytest.mark.asyncio
async def test_refund_reverses_unconsumed_top_up_balance_once() -> None:
    uow = FakeUow(used_units=8_000)
    reverse = reverse_subscription_top_up_factory(unit_of_work_factory=lambda: uow)

    result = await reverse(_command())

    assert result.outcome == "reversed"
    assert result.units == 10_000
    assert uow.cycle.top_up_units == 0
    assert uow.cycle.version == 2
    assert uow.subscription_top_up_reversals.reversal.outcome == "reversed"
    assert uow.commit_count == 1


@pytest.mark.asyncio
async def test_refund_becomes_manual_review_when_units_were_already_consumed() -> None:
    uow = FakeUow(used_units=15_000)
    reverse = reverse_subscription_top_up_factory(unit_of_work_factory=lambda: uow)

    result = await reverse(_command())

    assert result.outcome == "manual_review"
    assert uow.cycle.top_up_units == 10_000
    assert uow.cycle.version == 1
    assert uow.subscription_top_up_reversals.reversal.reason_code == "units_already_consumed"
    assert uow.commit_count == 1


@pytest.mark.asyncio
async def test_same_provider_refund_event_is_idempotent() -> None:
    uow = FakeUow(used_units=8_000)
    reverse = reverse_subscription_top_up_factory(unit_of_work_factory=lambda: uow)

    first = await reverse(_command())
    second = await reverse(_command())

    assert first.reversal_id == second.reversal_id
    assert second.idempotent_replay is True
    assert uow.cycle.top_up_units == 0
    assert uow.commit_count == 1


@pytest.mark.asyncio
async def test_second_distinct_reversal_event_for_same_grant_fails_closed() -> None:
    uow = FakeUow(used_units=8_000)
    reverse = reverse_subscription_top_up_factory(unit_of_work_factory=lambda: uow)

    await reverse(_command(event_ref="lemon:refund:7001"))

    with pytest.raises(SubscriptionTopUpReversalError, match="already has a reversal decision"):
        await reverse(_command(event_ref="lemon:refund:7002"))

    assert uow.cycle.top_up_units == 0
    assert uow.commit_count == 1
