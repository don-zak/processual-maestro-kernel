from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from processual_api.admin_marketplace.subscription_quota_rollover_persistence import (
    AdminMarketSubscriptionQuotaCycle,
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

            existing = await uow.subscription_quota_cycles.get_by_source_cycle_id(
                command.source_cycle_id,
                for_update=True,
            )
            if existing is not None:
                _assert_replay_matches(command, existing)
                return existing

            source = await uow.subscription_quota_cycles.get_by_id(
                command.source_cycle_id,
                for_update=True,
            )
            if source is None:
                raise SubscriptionQuotaRolloverError("source quota cycle was not found.")
            if (
                source.subscription_id != command.subscription_id
                or source.metric_code != command.metric_code.strip().lower()
                or source.customer_ref != subscription.customer_ref
            ):
                raise SubscriptionQuotaRolloverError(
                    "source quota cycle conflicts with the subscription."
                )
            if source.period_end != command.period_start:
                raise SubscriptionQuotaRolloverError("quota periods are not contiguous.")

            cycle = AdminMarketSubscriptionQuotaCycle(
                subscription_id=subscription.id,
                source_cycle_id=source.id,
                customer_ref=subscription.customer_ref,
                quota_profile_ref=source.quota_profile_ref,
                metric_code=source.metric_code,
                period_start=command.period_start,
                period_end=command.period_end,
                base_limit_units=command.base_limit_units,
                rollover_units=source.available_units,
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
) -> None:
    if (
        existing.subscription_id != command.subscription_id
        or existing.source_cycle_id != command.source_cycle_id
        or existing.metric_code != command.metric_code.strip().lower()
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
