from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from processual_api.admin_marketplace.subscription_quota_rollover_persistence import (
    AdminMarketSubscriptionQuotaCycle,
)
from processual_api.billing.plan_fulfillment_catalog import (
    PLAN_FULFILLMENT_CATALOG_VERSION,
    QUOTA_METRIC_CODE,
    get_plan_fulfillment_spec,
)


class SubscriptionQuotaRolloverError(RuntimeError):
    """Quota rollover cannot be completed safely."""


@dataclass(frozen=True, slots=True)
class SubscriptionQuotaRolloverCommand:
    subscription_id: uuid.UUID
    source_cycle_id: uuid.UUID
    metric_code: str
    period_start: datetime
    period_end: datetime
    base_limit_units: int


def rollover_subscription_quota_factory(*, unit_of_work_factory: Callable[[], object]):
    async def rollover(
        command: SubscriptionQuotaRolloverCommand,
    ) -> AdminMarketSubscriptionQuotaCycle:
        _validate(command)
        async with unit_of_work_factory() as uow:
            subscription = await uow.subscriptions.get_by_id(
                command.subscription_id,
                for_update=True,
            )
            if subscription is None:
                raise SubscriptionQuotaRolloverError("subscription was not found.")
            if subscription.status != "active":
                raise SubscriptionQuotaRolloverError(
                    "quota rollover requires an active subscription."
                )

            plan = await uow.plans.get_by_id(subscription.plan_id, for_update=True)
            if plan is None:
                raise SubscriptionQuotaRolloverError(
                    "subscription plan was not found."
                )
            try:
                plan_spec = get_plan_fulfillment_spec(plan.plan_code)
            except KeyError as exc:
                raise SubscriptionQuotaRolloverError(
                    "subscription plan is not in the authoritative catalog."
                ) from exc
            if plan_spec.seat_based_consumption:
                raise SubscriptionQuotaRolloverError(
                    "quota consumption cannot be seat based."
                )
            if command.metric_code.strip().lower() != QUOTA_METRIC_CODE:
                raise SubscriptionQuotaRolloverError(
                    "quota metric conflicts with the authoritative plan."
                )
            if command.base_limit_units != plan_spec.monthly_unit_allowance:
                raise SubscriptionQuotaRolloverError(
                    "quota base limit conflicts with the authoritative plan."
                )

            existing = await uow.subscription_quota_cycles.get_by_source_cycle_id(
                command.source_cycle_id,
                for_update=True,
            )
            if existing is not None:
                _assert_replay_matches(command, existing, plan_spec.plan_code)
                return existing

            source = await uow.subscription_quota_cycles.get_by_id(
                command.source_cycle_id,
                for_update=True,
            )
            if source is None:
                raise SubscriptionQuotaRolloverError("source quota cycle was not found.")
            if (
                source.subscription_id != command.subscription_id
                or source.metric_code != QUOTA_METRIC_CODE
                or source.customer_ref != subscription.customer_ref
                or source.plan_code != plan_spec.plan_code
                or source.plan_catalog_version != PLAN_FULFILLMENT_CATALOG_VERSION
            ):
                raise SubscriptionQuotaRolloverError(
                    "source quota cycle conflicts with the authoritative subscription plan."
                )
            if source.period_end != command.period_start:
                raise SubscriptionQuotaRolloverError("quota periods are not contiguous.")

            cycle = AdminMarketSubscriptionQuotaCycle(
                subscription_id=subscription.id,
                source_cycle_id=source.id,
                customer_ref=subscription.customer_ref,
                plan_code=plan_spec.plan_code,
                plan_catalog_version=PLAN_FULFILLMENT_CATALOG_VERSION,
                entitlement_codes=list(plan_spec.entitlement_codes),
                quota_profile_ref=plan.quota_profile_ref,
                metric_code=QUOTA_METRIC_CODE,
                period_start=command.period_start,
                period_end=command.period_end,
                base_limit_units=plan_spec.monthly_unit_allowance,
                rollover_units=source.available_units,
                rollover_status="available",
                used_units=0,
            )
            uow.subscription_quota_cycles.add(cycle)
            await uow.commit()
            return cycle

    return rollover


def _validate(command: SubscriptionQuotaRolloverCommand) -> None:
    if not command.metric_code.strip():
        raise ValueError("quota metric code is required.")
    if command.period_start.tzinfo is None or command.period_end.tzinfo is None:
        raise ValueError("quota rollover timestamps must be timezone-aware.")
    if command.period_end <= command.period_start:
        raise ValueError("quota rollover period is invalid.")
    if command.base_limit_units < 0:
        raise ValueError("quota base limit cannot be negative.")


def _assert_replay_matches(
    command: SubscriptionQuotaRolloverCommand,
    existing: AdminMarketSubscriptionQuotaCycle,
    plan_code: str,
) -> None:
    if (
        existing.subscription_id != command.subscription_id
        or existing.source_cycle_id != command.source_cycle_id
        or existing.metric_code != QUOTA_METRIC_CODE
        or existing.plan_code != plan_code
        or existing.plan_catalog_version != PLAN_FULFILLMENT_CATALOG_VERSION
        or existing.period_start != command.period_start
        or existing.period_end != command.period_end
        or existing.base_limit_units != command.base_limit_units
    ):
        raise SubscriptionQuotaRolloverError(
            "quota rollover replay conflicts with the existing cycle."
        )


__all__ = [
    "SubscriptionQuotaRolloverCommand",
    "SubscriptionQuotaRolloverError",
    "rollover_subscription_quota_factory",
]
