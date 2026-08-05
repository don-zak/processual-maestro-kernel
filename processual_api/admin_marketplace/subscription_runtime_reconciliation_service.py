from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Protocol

from processual_api.admin_marketplace.subscription_runtime import (
    SubscriptionRuntimeError,
    SubscriptionRuntimeState,
    transition_subscription_runtime,
)
from processual_api.admin_marketplace.subscription_runtime_transition_persistence import (
    AdminMarketSubscriptionRuntimeTransition,
)


class SubscriptionRuntimeReconciliationUnitOfWork(Protocol):
    lemon_squeezy_reconciliation_decisions: object
    subscription_runtime: object
    subscription_runtime_transitions: object

    async def __aenter__(self) -> "SubscriptionRuntimeReconciliationUnitOfWork": ...
    async def __aexit__(self, exc_type, exc, traceback) -> None: ...
    async def commit(self) -> None: ...


_TARGET_BY_EVENT = {
    "order_created": "active",
    "subscription_created": "active",
    "subscription_updated": "active",
    "subscription_resumed": "active",
    "subscription_unpaused": "active",
    "subscription_payment_success": "active",
    "subscription_payment_recovered": "active",
    "subscription_payment_failed": "grace",
    "subscription_paused": "suspended",
    "subscription_cancelled": "terminated",
    "subscription_expired": "terminated",
    "subscription_payment_refunded": "terminated",
    "order_refunded": "terminated",
}


def apply_reconciliation_to_runtime_factory(
    *,
    uow_factory: Callable[[], SubscriptionRuntimeReconciliationUnitOfWork],
    grace_days: int = 7,
):
    if grace_days < 1 or grace_days > 30:
        raise SubscriptionRuntimeError("grace period is outside allowed bounds.")

    async def apply(
        *,
        reconciliation_event_identity_hash: str,
        subscription_id: uuid.UUID,
        customer_ref: str,
        event_name: str,
        effective_at: datetime | None = None,
    ) -> AdminMarketSubscriptionRuntimeTransition:
        timestamp = effective_at or datetime.now(timezone.utc)
        if timestamp.tzinfo is None:
            raise SubscriptionRuntimeError("effective_at must be timezone-aware.")
        identity_hash = reconciliation_event_identity_hash.strip().lower()
        if len(identity_hash) != 64 or any(ch not in "0123456789abcdef" for ch in identity_hash):
            raise SubscriptionRuntimeError("reconciliation event identity hash is invalid.")
        normalized_event = event_name.strip().lower()
        target_stage = _TARGET_BY_EVENT.get(normalized_event)
        if target_stage is None:
            raise SubscriptionRuntimeError("event does not define a runtime transition.")

        async with uow_factory() as uow:
            decision = await uow.lemon_squeezy_reconciliation_decisions.get_by_event_identity_hash(
                identity_hash,
                for_update=True,
            )
            if decision is None:
                raise SubscriptionRuntimeError("reconciliation decision was not found.")

            existing = await uow.subscription_runtime_transitions.get_by_decision_id(
                decision.id,
                for_update=True,
            )
            if existing is not None:
                if (
                    existing.subscription_id != subscription_id
                    or existing.customer_ref != customer_ref
                    or existing.event_name != normalized_event
                    or existing.to_stage != target_stage
                ):
                    raise SubscriptionRuntimeError(
                        "runtime transition replay conflicts with the original binding."
                    )
                return existing

            if decision.action != "reconcile":
                raise SubscriptionRuntimeError("reconciliation decision is not executable.")
            if decision.customer_ref != customer_ref:
                raise SubscriptionRuntimeError("reconciliation customer binding mismatch.")

            runtime = await uow.subscription_runtime.get_by_subscription_id(
                subscription_id,
                for_update=True,
            )
            if runtime is None:
                raise SubscriptionRuntimeError("subscription runtime was not found.")
            if runtime.customer_ref != customer_ref:
                raise SubscriptionRuntimeError("subscription runtime customer mismatch.")

            from_stage = runtime.access_stage
            state = SubscriptionRuntimeState(
                subscription_id=runtime.subscription_id,
                customer_ref=runtime.customer_ref,
                entitlement_profile_ref=runtime.entitlement_profile_ref,
                quota_profile_ref=runtime.quota_profile_ref,
                access_stage=runtime.access_stage,
                version=runtime.version,
                effective_at=runtime.effective_at,
                grace_until=runtime.grace_until,
                suspended_at=runtime.suspended_at,
                terminated_at=runtime.terminated_at,
            )
            grace_until = timestamp + timedelta(days=grace_days) if target_stage == "grace" else None
            transition_subscription_runtime(
                state,
                target_stage=target_stage,
                effective_at=timestamp,
                grace_until=grace_until,
            )
            runtime.access_stage = state.access_stage
            runtime.version = state.version
            runtime.effective_at = state.effective_at
            runtime.grace_until = state.grace_until
            runtime.suspended_at = state.suspended_at
            runtime.terminated_at = state.terminated_at

            transition = AdminMarketSubscriptionRuntimeTransition(
                id=uuid.uuid4(),
                runtime_id=runtime.id,
                subscription_id=subscription_id,
                reconciliation_decision_id=decision.id,
                customer_ref=customer_ref,
                event_name=normalized_event,
                from_stage=from_stage,
                to_stage=target_stage,
                effective_at=timestamp,
            )
            uow.subscription_runtime_transitions.add(transition)
            await uow.commit()
            return transition

    return apply
