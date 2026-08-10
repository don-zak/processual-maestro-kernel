from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from processual_api.billing.commercial_quota_top_up_contracts import (
    TopUpPurchaseState,
    quote_top_up_for_runtime,
)
from processual_api.billing.plan_fulfillment_catalog import (
    PLAN_FULFILLMENT_CATALOG_VERSION,
    QUOTA_METRIC_CODE,
    get_plan_fulfillment_spec,
)

TOP_UP_MINIMUM_MONTHLY_CONSUMPTION_PERCENT = 80
_ALLOWED_BILLING_PERIODS = frozenset({"monthly", "annual"})


class SubscriptionTopUpEligibilityError(RuntimeError):
    """A top-up purchase cannot be authorized safely."""


@dataclass(frozen=True, slots=True)
class SubscriptionTopUpEligibilityCommand:
    customer_ref: str
    subscription_id: uuid.UUID
    quota_cycle_id: uuid.UUID
    requested_units: int
    billing_period: str
    evaluated_at: datetime


@dataclass(frozen=True, slots=True)
class SubscriptionTopUpEligibilityDecision:
    eligible: bool
    reason: str
    customer_ref: str
    plan_code: str
    plan_catalog_version: str
    billing_period: str
    quota_cycle_id: uuid.UUID
    monthly_base_units: int
    monthly_used_units: int
    minimum_used_units: int
    consumption_percent_floor: int
    requested_units: int
    bundle_count: int
    total_units: int
    total_price_usd: str
    quote_state: str


def evaluate_subscription_top_up_eligibility_factory(
    *,
    unit_of_work_factory: Callable[[], object],
):
    async def evaluate(
        command: SubscriptionTopUpEligibilityCommand,
    ) -> SubscriptionTopUpEligibilityDecision:
        customer_ref, billing_period = _validate(command)
        async with unit_of_work_factory() as uow:
            subscription = await uow.subscriptions.get_by_id(
                command.subscription_id,
                for_update=True,
            )
            if subscription is None:
                raise SubscriptionTopUpEligibilityError("subscription was not found.")
            if subscription.status != "active":
                raise SubscriptionTopUpEligibilityError(
                    "top-up purchase requires an active subscription."
                )
            if subscription.customer_ref != customer_ref:
                raise SubscriptionTopUpEligibilityError(
                    "subscription does not belong to the purchasing customer."
                )

            plan = await uow.plans.get_by_id(subscription.plan_id, for_update=True)
            if plan is None:
                raise SubscriptionTopUpEligibilityError(
                    "subscription plan was not found."
                )
            try:
                spec = get_plan_fulfillment_spec(plan.plan_code)
            except KeyError as exc:
                raise SubscriptionTopUpEligibilityError(
                    "subscription plan is not in the authoritative fulfillment catalog."
                ) from exc

            cycle = await uow.subscription_quota_cycles.get_by_id(
                command.quota_cycle_id,
                for_update=True,
            )
            if cycle is None:
                raise SubscriptionTopUpEligibilityError("quota cycle was not found.")
            if (
                cycle.subscription_id != subscription.id
                or cycle.customer_ref != customer_ref
                or cycle.metric_code != QUOTA_METRIC_CODE
            ):
                raise SubscriptionTopUpEligibilityError(
                    "quota cycle conflicts with the subscription."
                )
            if not cycle.period_start <= command.evaluated_at < cycle.period_end:
                raise SubscriptionTopUpEligibilityError(
                    "top-up eligibility requires the current monthly quota cycle."
                )
            if (
                cycle.plan_code != spec.plan_code
                or cycle.plan_catalog_version != PLAN_FULFILLMENT_CATALOG_VERSION
                or cycle.base_limit_units != spec.monthly_unit_allowance
            ):
                raise SubscriptionTopUpEligibilityError(
                    "quota cycle conflicts with the authoritative plan snapshot."
                )

            minimum_used_units = _ceil_percent(
                cycle.base_limit_units,
                TOP_UP_MINIMUM_MONTHLY_CONSUMPTION_PERCENT,
            )
            if cycle.used_units < minimum_used_units:
                raise SubscriptionTopUpEligibilityError(
                    "top-up purchase requires at least 80% consumption of the monthly base quota."
                )

            quote = quote_top_up_for_runtime(spec.plan_code, command.requested_units)
            if quote.state not in {
                TopUpPurchaseState.READY_FOR_REVIEW,
                TopUpPurchaseState.UPGRADE_RECOMMENDED,
            }:
                raise SubscriptionTopUpEligibilityError(
                    f"top-up request is not purchasable: {quote.state.value}."
                )
            if quote.total_units <= 0 or quote.bundle_count <= 0:
                raise SubscriptionTopUpEligibilityError(
                    "top-up quote did not produce purchasable units."
                )

            return SubscriptionTopUpEligibilityDecision(
                eligible=True,
                reason="monthly base quota consumption threshold satisfied",
                customer_ref=customer_ref,
                plan_code=spec.plan_code,
                plan_catalog_version=PLAN_FULFILLMENT_CATALOG_VERSION,
                billing_period=billing_period,
                quota_cycle_id=cycle.id,
                monthly_base_units=cycle.base_limit_units,
                monthly_used_units=cycle.used_units,
                minimum_used_units=minimum_used_units,
                consumption_percent_floor=TOP_UP_MINIMUM_MONTHLY_CONSUMPTION_PERCENT,
                requested_units=command.requested_units,
                bundle_count=quote.bundle_count,
                total_units=quote.total_units,
                total_price_usd=str(quote.total_price_usd),
                quote_state=quote.state.value,
            )

    return evaluate


def _ceil_percent(value: int, percent: int) -> int:
    return (value * percent + 99) // 100


def _validate(command: SubscriptionTopUpEligibilityCommand) -> tuple[str, str]:
    customer_ref = command.customer_ref.strip()
    if not customer_ref:
        raise ValueError("customer_ref is required.")
    if command.requested_units <= 0:
        raise ValueError("requested_units must be positive.")
    billing_period = command.billing_period.strip().lower()
    if billing_period not in _ALLOWED_BILLING_PERIODS:
        raise ValueError("billing_period must be monthly or annual.")
    if command.evaluated_at.tzinfo is None:
        raise ValueError("top-up eligibility timestamp must be timezone-aware.")
    return customer_ref, billing_period


__all__ = [
    "TOP_UP_MINIMUM_MONTHLY_CONSUMPTION_PERCENT",
    "SubscriptionTopUpEligibilityCommand",
    "SubscriptionTopUpEligibilityDecision",
    "SubscriptionTopUpEligibilityError",
    "evaluate_subscription_top_up_eligibility_factory",
]
