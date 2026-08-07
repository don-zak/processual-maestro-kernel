from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from processual_api.admin_marketplace.subscription_top_up_reversal_persistence import (
    AdminMarketSubscriptionTopUpReversal,
)


class SubscriptionTopUpReversalError(RuntimeError):
    """A granted subscription top-up cannot be reversed safely."""


@dataclass(frozen=True, slots=True)
class ReverseSubscriptionTopUpCommand:
    order_id: uuid.UUID
    provider_event_ref: str
    reason_code: str
    reversed_at: datetime


@dataclass(frozen=True, slots=True)
class SubscriptionTopUpReversalResult:
    reversal_id: uuid.UUID
    order_id: uuid.UUID
    grant_id: uuid.UUID
    units: int
    outcome: str
    idempotent_replay: bool
    committed: bool


async def reverse_subscription_top_up_in_uow(
    *,
    uow: object,
    command: ReverseSubscriptionTopUpCommand,
) -> SubscriptionTopUpReversalResult:
    _validate(command)

    existing_event = await uow.subscription_top_up_reversals.get_by_provider_event_ref(
        command.provider_event_ref,
        for_update=True,
    )
    if existing_event is not None:
        if existing_event.order_id != command.order_id:
            raise SubscriptionTopUpReversalError(
                "top-up reversal event already belongs to another order."
            )
        return _result(existing_event, replay=True, committed=False)

    grant = await uow.subscription_top_up_grants.get_by_order_id(
        command.order_id,
        for_update=True,
    )
    if grant is None:
        raise SubscriptionTopUpReversalError("top-up grant was not found.")

    existing_grant = await uow.subscription_top_up_reversals.get_by_grant_id(
        grant.id,
        for_update=True,
    )
    if existing_grant is not None:
        raise SubscriptionTopUpReversalError(
            "top-up grant already has a reversal decision."
        )

    order = await uow.top_up_orders.get_by_id(command.order_id, for_update=True)
    if order is None or order.state != "granted":
        raise SubscriptionTopUpReversalError(
            "top-up reversal requires a granted order."
        )
    if (
        grant.order_id != order.id
        or grant.subscription_id != order.subscription_id
        or grant.quota_cycle_id != order.quota_cycle_id
        or grant.customer_ref != order.customer_ref
    ):
        raise SubscriptionTopUpReversalError(
            "top-up grant conflicts with the authoritative order snapshot."
        )

    cycle = await uow.subscription_quota_cycles.get_by_id(
        grant.quota_cycle_id,
        for_update=True,
    )
    if cycle is None:
        raise SubscriptionTopUpReversalError("top-up quota cycle was not found.")
    if (
        cycle.subscription_id != grant.subscription_id
        or cycle.customer_ref != grant.customer_ref
    ):
        raise SubscriptionTopUpReversalError(
            "top-up reversal conflicts with the quota cycle."
        )
    if cycle.top_up_units < grant.units:
        raise SubscriptionTopUpReversalError(
            "quota cycle contains fewer top-up units than the grant ledger."
        )

    remaining_top_up_units = cycle.top_up_units - grant.units
    maximum_after_reversal = (
        cycle.base_limit_units
        + cycle.spendable_rollover_units
        + remaining_top_up_units
    )
    can_reverse_balance = cycle.used_units <= maximum_after_reversal
    outcome = "reversed" if can_reverse_balance else "manual_review"
    reason_code = command.reason_code if can_reverse_balance else "units_already_consumed"

    reversal = AdminMarketSubscriptionTopUpReversal(
        id=uuid.uuid4(),
        order_id=order.id,
        grant_id=grant.id,
        subscription_id=grant.subscription_id,
        quota_cycle_id=grant.quota_cycle_id,
        customer_ref=grant.customer_ref,
        provider_event_ref=command.provider_event_ref,
        units=grant.units,
        outcome=outcome,
        reason_code=reason_code,
        reversed_at=command.reversed_at,
    )
    uow.subscription_top_up_reversals.add(reversal)

    if can_reverse_balance:
        cycle.top_up_units = remaining_top_up_units
        cycle.version += 1

    return _result(reversal, replay=False, committed=False)


def reverse_subscription_top_up_factory(
    *,
    unit_of_work_factory: Callable[[], object],
):
    async def reverse(
        command: ReverseSubscriptionTopUpCommand,
    ) -> SubscriptionTopUpReversalResult:
        async with unit_of_work_factory() as uow:
            result = await reverse_subscription_top_up_in_uow(
                uow=uow,
                command=command,
            )
            if result.idempotent_replay:
                return result
            await uow.commit()
            return SubscriptionTopUpReversalResult(
                reversal_id=result.reversal_id,
                order_id=result.order_id,
                grant_id=result.grant_id,
                units=result.units,
                outcome=result.outcome,
                idempotent_replay=False,
                committed=True,
            )

    return reverse


def _result(
    reversal: AdminMarketSubscriptionTopUpReversal,
    *,
    replay: bool,
    committed: bool,
) -> SubscriptionTopUpReversalResult:
    return SubscriptionTopUpReversalResult(
        reversal_id=reversal.id,
        order_id=reversal.order_id,
        grant_id=reversal.grant_id,
        units=reversal.units,
        outcome=reversal.outcome,
        idempotent_replay=replay,
        committed=committed,
    )


def _validate(command: ReverseSubscriptionTopUpCommand) -> None:
    if not command.provider_event_ref.strip():
        raise ValueError("provider_event_ref must not be blank.")
    if not command.reason_code.strip():
        raise ValueError("reason_code must not be blank.")
    if command.reversed_at.tzinfo is None:
        raise ValueError("top-up reversal timestamp must be timezone-aware.")


__all__ = [
    "ReverseSubscriptionTopUpCommand",
    "SubscriptionTopUpReversalError",
    "SubscriptionTopUpReversalResult",
    "reverse_subscription_top_up_factory",
    "reverse_subscription_top_up_in_uow",
]
