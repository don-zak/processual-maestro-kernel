from __future__ import annotations

from datetime import datetime, timedelta

from processual_api.admin_marketplace.subscription_delinquency_persistence import (
    AdminMarketSubscriptionDelinquency,
)

GRACE_DAYS = 15
GRACE_USAGE_PERCENT = 25
FREEZE_AFTER_MISSED_CYCLES = 3
PENDING_DELETION_AFTER_MISSED_CYCLES = 6


def billing_cycle_key(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("billing cycle timestamp must be timezone-aware.")
    return value.strftime("%Y-%m")


async def apply_payment_failure(
    *,
    uow: object,
    subscription: object,
    effective_at: datetime,
) -> AdminMarketSubscriptionDelinquency:
    cycle_key = billing_cycle_key(effective_at)
    record = await uow.subscription_delinquency.get_by_subscription_id(
        subscription.id,
        for_update=True,
    )
    if record is None:
        record = AdminMarketSubscriptionDelinquency(
            subscription_id=subscription.id,
            customer_ref=subscription.customer_ref,
            state="grace_degraded",
            missed_billing_cycles=1,
            last_failed_cycle_key=cycle_key,
            first_failed_at=effective_at,
            last_failed_at=effective_at,
            grace_until=effective_at + timedelta(days=GRACE_DAYS),
            grace_usage_percent=GRACE_USAGE_PERCENT,
        )
        uow.subscription_delinquency.add(record)
        return record

    if record.customer_ref != subscription.customer_ref:
        raise RuntimeError("delinquency customer conflicts with subscription.")
    if record.last_failed_cycle_key != cycle_key:
        record.missed_billing_cycles += 1
        record.last_failed_cycle_key = cycle_key
    record.last_failed_at = effective_at
    record.resolved_at = None

    if record.missed_billing_cycles >= PENDING_DELETION_AFTER_MISSED_CYCLES:
        record.state = "pending_deletion"
        record.deletion_eligible_at = effective_at
        record.grace_until = None
    elif record.missed_billing_cycles >= FREEZE_AFTER_MISSED_CYCLES:
        record.state = "account_frozen"
        record.frozen_at = effective_at
        record.grace_until = None
    else:
        record.state = "grace_degraded"
        record.grace_until = effective_at + timedelta(days=GRACE_DAYS)
    return record


async def resolve_payment_delinquency(
    *,
    uow: object,
    subscription: object,
    effective_at: datetime,
) -> AdminMarketSubscriptionDelinquency | None:
    billing_cycle_key(effective_at)
    record = await uow.subscription_delinquency.get_by_subscription_id(
        subscription.id,
        for_update=True,
    )
    if record is None:
        return None
    if record.customer_ref != subscription.customer_ref:
        raise RuntimeError("delinquency customer conflicts with subscription.")
    record.state = "resolved"
    record.grace_until = None
    record.frozen_at = None
    record.deletion_eligible_at = None
    record.resolved_at = effective_at
    record.missed_billing_cycles = 0
    record.last_failed_cycle_key = None
    return record


__all__ = [
    "FREEZE_AFTER_MISSED_CYCLES",
    "GRACE_DAYS",
    "GRACE_USAGE_PERCENT",
    "PENDING_DELETION_AFTER_MISSED_CYCLES",
    "apply_payment_failure",
    "billing_cycle_key",
    "resolve_payment_delinquency",
]
