from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol

from processual_api.admin_marketplace.lemon_squeezy_reconciliation_gate import (
    LemonSqueezyReconciliationContext,
)
from processual_api.admin_marketplace.lemon_squeezy_webhooks import (
    LemonSqueezyWebhookError,
)


class LemonSqueezyContextUnitOfWork(Protocol):
    orders: object
    offers: object
    subscriptions: object
    lemon_squeezy_bindings: object


ContextLoader = Callable[
    [LemonSqueezyContextUnitOfWork, object],
    Awaitable[LemonSqueezyReconciliationContext],
]


def lemon_squeezy_reconciliation_context_loader_factory(
    *,
    production_mode: bool,
) -> ContextLoader:
    async def load(
        uow: LemonSqueezyContextUnitOfWork,
        inbox: object,
    ) -> LemonSqueezyReconciliationContext:
        order_ref = getattr(inbox, "order_ref", None)
        customer_ref = getattr(inbox, "customer_ref", None)
        offer_ref = getattr(inbox, "offer_ref", None)
        provider_customer_id = getattr(inbox, "provider_customer_id", None)
        provider_subscription_id = getattr(inbox, "provider_subscription_id", None)

        if not all(
            isinstance(value, str) and value
            for value in (
                order_ref,
                customer_ref,
                offer_ref,
                provider_customer_id,
            )
        ):
            raise LemonSqueezyWebhookError(
                "webhook reconciliation references are incomplete."
            )

        order = await uow.orders.get_by_ref(order_ref, for_update=True)
        if order is None:
            raise LemonSqueezyWebhookError(
                "referenced marketplace order was not found."
            )
        if order.customer_ref != customer_ref:
            raise LemonSqueezyWebhookError(
                "order customer binding conflicts with webhook."
            )
        if order.selected_channel != "lemon_squeezy":
            raise LemonSqueezyWebhookError(
                "order is not assigned to Lemon Squeezy."
            )

        offer = await uow.offers.get_by_id(order.offer_id, for_update=True)
        if offer is None:
            raise LemonSqueezyWebhookError(
                "referenced marketplace offer was not found."
            )
        if offer.offer_code != offer_ref:
            raise LemonSqueezyWebhookError(
                "offer binding conflicts with webhook."
            )
        if offer.sales_channel != "lemon_squeezy":
            raise LemonSqueezyWebhookError(
                "offer is not assigned to Lemon Squeezy."
            )
        if offer.billing_period != order.billing_period:
            raise LemonSqueezyWebhookError(
                "order billing period conflicts with offer."
            )

        binding = await uow.lemon_squeezy_bindings.get_by_order_id(
            order.id,
            for_update=True,
        )
        if binding is None:
            raise LemonSqueezyWebhookError(
                "Lemon Squeezy binding was not found."
            )
        if binding.customer_ref != customer_ref:
            raise LemonSqueezyWebhookError(
                "provider binding belongs to another customer."
            )
        if binding.offer_id != offer.id:
            raise LemonSqueezyWebhookError(
                "provider binding belongs to another offer."
            )
        if binding.provider_customer_id != provider_customer_id:
            raise LemonSqueezyWebhookError(
                "provider customer binding conflicts with webhook."
            )

        provider_customer_owner = (
            await uow.lemon_squeezy_bindings.get_by_provider_customer_id(
                provider_customer_id,
                for_update=True,
            )
        )
        if (
            provider_customer_owner is None
            or provider_customer_owner.id != binding.id
        ):
            raise LemonSqueezyWebhookError(
                "provider customer identifier has conflicting ownership."
            )

        active_subscription = await uow.subscriptions.get_active_by_customer_ref(
            customer_ref,
            for_update=True,
        )
        expected_subscription_id: str | None = binding.provider_subscription_id
        if active_subscription is not None:
            if active_subscription.order_id != order.id:
                raise LemonSqueezyWebhookError(
                    "customer has an active subscription for another order."
                )
            if active_subscription.offer_id != offer.id:
                raise LemonSqueezyWebhookError(
                    "active subscription offer conflicts with provider binding."
                )
            if binding.subscription_id != active_subscription.id:
                raise LemonSqueezyWebhookError(
                    "provider binding subscription conflicts with active subscription."
                )

        if provider_subscription_id is not None:
            provider_subscription_owner = (
                await uow.lemon_squeezy_bindings.get_by_provider_subscription_id(
                    provider_subscription_id,
                    for_update=True,
                )
            )
            if (
                provider_subscription_owner is None
                or provider_subscription_owner.id != binding.id
            ):
                raise LemonSqueezyWebhookError(
                    "provider subscription identifier has conflicting ownership."
                )
            expected_subscription_id = provider_subscription_id

        return LemonSqueezyReconciliationContext(
            expected_customer_ref=customer_ref,
            expected_order_ref=order.order_ref,
            expected_offer_ref=offer.offer_code,
            order_sales_channel=order.selected_channel,
            offer_sales_channel=offer.sales_channel,
            production_mode=production_mode,
            expected_provider_customer_id=binding.provider_customer_id,
            expected_provider_order_id=binding.provider_order_id,
            expected_provider_subscription_id=expected_subscription_id,
            expected_variant_id=binding.variant_id,
            expected_currency=binding.currency,
            expected_total_amount=binding.total_amount,
            latest_provider_effective_at=binding.last_provider_effective_at,
        )

    return load


__all__ = ["lemon_squeezy_reconciliation_context_loader_factory"]
