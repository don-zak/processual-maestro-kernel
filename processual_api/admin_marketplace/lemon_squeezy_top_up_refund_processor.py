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
from processual_api.admin_marketplace.lemon_squeezy_top_up_processor import TOP_UP_OFFER_REF
from processual_api.admin_marketplace.lemon_squeezy_webhooks import LemonSqueezyWebhookError
from processual_api.admin_marketplace.subscription_top_up_reversal import (
    ReverseSubscriptionTopUpCommand,
    SubscriptionTopUpReversalError,
    reverse_subscription_top_up_in_uow,
)


@dataclass(frozen=True, slots=True)
class LemonSqueezyTopUpRefundResult:
    inbox_id: uuid.UUID
    order_id: uuid.UUID
    outcome: str
    reversal_id: uuid.UUID | None
    replayed: bool


def _amount_from_cents(value: object, *, field_name: str) -> Decimal:
    try:
        cents = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise LemonSqueezyWebhookError(f"{field_name} is invalid.") from exc
    if not cents.is_finite() or cents < 0 or cents != cents.to_integral_value():
        raise LemonSqueezyWebhookError(f"{field_name} is invalid.")
    return cents / Decimal(100)


def process_lemon_squeezy_top_up_refund_factory(
    *,
    uow_factory: Callable[[], object],
):
    async def process(
        *,
        inbox_id: uuid.UUID,
        processed_at: datetime | None = None,
    ) -> LemonSqueezyTopUpRefundResult:
        timestamp = processed_at or datetime.now(UTC)
        if timestamp.tzinfo is None:
            raise LemonSqueezyWebhookError("processed_at must be timezone-aware.")

        async with uow_factory() as uow:
            inbox = await uow.lemon_squeezy_webhook_inbox.get_by_id(
                inbox_id,
                for_update=True,
            )
            if inbox is None:
                raise LemonSqueezyWebhookError("top-up refund webhook inbox entry was not found.")
            try:
                order_id = uuid.UUID(inbox.order_ref)
            except (ValueError, AttributeError) as exc:
                raise LemonSqueezyWebhookError("top-up refund order_ref must be a UUID.") from exc

            if inbox.processing_status == "processed":
                event_ref = _provider_event_ref(inbox)
                reversal = await uow.subscription_top_up_reversals.get_by_provider_event_ref(
                    event_ref,
                    for_update=True,
                )
                outcome = "reversed" if reversal is not None else "manual_review"
                return LemonSqueezyTopUpRefundResult(
                    inbox_id=inbox.id,
                    order_id=order_id,
                    outcome=outcome,
                    reversal_id=None if reversal is None else reversal.id,
                    replayed=True,
                )

            if inbox.offer_ref != TOP_UP_OFFER_REF:
                raise LemonSqueezyWebhookError("webhook is not a top-up refund event.")
            if inbox.event_name != "order_refunded" or inbox.resource_type != "orders":
                raise LemonSqueezyWebhookError(
                    "top-up refund processing requires a Lemon Squeezy order_refunded event."
                )
            if inbox.provider_order_id is None or inbox.provider_order_id != inbox.external_resource_id:
                raise LemonSqueezyWebhookError("top-up refund provider order binding is invalid.")
            if inbox.provider_subscription_id is not None:
                raise LemonSqueezyWebhookError("top-up refund must not be bound to a subscription.")
            if inbox.currency != "USD" or inbox.refunded_amount is None or inbox.total_amount is None:
                raise LemonSqueezyWebhookError("top-up refund evidence is incomplete.")

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
                    "top-up refund conflicts with the authoritative order binding."
                )

            refunded_amount = _amount_from_cents(
                inbox.refunded_amount,
                field_name="top-up refunded amount",
            )
            total_amount = _amount_from_cents(
                inbox.total_amount,
                field_name="top-up total amount",
            )
            if refunded_amount <= 0 or refunded_amount > total_amount:
                raise LemonSqueezyWebhookError("top-up refund amount is invalid.")

            claim_lemon_squeezy_webhook(inbox, claimed_at=timestamp)

            is_full_refund = inbox.provider_status == "refunded" and refunded_amount == total_amount
            is_partial_refund = inbox.provider_status == "partial_refund" and refunded_amount < total_amount
            if is_partial_refund:
                mark_lemon_squeezy_webhook_processed(inbox, processed_at=timestamp)
                await uow.commit()
                return LemonSqueezyTopUpRefundResult(
                    inbox_id=inbox.id,
                    order_id=order.id,
                    outcome="manual_review",
                    reversal_id=None,
                    replayed=False,
                )
            if not is_full_refund:
                raise LemonSqueezyWebhookError(
                    "top-up refund status conflicts with refunded amount evidence."
                )

            try:
                reversal = await reverse_subscription_top_up_in_uow(
                    uow=uow,
                    command=ReverseSubscriptionTopUpCommand(
                        order_id=order.id,
                        provider_event_ref=_provider_event_ref(inbox),
                        reason_code="provider_full_refund",
                        reversed_at=timestamp,
                    ),
                )
            except SubscriptionTopUpReversalError as exc:
                raise LemonSqueezyWebhookError(
                    "top-up refund could not be reconciled safely."
                ) from exc

            mark_lemon_squeezy_webhook_processed(inbox, processed_at=timestamp)
            await uow.commit()
            return LemonSqueezyTopUpRefundResult(
                inbox_id=inbox.id,
                order_id=order.id,
                outcome=reversal.outcome,
                reversal_id=reversal.reversal_id,
                replayed=reversal.idempotent_replay,
            )

    return process


def _provider_event_ref(inbox: object) -> str:
    return f"lemon_squeezy:order_refunded:{inbox.external_resource_id}:{inbox.payload_digest}"


__all__ = [
    "LemonSqueezyTopUpRefundResult",
    "process_lemon_squeezy_top_up_refund_factory",
]
