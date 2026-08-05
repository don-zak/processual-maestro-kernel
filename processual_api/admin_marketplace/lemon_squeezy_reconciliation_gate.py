from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from processual_api.admin_marketplace.lemon_squeezy_inbox import (
    LemonSqueezyWebhookInboxEntry,
)


ReconciliationAction = Literal["ignore", "reconcile", "requires_review"]


@dataclass(frozen=True, slots=True)
class LemonSqueezyReconciliationContext:
    expected_customer_ref: str
    expected_order_ref: str
    expected_offer_ref: str
    order_sales_channel: str
    offer_sales_channel: str
    production_mode: bool
    external_binding_matches: bool


@dataclass(frozen=True, slots=True)
class LemonSqueezyReconciliationDecision:
    action: ReconciliationAction
    reason_code: str


_RECONCILE_EVENTS = frozenset(
    {
        "order_created",
        "order_refunded",
        "subscription_created",
        "subscription_updated",
        "subscription_cancelled",
        "subscription_resumed",
        "subscription_expired",
        "subscription_paused",
        "subscription_unpaused",
        "subscription_payment_failed",
        "subscription_payment_success",
        "subscription_payment_recovered",
        "subscription_payment_refunded",
    }
)

_RESOURCE_TYPES_BY_EVENT = {
    "order_created": "orders",
    "order_refunded": "orders",
    "subscription_created": "subscriptions",
    "subscription_updated": "subscriptions",
    "subscription_cancelled": "subscriptions",
    "subscription_resumed": "subscriptions",
    "subscription_expired": "subscriptions",
    "subscription_paused": "subscriptions",
    "subscription_unpaused": "subscriptions",
    "subscription_payment_failed": "subscription-invoices",
    "subscription_payment_success": "subscription-invoices",
    "subscription_payment_recovered": "subscription-invoices",
    "subscription_payment_refunded": "subscription-invoices",
}


def classify_lemon_squeezy_reconciliation(
    *,
    entry: LemonSqueezyWebhookInboxEntry,
    context: LemonSqueezyReconciliationContext,
) -> LemonSqueezyReconciliationDecision:
    if entry.processing_status not in {"received", "processing"}:
        return LemonSqueezyReconciliationDecision(
            action="ignore",
            reason_code="event_already_terminal",
        )

    if entry.event_name not in _RECONCILE_EVENTS:
        return LemonSqueezyReconciliationDecision(
            action="requires_review",
            reason_code="unsupported_event",
        )

    expected_resource_type = _RESOURCE_TYPES_BY_EVENT[entry.event_name]
    if entry.resource_type != expected_resource_type:
        return LemonSqueezyReconciliationDecision(
            action="requires_review",
            reason_code="resource_type_mismatch",
        )

    if entry.customer_ref != context.expected_customer_ref:
        return LemonSqueezyReconciliationDecision(
            action="requires_review",
            reason_code="customer_binding_mismatch",
        )
    if entry.order_ref != context.expected_order_ref:
        return LemonSqueezyReconciliationDecision(
            action="requires_review",
            reason_code="order_binding_mismatch",
        )
    if entry.offer_ref != context.expected_offer_ref:
        return LemonSqueezyReconciliationDecision(
            action="requires_review",
            reason_code="offer_binding_mismatch",
        )

    if context.order_sales_channel != "lemon_squeezy":
        return LemonSqueezyReconciliationDecision(
            action="requires_review",
            reason_code="order_channel_mismatch",
        )
    if context.offer_sales_channel != "lemon_squeezy":
        return LemonSqueezyReconciliationDecision(
            action="requires_review",
            reason_code="offer_channel_mismatch",
        )

    if context.production_mode and entry.test_mode:
        return LemonSqueezyReconciliationDecision(
            action="ignore",
            reason_code="test_event_in_production",
        )
    if not context.production_mode and not entry.test_mode:
        return LemonSqueezyReconciliationDecision(
            action="requires_review",
            reason_code="live_event_in_test_environment",
        )

    if not context.external_binding_matches:
        return LemonSqueezyReconciliationDecision(
            action="requires_review",
            reason_code="external_binding_mismatch",
        )

    return LemonSqueezyReconciliationDecision(
        action="reconcile",
        reason_code="trusted_event_requires_reconciliation",
    )
