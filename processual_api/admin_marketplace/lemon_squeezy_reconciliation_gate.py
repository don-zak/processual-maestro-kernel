from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
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
    expected_provider_customer_id: str
    expected_provider_order_id: str | None = None
    expected_provider_subscription_id: str | None = None
    expected_variant_id: str | None = None
    expected_currency: str | None = None
    expected_total_amount: str | None = None
    latest_provider_effective_at: datetime | None = None


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

_EVIDENCE_SCHEMA_BY_RESOURCE = {
    "orders": 3,
    "subscriptions": 1,
    "subscription-invoices": 1,
}


def _review(reason_code: str) -> LemonSqueezyReconciliationDecision:
    return LemonSqueezyReconciliationDecision(
        action="requires_review",
        reason_code=reason_code,
    )


def _amounts_equal(left: str, right: str) -> bool:
    try:
        return Decimal(left) == Decimal(right)
    except (InvalidOperation, ValueError):
        return False


def _is_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


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
        return _review("unsupported_event")

    expected_resource_type = _RESOURCE_TYPES_BY_EVENT[entry.event_name]
    if entry.resource_type != expected_resource_type:
        return _review("resource_type_mismatch")

    if entry.customer_ref != context.expected_customer_ref:
        return _review("customer_binding_mismatch")
    if entry.order_ref != context.expected_order_ref:
        return _review("order_binding_mismatch")
    if entry.offer_ref != context.expected_offer_ref:
        return _review("offer_binding_mismatch")

    if context.order_sales_channel != "lemon_squeezy":
        return _review("order_channel_mismatch")
    if context.offer_sales_channel != "lemon_squeezy":
        return _review("offer_channel_mismatch")

    if context.production_mode and entry.test_mode:
        return LemonSqueezyReconciliationDecision(
            action="ignore",
            reason_code="test_event_in_production",
        )
    if not context.production_mode and not entry.test_mode:
        return _review("live_event_in_test_environment")

    expected_schema = _EVIDENCE_SCHEMA_BY_RESOURCE.get(entry.resource_type)
    if expected_schema is None or entry.evidence_schema_version != expected_schema:
        return _review("verified_evidence_missing")
    if entry.provider_effective_at is None or not _is_aware(entry.provider_effective_at):
        return _review("provider_effective_at_invalid")
    if context.latest_provider_effective_at is not None:
        if not _is_aware(context.latest_provider_effective_at):
            return _review("latest_provider_effective_at_invalid")
        if entry.provider_effective_at < context.latest_provider_effective_at:
            return _review("stale_provider_event")

    if entry.provider_customer_id != context.expected_provider_customer_id:
        return _review("provider_customer_mismatch")

    if (
        context.expected_provider_order_id is not None
        and entry.provider_order_id != context.expected_provider_order_id
    ):
        return _review("provider_order_mismatch")
    if (
        context.expected_provider_subscription_id is not None
        and entry.provider_subscription_id
        != context.expected_provider_subscription_id
    ):
        return _review("provider_subscription_mismatch")
    if (
        context.expected_variant_id is not None
        and entry.variant_id != context.expected_variant_id
    ):
        return _review("variant_mismatch")
    if (
        context.expected_currency is not None
        and entry.currency != context.expected_currency.upper()
    ):
        return _review("currency_mismatch")
    if context.expected_total_amount is not None and (
        entry.total_amount is None
        or not _amounts_equal(entry.total_amount, context.expected_total_amount)
    ):
        return _review("total_amount_mismatch")

    if entry.resource_type == "orders":
        if entry.provider_order_id != entry.external_resource_id:
            return _review("resource_provider_order_mismatch")
        if entry.variant_id is None or entry.currency is None or entry.total_amount is None:
            return _review("order_evidence_incomplete")
    elif entry.resource_type == "subscriptions":
        if entry.provider_subscription_id != entry.external_resource_id:
            return _review("resource_provider_subscription_mismatch")
        if entry.provider_order_id is None or entry.variant_id is None:
            return _review("subscription_evidence_incomplete")
    elif entry.resource_type == "subscription-invoices":
        if (
            entry.provider_subscription_id is None
            or entry.currency is None
            or entry.total_amount is None
        ):
            return _review("invoice_evidence_incomplete")

    return LemonSqueezyReconciliationDecision(
        action="reconcile",
        reason_code="verified_evidence_requires_reconciliation",
    )
