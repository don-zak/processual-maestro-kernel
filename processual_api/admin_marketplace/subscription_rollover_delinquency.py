from __future__ import annotations

from datetime import datetime


class SubscriptionRolloverDelinquencyError(RuntimeError):
    """Rollover delinquency state cannot be applied safely."""


async def lock_rollover_for_delinquency(
    *,
    uow: object,
    subscription_id: object,
    effective_at: datetime,
    expires_at: datetime,
) -> list[object]:
    _validate_times(effective_at=effective_at, expires_at=expires_at)
    cycles = await uow.subscription_quota_cycles.list_rollover_cycles(
        subscription_id=subscription_id,
        for_update=True,
    )
    changed: list[object] = []
    for cycle in cycles:
        if cycle.rollover_status == "expired":
            continue
        if cycle.rollover_status == "locked_for_delinquency":
            if cycle.rollover_expires_at != expires_at:
                raise SubscriptionRolloverDelinquencyError(
                    "locked rollover expiry conflicts with the current delinquency."
                )
            continue
        cycle.rollover_status = "locked_for_delinquency"
        cycle.rollover_locked_at = effective_at
        cycle.rollover_expires_at = expires_at
        cycle.rollover_restored_at = None
        cycle.rollover_expired_at = None
        cycle.version += 1
        changed.append(cycle)
    return changed


async def restore_or_expire_rollover_after_payment(
    *,
    uow: object,
    subscription_id: object,
    effective_at: datetime,
) -> list[object]:
    if effective_at.tzinfo is None:
        raise ValueError("rollover payment timestamp must be timezone-aware.")
    cycles = await uow.subscription_quota_cycles.list_rollover_cycles(
        subscription_id=subscription_id,
        for_update=True,
    )
    changed: list[object] = []
    for cycle in cycles:
        if cycle.rollover_status != "locked_for_delinquency":
            continue
        expires_at = cycle.rollover_expires_at
        if expires_at is None or expires_at.tzinfo is None:
            raise SubscriptionRolloverDelinquencyError(
                "locked rollover requires a valid expiry timestamp."
            )
        if effective_at < expires_at:
            cycle.rollover_status = "restored"
            cycle.rollover_restored_at = effective_at
            cycle.rollover_expired_at = None
        else:
            cycle.rollover_status = "expired"
            cycle.rollover_expired_at = effective_at
            cycle.rollover_restored_at = None
        cycle.version += 1
        changed.append(cycle)
    return changed


async def expire_overdue_rollover(
    *,
    uow: object,
    subscription_id: object,
    evaluated_at: datetime,
) -> list[object]:
    if evaluated_at.tzinfo is None:
        raise ValueError("rollover expiry timestamp must be timezone-aware.")
    cycles = await uow.subscription_quota_cycles.list_rollover_cycles(
        subscription_id=subscription_id,
        for_update=True,
    )
    changed: list[object] = []
    for cycle in cycles:
        if cycle.rollover_status != "locked_for_delinquency":
            continue
        expires_at = cycle.rollover_expires_at
        if expires_at is None or expires_at.tzinfo is None:
            raise SubscriptionRolloverDelinquencyError(
                "locked rollover requires a valid expiry timestamp."
            )
        if evaluated_at < expires_at:
            continue
        cycle.rollover_status = "expired"
        cycle.rollover_expired_at = evaluated_at
        cycle.rollover_restored_at = None
        cycle.version += 1
        changed.append(cycle)
    return changed


def _validate_times(*, effective_at: datetime, expires_at: datetime) -> None:
    if effective_at.tzinfo is None or expires_at.tzinfo is None:
        raise ValueError("rollover delinquency timestamps must be timezone-aware.")
    if expires_at <= effective_at:
        raise ValueError("rollover expiry must follow the delinquency timestamp.")


__all__ = [
    "SubscriptionRolloverDelinquencyError",
    "expire_overdue_rollover",
    "lock_rollover_for_delinquency",
    "restore_or_expire_rollover_after_payment",
]
