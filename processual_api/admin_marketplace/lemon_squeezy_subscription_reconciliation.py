from __future__ import annotations

from datetime import datetime

from processual_api.admin_marketplace.lemon_squeezy_webhooks import (
    LemonSqueezyWebhookError,
)

_EVENT_STATUS = {
    "subscription_created": "active",
    "subscription_updated": "active",
    "subscription_resumed": "active",
    "subscription_unpaused": "active",
    "subscription_payment_success": "active",
    "subscription_payment_recovered": "active",
    "subscription_paused": "suspended",
    "subscription_payment_failed": "suspended",
    "subscription_payment_refunded": "suspended",
    "subscription_cancelled": "cancelled",
    "subscription_expired": "expired",
}

_ALLOWED_SOURCE = {
    "active": frozenset({"pending", "active", "suspended"}),
    "suspended": frozenset({"pending", "active", "suspended"}),
    "cancelled": frozenset({"pending", "active", "suspended", "cancelled"}),
    "expired": frozenset({"pending", "active", "suspended", "expired"}),
}


async def apply_lemon_squeezy_subscription_lifecycle(
    *,
    uow: object,
    binding: object,
    inbox: object,
) -> object | None:
    target_status = _EVENT_STATUS.get(getattr(inbox, "event_name", ""))
    if target_status is None:
        return None

    subscription_id = getattr(binding, "subscription_id", None)
    if subscription_id is None:
        raise LemonSqueezyWebhookError(
            "authoritative binding has no internal subscription."
        )

    subscription = await uow.subscriptions.get_by_id(
        subscription_id,
        for_update=True,
    )
    if subscription is None:
        raise LemonSqueezyWebhookError("authoritative subscription was not found.")

    if (
        subscription.customer_ref != getattr(inbox, "customer_ref", None)
        or subscription.order_id != getattr(binding, "order_id", None)
        or subscription.offer_id != getattr(binding, "offer_id", None)
    ):
        raise LemonSqueezyWebhookError(
            "authoritative subscription conflicts with provider binding."
        )

    current_status = subscription.status
    if current_status not in _ALLOWED_SOURCE[target_status]:
        raise LemonSqueezyWebhookError(
            "provider lifecycle cannot transition the authoritative subscription."
        )

    effective_at = getattr(inbox, "provider_effective_at", None)
    if not isinstance(effective_at, datetime) or effective_at.tzinfo is None:
        raise LemonSqueezyWebhookError("provider lifecycle timestamp is invalid.")

    subscription.status = target_status
    if target_status == "active":
        if subscription.starts_at is None:
            subscription.starts_at = effective_at
        subscription.ends_at = None
    elif target_status in {"cancelled", "expired"}:
        subscription.ends_at = effective_at

    return subscription


__all__ = ["apply_lemon_squeezy_subscription_lifecycle"]
