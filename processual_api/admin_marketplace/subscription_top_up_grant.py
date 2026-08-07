from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from processual_api.admin_marketplace.subscription_top_up_eligibility import (
    TOP_UP_MINIMUM_MONTHLY_CONSUMPTION_PERCENT,
)
from processual_api.admin_marketplace.subscription_top_up_grant_persistence import (
    AdminMarketSubscriptionTopUpGrant,
)
from processual_api.billing.commercial_quota_top_up_contracts import quote_top_up
from processual_api.billing.plan_fulfillment_catalog import (
    PLAN_FULFILLMENT_CATALOG_VERSION,
    QUOTA_METRIC_CODE,
    get_plan_fulfillment_spec,
)


class SubscriptionTopUpGrantError(RuntimeError):
    """Verified top-up units cannot be granted safely."""


@dataclass(frozen=True, slots=True)
class SubscriptionTopUpGrantCommand:
    order_id: uuid.UUID
    subscription_id: uuid.UUID
    quota_cycle_id: uuid.UUID
    customer_ref: str
    provider_reference: str
    granted_at: datetime


@dataclass(frozen=True, slots=True)
class SubscriptionTopUpGrantResult:
    grant_id: uuid.UUID
    order_id: uuid.UUID
    quota_cycle_id: uuid.UUID
    units: int
    expires_at: datetime
    idempotent_replay: bool
    committed: bool


async def apply_verified_subscription_top_up_in_uow(
    *,
    uow: object,
    command: SubscriptionTopUpGrantCommand,
) -> SubscriptionTopUpGrantResult:
    _validate(command)
    grant_key = f"subscription-top-up:{command.order_id}"

    existing = await uow.subscription_top_up_grants.get_by_order_id(
        command.order_id,
        for_update=True,
    )
    if existing is not None:
        _assert_replay_matches(existing=existing, command=command)
        return SubscriptionTopUpGrantResult(
            grant_id=existing.id,
            order_id=existing.order_id,
            quota_cycle_id=existing.quota_cycle_id,
            units=existing.units,
            expires_at=existing.expires_at,
            idempotent_replay=True,
            committed=False,
        )

    order = await uow.top_up_orders.get_by_id(command.order_id, for_update=True)
    if order is None:
        raise SubscriptionTopUpGrantError("top-up order was not found.")
    if (
        order.subscription_id != command.subscription_id
        or order.quota_cycle_id != command.quota_cycle_id
        or order.customer_ref != command.customer_ref
        or order.plan_catalog_version != PLAN_FULFILLMENT_CATALOG_VERSION
    ):
        raise SubscriptionTopUpGrantError(
            "top-up order ownership snapshot conflicts with the grant command."
        )
    if order.state not in {"awaiting_payment", "payment_verified"}:
        raise SubscriptionTopUpGrantError(
            "top-up order is not eligible for a new grant."
        )

    subscription = await uow.subscriptions.get_by_id(
        command.subscription_id,
        for_update=True,
    )
    if subscription is None or subscription.status != "active":
        raise SubscriptionTopUpGrantError(
            "top-up grant requires an active subscription."
        )
    if subscription.customer_ref != command.customer_ref:
        raise SubscriptionTopUpGrantError(
            "top-up grant customer conflicts with the subscription."
        )

    plan = await uow.plans.get_by_id(subscription.plan_id, for_update=True)
    if plan is None:
        raise SubscriptionTopUpGrantError("subscription plan was not found.")
    try:
        spec = get_plan_fulfillment_spec(plan.plan_code)
    except KeyError as exc:
        raise SubscriptionTopUpGrantError(
            "subscription plan is not authoritative."
        ) from exc
    if order.plan_code != spec.plan_code:
        raise SubscriptionTopUpGrantError(
            "top-up order plan conflicts with the subscription."
        )

    cycle = await uow.subscription_quota_cycles.get_by_id(
        command.quota_cycle_id,
        for_update=True,
    )
    if cycle is None:
        raise SubscriptionTopUpGrantError("quota cycle was not found.")
    if (
        cycle.subscription_id != subscription.id
        or cycle.customer_ref != command.customer_ref
        or cycle.metric_code != QUOTA_METRIC_CODE
    ):
        raise SubscriptionTopUpGrantError(
            "quota cycle conflicts with the top-up grant."
        )
    if not cycle.period_start <= command.granted_at < cycle.period_end:
        raise SubscriptionTopUpGrantError(
            "top-up grant requires the current monthly quota cycle."
        )
    if (
        cycle.plan_code != spec.plan_code
        or cycle.plan_catalog_version != PLAN_FULFILLMENT_CATALOG_VERSION
        or cycle.base_limit_units != spec.monthly_unit_allowance
    ):
        raise SubscriptionTopUpGrantError(
            "quota cycle conflicts with the authoritative plan snapshot."
        )

    minimum_used_units = _ceil_percent(
        cycle.base_limit_units,
        TOP_UP_MINIMUM_MONTHLY_CONSUMPTION_PERCENT,
    )
    if cycle.used_units < minimum_used_units:
        raise SubscriptionTopUpGrantError(
            "top-up grant requires at least 80% consumption of the monthly base quota."
        )

    quote = quote_top_up(spec.plan_code, order.requested_units)
    if quote.total_units <= 0 or quote.bundle_count <= 0:
        raise SubscriptionTopUpGrantError(
            "top-up order does not resolve to an authoritative quote."
        )
    if (
        order.bundle_count != quote.bundle_count
        or order.requested_units != quote.total_units
        or Decimal(order.total_price_usd) != quote.total_price_usd
    ):
        raise SubscriptionTopUpGrantError(
            "top-up order snapshot conflicts with the authoritative quote."
        )

    payment = await uow.top_up_payments.get_by_provider_reference(
        command.provider_reference
    )
    if payment is None or payment.order_id != order.id:
        raise SubscriptionTopUpGrantError(
            "verified payment does not belong to the top-up order."
        )
    if payment.outcome != "verified":
        raise SubscriptionTopUpGrantError("top-up payment is not verified.")
    expected_currency = order.settlement_currency.strip().upper()
    if payment.verified_currency != expected_currency:
        raise SubscriptionTopUpGrantError(
            "verified payment currency conflicts with the top-up order."
        )
    if Decimal(payment.verified_amount) != Decimal(order.settlement_amount):
        raise SubscriptionTopUpGrantError(
            "verified payment amount conflicts with the top-up order."
        )

    duplicate_key = await uow.subscription_top_up_grants.get_by_idempotency_key(
        grant_key,
        for_update=True,
    )
    if duplicate_key is not None:
        raise SubscriptionTopUpGrantError(
            "top-up grant idempotency key already belongs to another grant."
        )

    grant_record = AdminMarketSubscriptionTopUpGrant(
        id=uuid.uuid4(),
        order_id=order.id,
        subscription_id=subscription.id,
        quota_cycle_id=cycle.id,
        customer_ref=subscription.customer_ref,
        plan_code=spec.plan_code,
        plan_catalog_version=PLAN_FULFILLMENT_CATALOG_VERSION,
        units=quote.total_units,
        grant_idempotency_key=grant_key,
        provider_reference=command.provider_reference,
        granted_at=command.granted_at,
        expires_at=cycle.period_end,
    )
    uow.subscription_top_up_grants.add(grant_record)
    cycle.top_up_units += quote.total_units
    cycle.version += 1
    order.state = "granted"
    return SubscriptionTopUpGrantResult(
        grant_id=grant_record.id,
        order_id=grant_record.order_id,
        quota_cycle_id=grant_record.quota_cycle_id,
        units=grant_record.units,
        expires_at=grant_record.expires_at,
        idempotent_replay=False,
        committed=False,
    )


def grant_verified_subscription_top_up_factory(
    *,
    unit_of_work_factory: Callable[[], object],
):
    async def grant(
        command: SubscriptionTopUpGrantCommand,
    ) -> SubscriptionTopUpGrantResult:
        async with unit_of_work_factory() as uow:
            result = await apply_verified_subscription_top_up_in_uow(
                uow=uow,
                command=command,
            )
            if result.idempotent_replay:
                return result
            await uow.commit()
            return SubscriptionTopUpGrantResult(
                grant_id=result.grant_id,
                order_id=result.order_id,
                quota_cycle_id=result.quota_cycle_id,
                units=result.units,
                expires_at=result.expires_at,
                idempotent_replay=False,
                committed=True,
            )

    return grant


def _ceil_percent(value: int, percent: int) -> int:
    return (value * percent + 99) // 100


def _validate(command: SubscriptionTopUpGrantCommand) -> None:
    if not command.customer_ref.strip():
        raise ValueError("customer_ref must not be blank.")
    if not command.provider_reference.strip():
        raise ValueError("provider_reference must not be blank.")
    if command.granted_at.tzinfo is None:
        raise ValueError("top-up grant timestamp must be timezone-aware.")


def _assert_replay_matches(
    *,
    existing: AdminMarketSubscriptionTopUpGrant,
    command: SubscriptionTopUpGrantCommand,
) -> None:
    if (
        existing.subscription_id != command.subscription_id
        or existing.quota_cycle_id != command.quota_cycle_id
        or existing.customer_ref != command.customer_ref
        or existing.provider_reference != command.provider_reference
    ):
        raise SubscriptionTopUpGrantError(
            "top-up grant replay conflicts with the existing ledger entry."
        )


__all__ = [
    "SubscriptionTopUpGrantCommand",
    "SubscriptionTopUpGrantError",
    "SubscriptionTopUpGrantResult",
    "apply_verified_subscription_top_up_in_uow",
    "grant_verified_subscription_top_up_factory",
]
