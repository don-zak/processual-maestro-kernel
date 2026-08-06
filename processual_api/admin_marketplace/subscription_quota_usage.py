from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from processual_api.admin_marketplace.subscription_quota_usage_persistence import (
    AdminMarketSubscriptionQuotaCycleUsage,
)


class SubscriptionQuotaUsageError(RuntimeError):
    """Quota usage cannot be recorded safely."""


@dataclass(frozen=True, slots=True)
class SubscriptionQuotaUsageCommand:
    subscription_id: uuid.UUID
    quota_cycle_id: uuid.UUID
    customer_ref: str
    metric_code: str
    units: int
    idempotency_key_hash: str
    dimensions_digest: str
    occurred_at: datetime


def record_subscription_quota_usage_factory(
    *,
    unit_of_work_factory: Callable[[], object],
):
    async def record(
        command: SubscriptionQuotaUsageCommand,
    ) -> AdminMarketSubscriptionQuotaCycleUsage:
        _validate(command)
        async with unit_of_work_factory() as uow:
            existing = await uow.subscription_quota_cycle_usage.get_by_idempotency_hash(
                command.idempotency_key_hash,
                for_update=True,
            )
            if existing is not None:
                _assert_replay_matches(command, existing)
                return existing

            subscription = await uow.subscriptions.get_by_id(
                command.subscription_id,
                for_update=True,
            )
            if subscription is None or subscription.status != "active":
                raise SubscriptionQuotaUsageError(
                    "quota usage requires an active subscription."
                )
            if subscription.customer_ref != command.customer_ref:
                raise SubscriptionQuotaUsageError(
                    "quota usage customer conflicts with subscription."
                )

            runtime = await uow.subscription_runtime.get_by_subscription_id(
                command.subscription_id,
                for_update=True,
            )
            if runtime is None or runtime.access_stage != "active":
                raise SubscriptionQuotaUsageError(
                    "quota usage requires active runtime access."
                )
            if runtime.customer_ref != command.customer_ref:
                raise SubscriptionQuotaUsageError(
                    "quota usage customer conflicts with runtime."
                )

            cycle = await uow.subscription_quota_cycles.get_by_id(
                command.quota_cycle_id,
                for_update=True,
            )
            if cycle is None:
                raise SubscriptionQuotaUsageError("quota cycle was not found.")
            if (
                cycle.subscription_id != command.subscription_id
                or cycle.customer_ref != command.customer_ref
                or cycle.metric_code != command.metric_code
            ):
                raise SubscriptionQuotaUsageError(
                    "quota cycle conflicts with usage command."
                )
            if not cycle.period_start <= command.occurred_at < cycle.period_end:
                raise SubscriptionQuotaUsageError(
                    "quota usage falls outside the selected cycle."
                )
            if command.units > cycle.available_units:
                raise SubscriptionQuotaUsageError("quota balance is insufficient.")

            cycle.used_units += command.units
            cycle.version += 1
            usage = AdminMarketSubscriptionQuotaCycleUsage(
                quota_cycle_id=cycle.id,
                subscription_id=cycle.subscription_id,
                customer_ref=cycle.customer_ref,
                metric_code=cycle.metric_code,
                units=command.units,
                idempotency_key_hash=command.idempotency_key_hash,
                dimensions_digest=command.dimensions_digest,
                occurred_at=command.occurred_at,
            )
            uow.subscription_quota_cycle_usage.add(usage)
            await uow.commit()
            return usage

    return record


def _validate(command: SubscriptionQuotaUsageCommand) -> None:
    if command.units <= 0:
        raise ValueError("quota usage units must be positive.")
    if command.occurred_at.tzinfo is None:
        raise ValueError("quota usage timestamp must be timezone-aware.")
    if len(command.idempotency_key_hash) != 64:
        raise ValueError("quota usage idempotency hash must contain 64 characters.")
    if len(command.dimensions_digest) != 64:
        raise ValueError("quota usage dimensions digest must contain 64 characters.")


def _assert_replay_matches(
    command: SubscriptionQuotaUsageCommand,
    existing: AdminMarketSubscriptionQuotaCycleUsage,
) -> None:
    if (
        existing.quota_cycle_id != command.quota_cycle_id
        or existing.subscription_id != command.subscription_id
        or existing.customer_ref != command.customer_ref
        or existing.metric_code != command.metric_code
        or existing.units != command.units
        or existing.dimensions_digest != command.dimensions_digest
        or existing.occurred_at != command.occurred_at
    ):
        raise SubscriptionQuotaUsageError(
            "quota usage replay conflicts with the existing ledger entry."
        )


__all__ = [
    "SubscriptionQuotaUsageCommand",
    "SubscriptionQuotaUsageError",
    "record_subscription_quota_usage_factory",
]
