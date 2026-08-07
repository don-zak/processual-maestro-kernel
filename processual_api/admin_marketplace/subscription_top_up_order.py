from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime

from processual_api.admin_marketplace.subscription_top_up_eligibility import (
    TOP_UP_MINIMUM_MONTHLY_CONSUMPTION_PERCENT,
)
from processual_api.billing.commercial_currency_settlement_contracts import (
    ExchangeRateProviderPort,
    calculate_tnd_settlement,
    validate_channel_settlement,
)
from processual_api.billing.commercial_quota_top_up_contracts import quote_top_up
from processual_api.billing.commercial_settings_top_up_checkout_contracts import (
    TopUpCheckoutChannel,
)
from processual_api.billing.commercial_top_up_models import CommercialTopUpOrder
from processual_api.billing.plan_fulfillment_catalog import (
    PLAN_FULFILLMENT_CATALOG_VERSION,
    QUOTA_METRIC_CODE,
    get_plan_fulfillment_spec,
)


class SubscriptionTopUpOrderError(RuntimeError):
    """An authoritative top-up order cannot be created safely."""


LocalTunisiaEligibilityResolver = Callable[
    [str, uuid.UUID, datetime],
    Awaitable[bool],
]


@dataclass(frozen=True, slots=True)
class CreateSubscriptionTopUpOrderCommand:
    order_id: uuid.UUID
    customer_ref: str
    subscription_id: uuid.UUID
    quota_cycle_id: uuid.UUID
    requested_units: int
    channel: TopUpCheckoutChannel
    idempotency_key: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class SubscriptionTopUpOrderResult:
    order_id: uuid.UUID
    plan_code: str
    quota_cycle_id: uuid.UUID
    requested_units: int
    bundle_count: int
    total_price_usd: str
    settlement_currency: str
    settlement_amount: str
    channel: str
    idempotent_replay: bool
    committed: bool


def create_subscription_top_up_order_factory(
    *,
    unit_of_work_factory: Callable[[], object],
    local_tunisia_eligibility_resolver: LocalTunisiaEligibilityResolver | None = None,
    exchange_rate_provider: ExchangeRateProviderPort | None = None,
):
    async def create(
        command: CreateSubscriptionTopUpOrderCommand,
    ) -> SubscriptionTopUpOrderResult:
        _validate(command)

        async with unit_of_work_factory() as uow:
            existing = await uow.top_up_orders.get_by_idempotency_key(
                command.idempotency_key
            )
            if existing is not None:
                _assert_replay_matches(command=command, existing=existing)
                return _result(existing, replay=True, committed=False)

            subscription = await uow.subscriptions.get_by_id(
                command.subscription_id,
                for_update=True,
            )
            if subscription is None or subscription.status != "active":
                raise SubscriptionTopUpOrderError(
                    "top-up order requires an active subscription."
                )
            if subscription.customer_ref != command.customer_ref:
                raise SubscriptionTopUpOrderError(
                    "top-up order customer conflicts with the subscription."
                )

            plan = await uow.plans.get_by_id(subscription.plan_id, for_update=True)
            if plan is None:
                raise SubscriptionTopUpOrderError("subscription plan was not found.")
            try:
                spec = get_plan_fulfillment_spec(plan.plan_code)
            except KeyError as exc:
                raise SubscriptionTopUpOrderError(
                    "subscription plan is not authoritative."
                ) from exc

            cycle = await uow.subscription_quota_cycles.get_by_id(
                command.quota_cycle_id,
                for_update=True,
            )
            if cycle is None:
                raise SubscriptionTopUpOrderError("quota cycle was not found.")
            if (
                cycle.subscription_id != subscription.id
                or cycle.customer_ref != command.customer_ref
                or cycle.metric_code != QUOTA_METRIC_CODE
            ):
                raise SubscriptionTopUpOrderError(
                    "quota cycle conflicts with the top-up order."
                )
            if not cycle.period_start <= command.created_at < cycle.period_end:
                raise SubscriptionTopUpOrderError(
                    "top-up order requires the current monthly quota cycle."
                )
            if (
                cycle.plan_code != spec.plan_code
                or cycle.plan_catalog_version != PLAN_FULFILLMENT_CATALOG_VERSION
                or cycle.base_limit_units != spec.monthly_unit_allowance
            ):
                raise SubscriptionTopUpOrderError(
                    "quota cycle conflicts with the authoritative plan snapshot."
                )

            minimum_used_units = _ceil_percent(
                cycle.base_limit_units,
                TOP_UP_MINIMUM_MONTHLY_CONSUMPTION_PERCENT,
            )
            if cycle.used_units < minimum_used_units:
                raise SubscriptionTopUpOrderError(
                    "top-up order requires at least 80% consumption of the monthly base quota."
                )

            quote = quote_top_up(spec.plan_code, command.requested_units)
            if quote.total_units <= 0 or quote.bundle_count <= 0:
                raise SubscriptionTopUpOrderError(
                    f"top-up request is not purchasable: {quote.state.value}."
                )
            if quote.total_units != command.requested_units:
                raise SubscriptionTopUpOrderError(
                    "top-up quote units conflict with the requested units."
                )

            settlement_currency = "USD"
            settlement_amount = quote.total_price_usd
            exchange_rate_quote = None

            if command.channel is TopUpCheckoutChannel.LOCAL_TUNISIA:
                if (
                    local_tunisia_eligibility_resolver is None
                    or exchange_rate_provider is None
                ):
                    raise SubscriptionTopUpOrderError(
                        "Tunisia-local top-up ordering is not configured."
                    )
                eligible = await local_tunisia_eligibility_resolver(
                    command.customer_ref,
                    command.subscription_id,
                    command.created_at,
                )
                if not eligible:
                    raise SubscriptionTopUpOrderError(
                        "customer is not eligible for Tunisia-local settlement."
                    )
                exchange_rate_quote = await exchange_rate_provider.quote_usd_to_tnd(
                    requested_at=command.created_at,
                )
                if exchange_rate_quote.is_expired_at(command.created_at):
                    raise SubscriptionTopUpOrderError(
                        "Tunisia-local exchange-rate quote is expired."
                    )
                settlement_currency = "TND"
                settlement_amount = calculate_tnd_settlement(
                    amount_usd=quote.total_price_usd,
                    usd_tnd_rate=exchange_rate_quote.rate,
                )
            elif command.channel is not TopUpCheckoutChannel.LEMON_SQUEEZY:
                raise SubscriptionTopUpOrderError("unsupported top-up checkout channel.")

            try:
                validate_channel_settlement(
                    channel=command.channel,
                    total_price_usd=quote.total_price_usd,
                    settlement_currency=settlement_currency,
                    settlement_amount=settlement_amount,
                    exchange_rate_quote=exchange_rate_quote,
                )
            except (TypeError, ValueError) as exc:
                raise SubscriptionTopUpOrderError(
                    "top-up settlement snapshot is invalid."
                ) from exc

            order = CommercialTopUpOrder(
                id=command.order_id,
                account_id=None,
                customer_ref=subscription.customer_ref,
                subscription_id=subscription.id,
                quota_cycle_id=cycle.id,
                plan_code=spec.plan_code,
                plan_catalog_version=PLAN_FULFILLMENT_CATALOG_VERSION,
                requested_units=quote.total_units,
                bundle_count=quote.bundle_count,
                total_price_usd=quote.total_price_usd,
                settlement_currency=settlement_currency,
                settlement_amount=settlement_amount,
                exchange_rate_usd_tnd=(
                    None if exchange_rate_quote is None else exchange_rate_quote.rate
                ),
                exchange_rate_source=(
                    None if exchange_rate_quote is None else exchange_rate_quote.source
                ),
                exchange_rate_reference=(
                    None if exchange_rate_quote is None else exchange_rate_quote.reference
                ),
                exchange_rate_observed_at=(
                    None if exchange_rate_quote is None else exchange_rate_quote.observed_at
                ),
                exchange_rate_expires_at=(
                    None if exchange_rate_quote is None else exchange_rate_quote.expires_at
                ),
                channel=command.channel.value,
                idempotency_key=command.idempotency_key,
                state="awaiting_payment",
                created_at=command.created_at,
            )
            uow.top_up_orders.add(order)
            await uow.commit()
            return _result(order, replay=False, committed=True)

    return create


def _result(
    order: CommercialTopUpOrder,
    *,
    replay: bool,
    committed: bool,
) -> SubscriptionTopUpOrderResult:
    return SubscriptionTopUpOrderResult(
        order_id=order.id,
        plan_code=order.plan_code,
        quota_cycle_id=order.quota_cycle_id,
        requested_units=order.requested_units,
        bundle_count=order.bundle_count,
        total_price_usd=str(order.total_price_usd),
        settlement_currency=order.settlement_currency,
        settlement_amount=str(order.settlement_amount),
        channel=order.channel,
        idempotent_replay=replay,
        committed=committed,
    )


def _assert_replay_matches(
    *,
    command: CreateSubscriptionTopUpOrderCommand,
    existing: CommercialTopUpOrder,
) -> None:
    if (
        existing.id != command.order_id
        or existing.customer_ref != command.customer_ref
        or existing.subscription_id != command.subscription_id
        or existing.quota_cycle_id != command.quota_cycle_id
        or existing.requested_units != command.requested_units
        or existing.channel != command.channel.value
        or existing.plan_catalog_version != PLAN_FULFILLMENT_CATALOG_VERSION
    ):
        raise SubscriptionTopUpOrderError(
            "top-up order idempotency replay conflicts with the existing order."
        )


def _ceil_percent(value: int, percent: int) -> int:
    return (value * percent + 99) // 100


def _validate(command: CreateSubscriptionTopUpOrderCommand) -> None:
    if not command.customer_ref.strip():
        raise ValueError("customer_ref must not be blank.")
    if command.requested_units <= 0:
        raise ValueError("requested_units must be positive.")
    if not command.idempotency_key.strip():
        raise ValueError("idempotency_key must not be blank.")
    if command.created_at.tzinfo is None:
        raise ValueError("top-up order timestamp must be timezone-aware.")


__all__ = [
    "CreateSubscriptionTopUpOrderCommand",
    "LocalTunisiaEligibilityResolver",
    "SubscriptionTopUpOrderError",
    "SubscriptionTopUpOrderResult",
    "create_subscription_top_up_order_factory",
]
