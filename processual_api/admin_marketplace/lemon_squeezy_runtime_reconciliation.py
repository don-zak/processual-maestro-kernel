from __future__ import annotations

import uuid

from processual_api.admin_marketplace.lemon_squeezy_webhooks import (
    LemonSqueezyWebhookError,
)
from processual_api.admin_marketplace.subscription_runtime_transition_persistence import (
    AdminMarketSubscriptionRuntimeTransition,
)

_STATUS_STAGE = {
    "active": "active",
    "suspended": "suspended",
    "cancelled": "terminated",
    "expired": "terminated",
}


async def apply_lemon_squeezy_runtime_access(
    *,
    uow: object,
    binding: object,
    subscription: object,
    inbox: object,
    reconciliation_decision_id: uuid.UUID,
) -> None:
    target_stage = _STATUS_STAGE.get(getattr(subscription, "status", ""))
    if target_stage is None:
        return

    existing_transition = await uow.subscription_runtime_transitions.get_by_decision_id(
        reconciliation_decision_id,
        for_update=True,
    )
    if existing_transition is not None:
        return

    runtime = await uow.subscription_runtime.get_by_subscription_id(
        subscription.id,
        for_update=True,
    )
    if runtime is None:
        raise LemonSqueezyWebhookError("authoritative subscription runtime was not found.")

    if (
        runtime.customer_ref != subscription.customer_ref
        or runtime.subscription_id != subscription.id
        or subscription.id != getattr(binding, "subscription_id", None)
    ):
        raise LemonSqueezyWebhookError(
            "subscription runtime conflicts with authoritative binding."
        )

    effective_at = getattr(inbox, "provider_effective_at", None)
    if effective_at is None or effective_at.tzinfo is None:
        raise LemonSqueezyWebhookError("runtime transition timestamp is invalid.")
    if effective_at < runtime.effective_at:
        raise LemonSqueezyWebhookError("runtime transition is older than current state.")

    from_stage = runtime.access_stage
    if from_stage == "terminated" and target_stage != "terminated":
        raise LemonSqueezyWebhookError("terminated runtime cannot be reactivated.")

    if from_stage != target_stage:
        runtime.access_stage = target_stage
        runtime.effective_at = effective_at
        runtime.version += 1
        runtime.grace_until = None
        runtime.suspended_at = effective_at if target_stage == "suspended" else None
        runtime.terminated_at = effective_at if target_stage == "terminated" else None

    uow.subscription_runtime_transitions.add(
        AdminMarketSubscriptionRuntimeTransition(
            runtime_id=runtime.id,
            subscription_id=subscription.id,
            reconciliation_decision_id=reconciliation_decision_id,
            customer_ref=subscription.customer_ref,
            event_name=getattr(inbox, "event_name", "unknown"),
            from_stage=from_stage,
            to_stage=target_stage,
            effective_at=effective_at,
        )
    )


__all__ = ["apply_lemon_squeezy_runtime_access"]
