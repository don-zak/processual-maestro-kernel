from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from processual_api.admin_marketplace.audit_contracts import (
    CommercialAuditAction,
    CommercialAuditOutcome,
    CommercialAuditRecord,
    CommercialResourceType,
)
from processual_api.admin_marketplace.models import AdminMarketAuditRecord, AdminMarketOrder
from processual_api.admin_marketplace.notification_outbox import enqueue_commercial_notification
from processual_api.admin_marketplace.persistence.errors import AdminMarketplaceConflictError
from processual_api.admin_marketplace.persistence.protocols import AdminMarketplaceUnitOfWork


class LemonCheckoutOrderAuthorityError(ValueError):
    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__("Lemon Squeezy checkout order is not authorized.")


@dataclass(frozen=True, slots=True)
class LemonCheckoutOrderResult:
    order_id: uuid.UUID
    order_ref: str
    customer_ref: str
    offer_ref: str
    country_code: str
    currency: str
    status: str
    replayed: bool


class LemonCheckoutOrderAuthority:
    """Create a durable internal order before any Lemon Squeezy checkout call."""

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

    async def prepare(
        self,
        *,
        actor_user_id: str,
        actor_session_id: str,
        customer_ref: str,
        offer_id: uuid.UUID,
        offer_ref: str,
        plan_id: uuid.UUID,
        billing_period: str,
        currency: str,
        amount: Decimal,
        display_name: str,
        correlation_id: str,
        idempotency_key: str,
    ) -> LemonCheckoutOrderResult:
        actor_user_id = _required(actor_user_id, "actor_user_id")
        actor_session_id = _required(actor_session_id, "actor_session_id")
        customer_ref = _required(customer_ref, "customer_ref")
        offer_ref = _required(offer_ref, "offer_ref").lower()
        billing_period = _required(billing_period, "billing_period").lower()
        currency = _required(currency, "currency").upper()
        display_name = _required(display_name, "display_name")
        correlation_id = _required(correlation_id, "correlation_id")
        if billing_period not in {"monthly", "annual"}:
            raise LemonCheckoutOrderAuthorityError("invalid_billing_period")
        if len(currency) != 3:
            raise LemonCheckoutOrderAuthorityError("invalid_currency")
        normalized_amount = Decimal(amount).quantize(Decimal("0.001"))
        if not normalized_amount.is_finite() or normalized_amount < 0:
            raise LemonCheckoutOrderAuthorityError("invalid_amount")
        key_hash = _idempotency_hash(idempotency_key)
        now = self._clock()
        if now.tzinfo is None:
            raise LemonCheckoutOrderAuthorityError("timezone_aware_clock_required")

        try:
            return await self._prepare_once(
                actor_user_id=actor_user_id,
                actor_session_id=actor_session_id,
                customer_ref=customer_ref,
                offer_id=offer_id,
                offer_ref=offer_ref,
                plan_id=plan_id,
                billing_period=billing_period,
                currency=currency,
                amount=normalized_amount,
                display_name=display_name,
                correlation_id=correlation_id,
                key_hash=key_hash,
                now=now,
            )
        except AdminMarketplaceConflictError:
            async with self._unit_of_work_factory() as unit:
                existing = await unit.orders.get_by_creation_idempotency_key_hash(key_hash)
            if existing is None:
                raise
            _require_same_request(
                existing,
                customer_ref=customer_ref,
                offer_id=offer_id,
                offer_ref=offer_ref,
            )
            return _result(existing, offer_ref=offer_ref, replayed=True)

    async def _prepare_once(
        self,
        *,
        actor_user_id: str,
        actor_session_id: str,
        customer_ref: str,
        offer_id: uuid.UUID,
        offer_ref: str,
        plan_id: uuid.UUID,
        billing_period: str,
        currency: str,
        amount: Decimal,
        display_name: str,
        correlation_id: str,
        key_hash: str,
        now: datetime,
    ) -> LemonCheckoutOrderResult:
        async with self._unit_of_work_factory() as unit:
            existing = await unit.orders.get_by_creation_idempotency_key_hash(
                key_hash,
                for_update=True,
            )
            if existing is not None:
                _require_same_request(
                    existing,
                    customer_ref=customer_ref,
                    offer_id=offer_id,
                    offer_ref=offer_ref,
                )
                return _result(existing, offer_ref=offer_ref, replayed=True)

            eligibility = await unit.channel_eligibilities.get_by_customer_ref(
                customer_ref,
                for_update=True,
            )
            if eligibility is None:
                raise LemonCheckoutOrderAuthorityError("trusted_customer_eligibility_required")
            if str(eligibility.lemon_squeezy_status).strip().lower() != "eligible":
                raise LemonCheckoutOrderAuthorityError("lemon_squeezy_customer_ineligible")
            if bool(eligibility.admin_review_required):
                raise LemonCheckoutOrderAuthorityError("lemon_squeezy_admin_review_required")
            country_code = str(eligibility.country_code or "").strip().upper()
            if len(country_code) != 2:
                raise LemonCheckoutOrderAuthorityError("trusted_customer_country_required")

            order = AdminMarketOrder(
                id=self._id_factory(),
                order_ref=f"ord_{self._reference_factory().hex[:24]}",
                customer_ref=customer_ref,
                offer_id=offer_id,
                plan_id=plan_id,
                billing_period=billing_period,
                selected_channel="lemon_squeezy",
                country_code=country_code,
                currency=currency,
                subtotal_amount=amount,
                tax_amount=Decimal("0.000"),
                total_amount=amount,
                status="awaiting_payment",
                contract_status="not_required",
                payment_requirement="required",
                payment_status="pending",
                payment_reference=None,
                payment_destination_snapshot={},
                offer_snapshot={
                    "offer_ref": offer_ref,
                    "display_name": display_name,
                    "billing_period": billing_period,
                    "currency": currency,
                    "amount": str(amount),
                    "sales_channel": "lemon_squeezy",
                    "contract_required": False,
                    "snapshot_at": now.isoformat(),
                },
                creation_idempotency_key_hash=key_hash,
                created_at=now,
                updated_at=now,
            )
            unit.orders.add(order)
            unit.commercial_audit.append(
                _audit_record(
                    order=order,
                    actor_user_id=actor_user_id,
                    actor_session_id=actor_session_id,
                    correlation_id=correlation_id,
                    occurred_at=now,
                    event_id=self._event_id_factory(),
                )
            )
            enqueue_commercial_notification(
                unit,
                event_type="order_created",
                aggregate_type="order",
                aggregate_ref=order.order_ref,
                customer_ref=customer_ref,
                payload={
                    "order_ref": order.order_ref,
                    "status": order.status,
                    "currency": order.currency,
                },
                deduplication_material=key_hash,
                occurred_at=now,
            )
            await unit.commit()
            return _result(order, offer_ref=offer_ref, replayed=False)


def _required(value: str, field_name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise LemonCheckoutOrderAuthorityError(f"{field_name}_required")
    return normalized


def _idempotency_hash(value: str) -> str:
    normalized = str(value or "").strip()
    if len(normalized) < 16 or len(normalized) > 128:
        raise LemonCheckoutOrderAuthorityError("idempotency_key_invalid")
    material = f"lemon_squeezy_checkout:{normalized}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _require_same_request(
    order: AdminMarketOrder,
    *,
    customer_ref: str,
    offer_id: uuid.UUID,
    offer_ref: str,
) -> None:
    if (
        order.customer_ref != customer_ref
        or order.offer_id != offer_id
        or order.selected_channel != "lemon_squeezy"
        or str(order.offer_snapshot.get("offer_ref", "")).strip().lower() != offer_ref
    ):
        raise LemonCheckoutOrderAuthorityError("idempotency_key_request_mismatch")
    if order.status in {"cancelled", "expired", "requires_review"}:
        raise LemonCheckoutOrderAuthorityError("checkout_order_not_eligible")


def _result(
    order: AdminMarketOrder,
    *,
    offer_ref: str,
    replayed: bool,
) -> LemonCheckoutOrderResult:
    return LemonCheckoutOrderResult(
        order_id=order.id,
        order_ref=order.order_ref,
        customer_ref=order.customer_ref,
        offer_ref=offer_ref,
        country_code=order.country_code,
        currency=order.currency,
        status=order.status,
        replayed=replayed,
    )


def _audit_record(
    *,
    order: AdminMarketOrder,
    actor_user_id: str,
    actor_session_id: str,
    correlation_id: str,
    occurred_at: datetime,
    event_id: uuid.UUID,
) -> AdminMarketAuditRecord:
    state = {
        "order_ref": order.order_ref,
        "customer_ref": order.customer_ref,
        "offer_id": str(order.offer_id),
        "plan_id": str(order.plan_id),
        "billing_period": order.billing_period,
        "sales_channel": order.selected_channel,
        "country_code": order.country_code,
        "currency": order.currency,
        "total_amount": str(order.total_amount),
        "status": order.status,
        "contract_status": order.contract_status,
        "payment_status": order.payment_status,
    }
    digest = hashlib.sha256(
        json.dumps(state, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    record = CommercialAuditRecord(
        event_id=str(event_id),
        occurred_at=occurred_at,
        actor_user_id=actor_user_id,
        actor_session_id=actor_session_id,
        platform_authority="identity_customer",
        action=CommercialAuditAction.ORDER_CREATED,
        resource_type=CommercialResourceType.ORDER,
        resource_id=order.order_ref,
        outcome=CommercialAuditOutcome.ALLOWED,
        reason_code="lemon_squeezy_checkout_order_created",
        correlation_id=correlation_id,
        new_state_digest=digest,
        metadata={
            "billing_period": order.billing_period,
            "sales_channel": "lemon_squeezy",
        },
    )
    return AdminMarketAuditRecord(
        id=event_id,
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


__all__ = [
    "LemonCheckoutOrderAuthority",
    "LemonCheckoutOrderAuthorityError",
    "LemonCheckoutOrderResult",
]
