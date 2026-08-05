from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from processual_api.admin_marketplace.audit_contracts import (
    CommercialAuditAction,
    CommercialAuditOutcome,
    CommercialAuditRecord,
    CommercialResourceType,
)
from processual_api.admin_marketplace.errors import (
    CommercialOrderNotFoundError,
    SubscriptionActivationConflictError,
    SubscriptionActivationNotReadyError,
)
from processual_api.admin_marketplace.models import (
    AdminMarketAuditRecord,
    AdminMarketEntitlementActivation,
    AdminMarketSubscription,
)
from processual_api.admin_marketplace.notification_outbox import enqueue_commercial_notification
from processual_api.admin_marketplace.persistence.errors import (
    AdminMarketplaceConflictError,
)
from processual_api.admin_marketplace.persistence.protocols import (
    AdminMarketplaceUnitOfWork,
)


@dataclass(frozen=True, slots=True)
class SubscriptionActivationResult:
    activation_id: uuid.UUID
    activation_ref: str
    subscription_id: uuid.UUID
    subscription_ref: str
    order_ref: str
    customer_ref: str
    entitlement_profile_ref: str
    status: str
    subscription_status: str
    order_status: str
    activated_at: datetime
    reason_code: str


class SubscriptionActivationOrchestrator:
    """Atomically activates one fully gated direct-order subscription."""

    def __init__(
        self,
        *,
        unit_of_work_factory: Callable[[], AdminMarketplaceUnitOfWork],
        clock: Callable[[], datetime],
        id_factory: Callable[[], uuid.UUID] = uuid.uuid4,
        reference_factory: Callable[[], uuid.UUID] = uuid.uuid4,
        event_id_factory: Callable[[], uuid.UUID] = uuid.uuid4,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock
        self._id_factory = id_factory
        self._reference_factory = reference_factory
        self._event_id_factory = event_id_factory

    async def activate_ready_order(
        self,
        *,
        order_ref: str,
        correlation_id: str,
        idempotency_key: str,
    ) -> SubscriptionActivationResult:
        order_ref = _required(order_ref, "order_ref").lower()
        correlation_id = _required(correlation_id, "correlation_id")
        idempotency_hash = _sha256(_required(idempotency_key, "idempotency_key"))
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("Subscription activation clock must be timezone-aware.")

        try:
            return await self._activate_once(
                order_ref=order_ref,
                correlation_id=correlation_id,
                idempotency_hash=idempotency_hash,
                now=now,
            )
        except AdminMarketplaceConflictError:
            replay = await self._replay(
                order_ref=order_ref,
                idempotency_hash=idempotency_hash,
            )
            if replay is None:
                raise
            return replay

    async def _activate_once(
        self,
        *,
        order_ref: str,
        correlation_id: str,
        idempotency_hash: str,
        now: datetime,
    ) -> SubscriptionActivationResult:
        async with self._unit_of_work_factory() as unit:
            order = await unit.orders.get_by_ref(order_ref, for_update=True)
            if order is None:
                raise CommercialOrderNotFoundError("Commercial order was not found.")

            key_replay = await unit.entitlement_activations.get_by_idempotency_key_hash(idempotency_hash)
            if key_replay is not None and key_replay.order_id != order.id:
                raise SubscriptionActivationConflictError("Activation idempotency key conflicts with another order.")

            existing = await unit.entitlement_activations.get_by_order_id(order.id, for_update=True)
            if existing is not None:
                subscription = await unit.subscriptions.get_by_id(existing.subscription_id)
                if subscription is None:
                    raise SubscriptionActivationConflictError("Activation references a missing subscription.")
                return _result(
                    activation=existing,
                    subscription=subscription,
                    order=order,
                    reason_code="subscription_already_activated",
                )

            _require_order_ready(order)
            contract = await unit.contracts.get_by_order_id(order.id, for_update=True)
            if contract is None or contract.status != "completed":
                raise SubscriptionActivationNotReadyError("completed_contract_required")
            if order.payment_requirement == "required":
                verification = await unit.payment_verifications.get_by_order_id(order.id, for_update=True)
                if verification is None or verification.status != "verified":
                    raise SubscriptionActivationNotReadyError("verified_payment_required")

            eligibility = await unit.channel_eligibilities.get_by_customer_ref(order.customer_ref, for_update=True)
            _require_automatic_eligibility(eligibility)

            active_subscription = await unit.subscriptions.get_active_by_customer_ref(
                order.customer_ref, for_update=True
            )
            if active_subscription is not None:
                raise SubscriptionActivationNotReadyError("active_subscription_conflict")

            offer = await unit.offers.get_by_id(order.offer_id, for_update=True)
            _require_offer_valid(offer=offer, order=order, now=now)
            plan = await unit.plans.get_by_id(order.plan_id, for_update=True)
            if plan is None or not plan.entitlement_profile_ref.strip():
                raise SubscriptionActivationNotReadyError("entitlement_profile_required")

            previous_digest = _digest(_activation_state(order, None, None))
            subscription_token = self._reference_factory().hex
            activation_token = self._reference_factory().hex
            subscription = AdminMarketSubscription(
                id=self._id_factory(),
                subscription_ref=f"sub_{subscription_token[:24]}",
                customer_ref=order.customer_ref,
                order_id=order.id,
                offer_id=order.offer_id,
                plan_id=order.plan_id,
                status="active",
                starts_at=now,
                ends_at=None,
                created_at=now,
                updated_at=now,
            )
            activation = AdminMarketEntitlementActivation(
                id=self._id_factory(),
                activation_ref=f"act_{activation_token[:24]}",
                customer_ref=order.customer_ref,
                order_id=order.id,
                subscription_id=subscription.id,
                entitlement_profile_ref=plan.entitlement_profile_ref,
                automatic_activation_allowed=True,
                status="activated",
                activation_idempotency_key_hash=idempotency_hash,
                activated_at=now,
                created_at=now,
            )
            order.status = "activated"
            order.completed_at = now
            order.updated_at = now
            unit.subscriptions.add(subscription)
            unit.entitlement_activations.add(activation)
            unit.commercial_audit.append(
                _activation_audit(
                    event_id=self._event_id_factory(),
                    occurred_at=now,
                    order=order,
                    subscription=subscription,
                    activation=activation,
                    correlation_id=correlation_id,
                    previous_digest=previous_digest,
                )
            )
            enqueue_commercial_notification(
                unit,
                event_type="subscription_activated",
                aggregate_type="order",
                aggregate_ref=order.order_ref,
                customer_ref=order.customer_ref,
                payload={
                    "order_ref": order.order_ref,
                    "subscription_ref": subscription.subscription_ref,
                    "activation_ref": activation.activation_ref,
                    "status": activation.status,
                },
                deduplication_material=activation.activation_idempotency_key_hash,
                occurred_at=now,
            )
            await unit.commit()
            return _result(
                activation=activation,
                subscription=subscription,
                order=order,
                reason_code="subscription_activated",
            )

    async def _replay(
        self,
        *,
        order_ref: str,
        idempotency_hash: str,
    ) -> SubscriptionActivationResult | None:
        async with self._unit_of_work_factory() as unit:
            order = await unit.orders.get_by_ref(order_ref)
            if order is None:
                return None
            activation = await unit.entitlement_activations.get_by_idempotency_key_hash(idempotency_hash)
            if activation is None:
                return None
            if activation.order_id != order.id:
                raise SubscriptionActivationConflictError("Activation idempotency key conflicts with another order.")
            subscription = await unit.subscriptions.get_by_id(activation.subscription_id)
        if subscription is None:
            return None
        return _result(
            activation=activation,
            subscription=subscription,
            order=order,
            reason_code="subscription_already_activated",
        )


def _require_order_ready(order) -> None:
    if order.status == "activated":
        raise SubscriptionActivationConflictError("Activated order is missing its activation record.")
    if order.status != "ready_for_activation":
        raise SubscriptionActivationNotReadyError("order_not_ready_for_activation")
    if order.selected_channel != "maestro_direct":
        raise SubscriptionActivationNotReadyError("direct_channel_required")
    if order.country_code != "TN" or order.currency != "TND":
        raise SubscriptionActivationNotReadyError("tunisian_direct_order_required")
    if order.contract_status != "completed":
        raise SubscriptionActivationNotReadyError("completed_contract_required")
    if order.payment_requirement == "required" and order.payment_status != "verified":
        raise SubscriptionActivationNotReadyError("verified_payment_required")
    if order.payment_requirement not in {"required", "not_required"}:
        raise SubscriptionActivationNotReadyError("invalid_payment_requirement")


def _require_automatic_eligibility(eligibility) -> None:
    if eligibility is None:
        raise SubscriptionActivationNotReadyError("channel_eligibility_required")
    if eligibility.address_status != "confirmed" or eligibility.country_code != "TN":
        raise SubscriptionActivationNotReadyError("confirmed_tunisian_address_required")
    if eligibility.maestro_direct_status != "eligible":
        raise SubscriptionActivationNotReadyError("maestro_direct_eligibility_required")
    if eligibility.admin_review_required:
        raise SubscriptionActivationNotReadyError("admin_review_blocks_activation")
    if not eligibility.automatic_activation_allowed:
        raise SubscriptionActivationNotReadyError("automatic_activation_not_allowed")


def _require_offer_valid(*, offer, order, now: datetime) -> None:
    if offer is None:
        raise SubscriptionActivationNotReadyError("offer_required")
    if (
        offer.id != order.offer_id
        or offer.plan_id != order.plan_id
        or offer.status != "published"
        or offer.sales_channel != "maestro_direct"
        or offer.currency != order.currency
        or offer.billing_period != order.billing_period
        or offer.amount != order.subtotal_amount
    ):
        raise SubscriptionActivationNotReadyError("offer_no_longer_valid")
    if offer.effective_at is not None and offer.effective_at > now:
        raise SubscriptionActivationNotReadyError("offer_not_yet_effective")
    if offer.expires_at is not None and offer.expires_at <= now:
        raise SubscriptionActivationNotReadyError("offer_expired")


def _activation_audit(
    *,
    event_id,
    occurred_at,
    order,
    subscription,
    activation,
    correlation_id,
    previous_digest,
) -> AdminMarketAuditRecord:
    record = CommercialAuditRecord(
        event_id=str(event_id),
        occurred_at=occurred_at,
        actor_user_id="system_subscription_activation",
        actor_session_id="system",
        platform_authority="system",
        action=CommercialAuditAction.SUBSCRIPTION_ACTIVATION_DECIDED,
        resource_type=CommercialResourceType.SUBSCRIPTION,
        resource_id=subscription.subscription_ref,
        outcome=CommercialAuditOutcome.ALLOWED,
        reason_code="subscription_activated",
        correlation_id=correlation_id,
        previous_state_digest=previous_digest,
        new_state_digest=_digest(_activation_state(order, subscription, activation)),
        metadata={
            "order_ref": order.order_ref,
            "subscription_ref": subscription.subscription_ref,
            "activation_ref": activation.activation_ref,
            "entitlement_profile_ref": activation.entitlement_profile_ref,
        },
    )
    return AdminMarketAuditRecord(
        id=uuid.UUID(record.event_id),
        event_ref=record.event_id,
        occurred_at=record.occurred_at,
        actor_user_id=record.actor_user_id,
        actor_session_id=record.actor_session_id,
        platform_authority=record.platform_authority,
        action=record.action.value,
        resource_type=record.resource_type.value,
        resource_id=record.resource_id,
        outcome=record.outcome.value,
        reason_code=record.reason_code,
        correlation_id=record.correlation_id,
        previous_state_digest=record.previous_state_digest,
        new_state_digest=record.new_state_digest,
        metadata_json=dict(record.metadata),
        created_at=record.occurred_at,
    )


def _result(*, activation, subscription, order, reason_code) -> SubscriptionActivationResult:
    return SubscriptionActivationResult(
        activation_id=activation.id,
        activation_ref=activation.activation_ref,
        subscription_id=subscription.id,
        subscription_ref=subscription.subscription_ref,
        order_ref=order.order_ref,
        customer_ref=order.customer_ref,
        entitlement_profile_ref=activation.entitlement_profile_ref,
        status=activation.status,
        subscription_status=subscription.status,
        order_status=order.status,
        activated_at=activation.activated_at or activation.created_at,
        reason_code=reason_code,
    )


def _activation_state(order, subscription, activation) -> dict[str, object]:
    return {
        "order_ref": order.order_ref,
        "order_status": order.status,
        "subscription_ref": None if subscription is None else subscription.subscription_ref,
        "subscription_status": None if subscription is None else subscription.status,
        "activation_ref": None if activation is None else activation.activation_ref,
        "activation_status": None if activation is None else activation.status,
    }


def _digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _required(value: str, field_name: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValueError(f"{field_name} is required.")
    return normalized


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


__all__ = [
    "SubscriptionActivationOrchestrator",
    "SubscriptionActivationResult",
]
