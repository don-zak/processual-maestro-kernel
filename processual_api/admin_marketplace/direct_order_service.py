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
from processual_api.admin_marketplace.errors import (
    DirectCommerceConflictError,
    DirectCommerceUnavailableError,
)
from processual_api.admin_marketplace.models import (
    AdminMarketAuditRecord,
    AdminMarketOrder,
)
from processual_api.admin_marketplace.persistence.errors import (
    AdminMarketplaceConflictError,
)
from processual_api.admin_marketplace.persistence.protocols import (
    AdminMarketplaceUnitOfWork,
)

TUNISIA_DIRECT_CONTRACT_VERSION = "tn-direct-v1"


@dataclass(frozen=True, slots=True)
class TunisiaPaymentOptionResult:
    visible: bool
    reason_code: str
    address_status: str | None
    country_code: str | None
    sales_channel: str | None
    currency: str | None
    offer_ref: str | None
    offer_display_name: str | None
    billing_period: str | None
    amount: Decimal | None


@dataclass(frozen=True, slots=True)
class DirectCommercialOrderResult:
    order_id: uuid.UUID
    order_ref: str
    customer_ref: str
    offer_ref: str
    plan_ref: str
    billing_period: str
    sales_channel: str
    country_code: str
    currency: str
    subtotal_amount: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    status: str
    contract_status: str
    contract_version: str
    payment_requirement: str
    payment_status: str
    payment_reference: str | None
    payment_destination_snapshot: dict[str, object]
    created_at: datetime
    updated_at: datetime
    reason_code: str


class TunisiaDirectOrderService:
    """Fail-closed Tunisian payment choice and idempotent order creation."""

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

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("Direct-commerce clock must be timezone-aware.")
        return now

    async def evaluate_payment_option(
        self,
        *,
        customer_ref: str,
        plan_ref: str,
        billing_period: str,
    ) -> TunisiaPaymentOptionResult:
        customer_ref, plan_ref, billing_period = _inputs(
            customer_ref=customer_ref,
            plan_ref=plan_ref,
            billing_period=billing_period,
        )
        now = self._now()
        async with self._unit_of_work_factory() as unit:
            eligibility = await unit.channel_eligibilities.get_by_customer_ref(
                customer_ref
            )
            unavailable = _eligibility_failure(eligibility)
            if unavailable is not None:
                return unavailable

            offer = await unit.offers.get_published_direct_for_plan_code(
                plan_code=plan_ref,
                billing_period=billing_period,
                now=now,
            )
            if offer is None:
                return _unavailable(
                    "published_tnd_direct_offer_required",
                    eligibility,
                )

            destination = await unit.payment_destinations.get_active_default()
            if destination is None:
                return _unavailable(
                    "active_default_payment_destination_required",
                    eligibility,
                )

        return TunisiaPaymentOptionResult(
            visible=True,
            reason_code="tunisian_direct_payment_available",
            address_status="confirmed",
            country_code="TN",
            sales_channel="maestro_direct",
            currency="TND",
            offer_ref=offer.offer_code,
            offer_display_name=offer.display_name,
            billing_period=billing_period,
            amount=Decimal(offer.amount),
        )

    async def create_order(
        self,
        *,
        actor_user_id: str,
        actor_session_id: str,
        customer_ref: str,
        plan_ref: str,
        billing_period: str,
        correlation_id: str,
        idempotency_key: str,
    ) -> DirectCommercialOrderResult:
        customer_ref, plan_ref, billing_period = _inputs(
            customer_ref=customer_ref,
            plan_ref=plan_ref,
            billing_period=billing_period,
        )
        actor_user_id = _required(actor_user_id, "actor_user_id")
        actor_session_id = _required(actor_session_id, "actor_session_id")
        correlation_id = _required(correlation_id, "correlation_id")
        idempotency_hash = _idempotency_hash(idempotency_key)
        now = self._now()

        try:
            return await self._create_order_once(
                actor_user_id=actor_user_id,
                actor_session_id=actor_session_id,
                customer_ref=customer_ref,
                plan_ref=plan_ref,
                billing_period=billing_period,
                correlation_id=correlation_id,
                idempotency_hash=idempotency_hash,
                now=now,
            )
        except AdminMarketplaceConflictError:
            # A concurrent request may win the unique idempotency-key insert.
            # Read it in a fresh transaction and return only if the request is
            # identical; other persistence conflicts remain failures.
            async with self._unit_of_work_factory() as unit:
                existing = await unit.orders.get_by_creation_idempotency_key_hash(
                    idempotency_hash,
                    for_update=False,
                )
            if existing is None:
                raise
            _require_same_request(
                existing,
                customer_ref=customer_ref,
                plan_ref=plan_ref,
                billing_period=billing_period,
            )
            return _order_result(existing, "commercial_order_create_idempotent")

    async def _create_order_once(
        self,
        *,
        actor_user_id: str,
        actor_session_id: str,
        customer_ref: str,
        plan_ref: str,
        billing_period: str,
        correlation_id: str,
        idempotency_hash: str,
        now: datetime,
    ) -> DirectCommercialOrderResult:

        async with self._unit_of_work_factory() as unit:
            existing = await unit.orders.get_by_creation_idempotency_key_hash(
                idempotency_hash,
                for_update=True,
            )
            if existing is not None:
                _require_same_request(
                    existing,
                    customer_ref=customer_ref,
                    plan_ref=plan_ref,
                    billing_period=billing_period,
                )
                return _order_result(existing, "commercial_order_create_idempotent")

            eligibility = await unit.channel_eligibilities.get_by_customer_ref(
                customer_ref,
                for_update=True,
            )
            failure = _eligibility_failure(eligibility)
            if failure is not None:
                raise DirectCommerceUnavailableError(failure.reason_code)

            offer = await unit.offers.get_published_direct_for_plan_code(
                plan_code=plan_ref,
                billing_period=billing_period,
                now=now,
                for_update=True,
            )
            if offer is None:
                raise DirectCommerceUnavailableError(
                    "published_tnd_direct_offer_required"
                )

            destination = await unit.payment_destinations.get_active_default(
                for_update=True,
            )
            if destination is None:
                raise DirectCommerceUnavailableError(
                    "active_default_payment_destination_required"
                )

            order = self._build_order(
                customer_ref=customer_ref,
                plan_ref=plan_ref,
                billing_period=billing_period,
                offer=offer,
                destination=destination,
                idempotency_hash=idempotency_hash,
                now=now,
            )
            unit.orders.add(order)
            unit.commercial_audit.append(
                self._audit(
                    order=order,
                    actor_user_id=actor_user_id,
                    actor_session_id=actor_session_id,
                    correlation_id=correlation_id,
                    occurred_at=now,
                )
            )
            await unit.commit()
            return _order_result(order, "commercial_order_created")

    def _build_order(
        self,
        *,
        customer_ref: str,
        plan_ref: str,
        billing_period: str,
        offer,
        destination,
        idempotency_hash: str,
        now: datetime,
    ) -> AdminMarketOrder:
        amount = Decimal(offer.amount).quantize(Decimal("0.001"))
        order_token = self._reference_factory().hex
        destination_snapshot = {
            "destination_ref": destination.destination_ref,
            "display_name": destination.display_name,
            "destination_type": destination.destination_type,
            "institution_name": destination.institution_name,
            "account_holder_name": destination.account_holder_name,
            "masked_identifier": destination.masked_identifier,
            "instructions": destination.instructions,
            "country_code": "TN",
            "currency": "TND",
            "sales_channel": "maestro_direct",
            "snapshot_at": now.isoformat(),
        }
        offer_snapshot = {
            "offer_ref": offer.offer_code,
            "plan_ref": plan_ref,
            "display_name": offer.display_name,
            "billing_period": billing_period,
            "currency": "TND",
            "amount": str(amount),
            "sales_channel": "maestro_direct",
            "contract_required": True,
            "contract_version": TUNISIA_DIRECT_CONTRACT_VERSION,
            "snapshot_at": now.isoformat(),
        }
        return AdminMarketOrder(
            id=self._id_factory(),
            order_ref=f"ord_{order_token[:24]}",
            customer_ref=customer_ref,
            offer_id=offer.id,
            plan_id=offer.plan_id,
            billing_period=billing_period,
            selected_channel="maestro_direct",
            country_code="TN",
            currency="TND",
            subtotal_amount=amount,
            tax_amount=Decimal("0.000"),
            total_amount=amount,
            status="awaiting_contract",
            contract_status="pending",
            payment_requirement="required",
            payment_status="pending",
            payment_reference=f"TN-{order_token[24:36].upper()}",
            payment_destination_snapshot=destination_snapshot,
            offer_snapshot=offer_snapshot,
            creation_idempotency_key_hash=idempotency_hash,
            created_at=now,
            updated_at=now,
        )

    def _audit(
        self,
        *,
        order: AdminMarketOrder,
        actor_user_id: str,
        actor_session_id: str,
        correlation_id: str,
        occurred_at: datetime,
    ) -> AdminMarketAuditRecord:
        record = CommercialAuditRecord(
            event_id=str(self._event_id_factory()),
            occurred_at=occurred_at,
            actor_user_id=actor_user_id,
            actor_session_id=actor_session_id,
            platform_authority="identity_customer",
            action=CommercialAuditAction.ORDER_CREATED,
            resource_type=CommercialResourceType.ORDER,
            resource_id=order.order_ref,
            outcome=CommercialAuditOutcome.ALLOWED,
            reason_code="commercial_order_created",
            correlation_id=correlation_id,
            new_state_digest=_digest(_order_state(order)),
            metadata={
                "plan_ref": str(order.offer_snapshot["plan_ref"]),
                "billing_period": order.billing_period,
                "sales_channel": order.selected_channel,
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


def _required(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} is required.")
    return normalized


def _inputs(
    *,
    customer_ref: str,
    plan_ref: str,
    billing_period: str,
) -> tuple[str, str, str]:
    customer = _required(customer_ref, "customer_ref")
    plan = _required(plan_ref, "plan_ref").lower()
    period = _required(billing_period, "billing_period").lower()
    if period not in {"monthly", "annual"}:
        raise ValueError("billing_period is invalid.")
    return customer, plan, period


def _eligibility_failure(eligibility) -> TunisiaPaymentOptionResult | None:
    if eligibility is None:
        return _unavailable("trusted_customer_eligibility_required", None)
    address_status = str(
        getattr(eligibility, "address_status", "unverified")
    ).strip().lower()
    country_code = (
        eligibility.country_code.strip().upper()
        if eligibility.country_code is not None
        else None
    )
    if address_status != "confirmed":
        return _unavailable("confirmed_customer_address_required", eligibility)
    if country_code != "TN":
        return _unavailable("tunisian_customer_address_required", eligibility)
    if eligibility.maestro_direct_status.strip().lower() != "eligible":
        return _unavailable("maestro_direct_customer_ineligible", eligibility)
    if bool(eligibility.admin_review_required):
        return _unavailable("maestro_direct_admin_review_required", eligibility)
    return None


def _unavailable(reason_code: str, eligibility) -> TunisiaPaymentOptionResult:
    return TunisiaPaymentOptionResult(
        visible=False,
        reason_code=reason_code,
        address_status=(
            None
            if eligibility is None
            else str(getattr(eligibility, "address_status", "unverified"))
        ),
        country_code=(None if eligibility is None else eligibility.country_code),
        sales_channel=None,
        currency=None,
        offer_ref=None,
        offer_display_name=None,
        billing_period=None,
        amount=None,
    )


def _idempotency_hash(value: str) -> str:
    normalized = value.strip()
    if len(normalized) < 16 or len(normalized) > 128:
        raise ValueError("idempotency_key is invalid.")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _require_same_request(
    order: AdminMarketOrder,
    *,
    customer_ref: str,
    plan_ref: str,
    billing_period: str,
) -> None:
    if (
        order.customer_ref != customer_ref
        or order.billing_period != billing_period
        or str(order.offer_snapshot.get("plan_ref", "")) != plan_ref
        or order.selected_channel != "maestro_direct"
    ):
        raise DirectCommerceConflictError(
            "Idempotency key belongs to another commercial order request."
        )


def _order_state(order: AdminMarketOrder) -> dict[str, object]:
    return {
        "order_ref": order.order_ref,
        "customer_ref": order.customer_ref,
        "offer_id": str(order.offer_id),
        "plan_id": str(order.plan_id),
        "billing_period": order.billing_period,
        "sales_channel": order.selected_channel,
        "country_code": order.country_code,
        "currency": order.currency,
        "subtotal_amount": str(order.subtotal_amount),
        "tax_amount": str(order.tax_amount),
        "total_amount": str(order.total_amount),
        "status": order.status,
        "contract_status": order.contract_status,
        "payment_requirement": order.payment_requirement,
        "payment_status": order.payment_status,
        "payment_reference": order.payment_reference,
    }


def _digest(value: dict[str, object]) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _order_result(
    order: AdminMarketOrder,
    reason_code: str,
) -> DirectCommercialOrderResult:
    return DirectCommercialOrderResult(
        order_id=order.id,
        order_ref=order.order_ref,
        customer_ref=order.customer_ref,
        offer_ref=str(order.offer_snapshot["offer_ref"]),
        plan_ref=str(order.offer_snapshot["plan_ref"]),
        billing_period=order.billing_period,
        sales_channel=order.selected_channel,
        country_code=order.country_code,
        currency=order.currency,
        subtotal_amount=Decimal(order.subtotal_amount),
        tax_amount=Decimal(order.tax_amount),
        total_amount=Decimal(order.total_amount),
        status=order.status,
        contract_status=order.contract_status,
        contract_version=str(order.offer_snapshot["contract_version"]),
        payment_requirement=order.payment_requirement,
        payment_status=order.payment_status,
        payment_reference=order.payment_reference,
        payment_destination_snapshot=dict(
            order.payment_destination_snapshot
        ),
        created_at=order.created_at,
        updated_at=order.updated_at,
        reason_code=reason_code,
    )


__all__ = [
    "DirectCommercialOrderResult",
    "TunisiaDirectOrderService",
    "TunisiaPaymentOptionResult",
    "TUNISIA_DIRECT_CONTRACT_VERSION",
]
