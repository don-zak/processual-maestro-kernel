from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from processual_api.admin_marketplace.subscription_top_up_eligibility import (
    SubscriptionTopUpEligibilityCommand,
    SubscriptionTopUpEligibilityError,
    evaluate_subscription_top_up_eligibility_factory,
)
from processual_api.billing.plan_fulfillment_catalog import (
    PLAN_FULFILLMENT_CATALOG_VERSION,
)

START = datetime(2026, 8, 1, tzinfo=UTC)
END = datetime(2026, 9, 1, tzinfo=UTC)
NOW = datetime(2026, 8, 20, tzinfo=UTC)
SUBSCRIPTION_ID = uuid.uuid4()
PLAN_ID = uuid.uuid4()
CYCLE_ID = uuid.uuid4()


class Repository:
    def __init__(self, value: object | None) -> None:
        self.value = value

    async def get_by_id(self, value: uuid.UUID, *, for_update: bool = False):
        if self.value is None or self.value.id != value:
            return None
        return self.value


class FakeUow:
    def __init__(self, *, subscription: object, plan: object, cycle: object) -> None:
        self.subscriptions = Repository(subscription)
        self.plans = Repository(plan)
        self.subscription_quota_cycles = Repository(cycle)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None


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
        "rollover_units": 5_000,
        "used_units": 8_000,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _command(**overrides: object) -> SubscriptionTopUpEligibilityCommand:
    values = {
        "customer_ref": "customer_001",
        "subscription_id": SUBSCRIPTION_ID,
        "quota_cycle_id": CYCLE_ID,
        "requested_units": 10_000,
        "billing_period": "monthly",
        "evaluated_at": NOW,
    }
    values.update(overrides)
    return SubscriptionTopUpEligibilityCommand(**values)


def _evaluate(*, subscription: object | None = None, plan: object | None = None, cycle: object | None = None):
    uow = FakeUow(
        subscription=subscription or _subscription(),
        plan=plan or _plan(),
        cycle=cycle or _cycle(),
    )
    return evaluate_subscription_top_up_eligibility_factory(
        unit_of_work_factory=lambda: uow
    )


@pytest.mark.asyncio
async def test_exactly_eighty_percent_of_monthly_base_is_eligible() -> None:
    decision = await _evaluate()(_command())

    assert decision.eligible is True
    assert decision.monthly_base_units == 10_000
    assert decision.monthly_used_units == 8_000
    assert decision.minimum_used_units == 8_000
    assert decision.total_units == 10_000


@pytest.mark.asyncio
async def test_below_eighty_percent_is_rejected() -> None:
    evaluate = _evaluate(cycle=_cycle(used_units=7_999))

    with pytest.raises(SubscriptionTopUpEligibilityError, match="at least 80%"):
        await evaluate(_command())


@pytest.mark.asyncio
async def test_rollover_does_not_reduce_monthly_consumption_threshold() -> None:
    evaluate = _evaluate(cycle=_cycle(rollover_units=100_000, used_units=7_999))

    with pytest.raises(SubscriptionTopUpEligibilityError, match="monthly base quota"):
        await evaluate(_command())


@pytest.mark.asyncio
async def test_customer_cannot_buy_for_another_customer_subscription() -> None:
    evaluate = _evaluate()

    with pytest.raises(SubscriptionTopUpEligibilityError, match="purchasing customer"):
        await evaluate(_command(customer_ref="customer_002"))


@pytest.mark.asyncio
async def test_annual_contract_uses_current_monthly_cycle_not_yearly_pool() -> None:
    decision = await _evaluate()(_command(billing_period="annual"))

    assert decision.billing_period == "annual"
    assert decision.monthly_base_units == 10_000
    assert decision.minimum_used_units == 8_000


@pytest.mark.asyncio
async def test_annual_contract_cannot_use_prior_month_consumption() -> None:
    evaluate = _evaluate(cycle=_cycle(period_start=START, period_end=END))

    with pytest.raises(SubscriptionTopUpEligibilityError, match="current monthly"):
        await evaluate(
            _command(
                billing_period="annual",
                evaluated_at=datetime(2026, 9, 2, tzinfo=UTC),
            )
        )


@pytest.mark.asyncio
async def test_plan_snapshot_must_match_authoritative_catalog() -> None:
    evaluate = _evaluate(cycle=_cycle(base_limit_units=9_999))

    with pytest.raises(SubscriptionTopUpEligibilityError, match="authoritative plan"):
        await evaluate(_command())


@pytest.mark.asyncio
async def test_invalid_bundle_request_is_rejected() -> None:
    evaluate = _evaluate()

    with pytest.raises(SubscriptionTopUpEligibilityError, match="not purchasable"):
        await evaluate(_command(requested_units=5_000))
