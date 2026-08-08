from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from processual_api.admin_marketplace.lemon_squeezy_inbox_lifecycle import (
    claim_lemon_squeezy_webhook,
    mark_lemon_squeezy_webhook_processed,
)
from processual_api.admin_marketplace.lemon_squeezy_webhooks import (
    LemonSqueezyWebhookError,
)
from processual_api.admin_marketplace.subscription_top_up_grant import (
    SubscriptionTopUpGrantCommand,
    SubscriptionTopUpGrantError,
    apply_verified_subscription_top_up_in_uow,
)
from processual_api.billing.commercial_top_up_models import (
    CommercialTopUpPaymentEvidence,
)

TOP_UP_OFFER_REF = "quota_top_up"


@dataclass(frozen=True, slots=True)
class LemonSqueezyTopUpProcessingResult:
    inbox_id: uuid.UUID
    order_id: uuid.UUID
    grant_id: uuid.UUID
    units: int
    replayed_grant: bool


def _usd_from_cents(value: object) -> Decimal:
    try:
        cents = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise LemonSqueezyWebhookError("top-up subtotal evidence is invalid.") from exc
    if not cents.is_finite() or cents < 0 or cents != cents.to_integral_value():
        raise LemonSqueezyWebhookError("top-up subtotal evidence is invalid.")
    return cents / Decimal(100)


def process_lemon_squeezy_top_up_factory(
    *,
    uow_factory: Callable[[], object],
):
    async def process(
        *,
        inbox_id: uuid.UUID,
        processed_at: datetime | None = None,
    ) -> LemonSqueezyTopUpProcessingResult:
        timestamp = processed_at or datetime.now(UTC)
        if timestamp.tzinfo is None:
            raise LemonSqueezyWebhookError("processed_at must be timezone-aware.")

        async with uow_factory() as uow:
            inbox = await uow.lemon_squeezy_webhook_inbox.get_by_id(
                inbox_id,
                for_update=True,
            )
            if inbox is None:
                raise LemonSqueezyWebhookError("top-up webhook inbox entry was not found.")
            if inbox.processing_status == "processed":
                try:
                    order_id = uuid.UUID(inbox.order_ref)
                except (ValueError, AttributeError) as exc:
                    raise LemonSqueezyWebhookError(
                        "processed top-up webhook has invalid order binding."
                    ) from exc
                existing = await uow.subscription_top_up_grants.get_by_order_id(
                    order_id,
                    for_update=True,
                )
                if existing is None:
                    raise LemonSqueezyWebhookError(
                        "processed top-up webhook is missing its grant ledger entry."
                    )
                return LemonSqueezyTopUpProcessingResult(
                    inbox_id=inbox.id,
                    order_id=order_id,
                    grant_id=existing.id,
                    units=existing.units,
                    replayed_grant=True,
                )

            if inbox.offer_ref != TOP_UP_OFFER_REF:
                raise LemonSqueezyWebhookError("webhook is not a top-up event.")
            if inbox.event_name != "order_created" or inbox.resource_type != "orders":
                raise LemonSqueezyWebhookError(
                    "top-up fulfillment requires a Lemon Squeezy order_created event."
                )
            if inbox.provider_status != "paid":
                raise LemonSqueezyWebhookError("top-up provider order is not paid.")
            if inbox.provider_order_id is None or inbox.provider_order_id != inbox.external_resource_id:
                raise LemonSqueezyWebhookError("top-up provider order binding is invalid.")
            if inbox.provider_subscription_id is not None:
                raise LemonSqueezyWebhookError(
                    "top-up purchase must not be bound to a provider subscription."
                )
            if inbox.currency != "USD" or inbox.subtotal_amount is None:
                raise LemonSqueezyWebhookError("top-up payment evidence is incomplete.")

            try:
                order_id = uuid.UUID(inbox.order_ref)
            except (ValueError, AttributeError) as exc:
                raise LemonSqueezyWebhookError("top-up order_ref must be a UUID.") from exc

            order = await uow.top_up_orders.get_by_id(order_id, for_update=True)
            if order is None:
                raise LemonSqueezyWebhookError("referenced top-up order was not found.")
            if (
                order.customer_ref != inbox.customer_ref
                or order.channel != "lemon_squeezy"
                or order.provider_variant_id is None
                or order.provider_variant_id != inbox.variant_id
            ):
                raise LemonSqueezyWebhookError(
                    "top-up webhook conflicts with the authoritative order binding."
                )

            verified_amount = _usd_from_cents(inbox.subtotal_amount)
            if verified_amount != Decimal(order.settlement_amount):
                raise LemonSqueezyWebhookError(
                    "top-up webhook subtotal conflicts with the authoritative order."
                )

            provider_reference = f"lemon_squeezy:order:{inbox.provider_order_id}"
            payment = await uow.top_up_payments.get_by_provider_reference(
                provider_reference
            )
            if payment is None:
                payment = CommercialTopUpPaymentEvidence(
                    id=uuid.uuid4(),
                    order_id=order.id,
                    provider_reference=provider_reference,
                    outcome="verified",
                    verified_amount=verified_amount,
                    verified_currency="USD",
                    immutable_evidence_reference=f"ls-inbox:{inbox.id}:{inbox.payload_digest}",
                    created_at=timestamp,
                )
                uow.top_up_payments.add(payment)
            elif (
                payment.order_id != order.id
                or payment.outcome != "verified"
                or Decimal(payment.verified_amount) != verified_amount
                or payment.verified_currency != "USD"
            ):
                raise LemonSqueezyWebhookError(
                    "provider payment reference conflicts with existing top-up evidence."
                )

            if order.state == "awaiting_payment":
                order.state = "payment_verified"

            claim_lemon_squeezy_webhook(inbox, claimed_at=timestamp)
            try:
                grant = await apply_verified_subscription_top_up_in_uow(
                    uow=uow,
                    command=SubscriptionTopUpGrantCommand(
                        order_id=order.id,
                        subscription_id=order.subscription_id,
                        quota_cycle_id=order.quota_cycle_id,
                        customer_ref=order.customer_ref,
                        provider_reference=provider_reference,
                        granted_at=timestamp,
                    ),
                )
            except SubscriptionTopUpGrantError as exc:
                raise LemonSqueezyWebhookError(
                    "verified top-up payment could not be granted safely."
                ) from exc

            mark_lemon_squeezy_webhook_processed(inbox, processed_at=timestamp)
            await uow.commit()
            return LemonSqueezyTopUpProcessingResult(
                inbox_id=inbox.id,
                order_id=order.id,
                grant_id=grant.grant_id,
                units=grant.units,
                replayed_grant=grant.idempotent_replay,
            )

    return process


__all__ = [
    "TOP_UP_OFFER_REF",
    "LemonSqueezyTopUpProcessingResult",
    "process_lemon_squeezy_top_up_factory",
]
