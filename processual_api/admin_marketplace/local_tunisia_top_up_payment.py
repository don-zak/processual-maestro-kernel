from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation

from processual_api.admin_marketplace.subscription_top_up_grant import (
    SubscriptionTopUpGrantCommand,
    SubscriptionTopUpGrantError,
    apply_verified_subscription_top_up_in_uow,
)
from processual_api.billing.commercial_top_up_models import CommercialTopUpPaymentEvidence


class LocalTunisiaTopUpPaymentError(RuntimeError):
    """Tunisia-local top-up payment evidence cannot be verified safely."""


@dataclass(frozen=True, slots=True)
class VerifyLocalTunisiaTopUpPaymentCommand:
    order_id: uuid.UUID
    customer_ref: str
    provider_reference: str
    amount_tnd: Decimal
    evidence_reference: str
    verified_at: datetime


@dataclass(frozen=True, slots=True)
class LocalTunisiaTopUpPaymentResult:
    order_id: uuid.UUID
    grant_id: uuid.UUID
    units: int
    replayed_grant: bool
    committed: bool


async def verify_local_tunisia_top_up_payment_in_uow(
    *,
    uow: object,
    command: VerifyLocalTunisiaTopUpPaymentCommand,
) -> LocalTunisiaTopUpPaymentResult:
    _validate(command)

    order = await uow.top_up_orders.get_by_id(command.order_id, for_update=True)
    if order is None:
        raise LocalTunisiaTopUpPaymentError("top-up order was not found.")
    if order.customer_ref != command.customer_ref:
        raise LocalTunisiaTopUpPaymentError("payment customer conflicts with the top-up order.")
    if order.channel != "local_tunisia" or order.settlement_currency != "TND":
        raise LocalTunisiaTopUpPaymentError("top-up order is not a Tunisia-local settlement.")
    if order.state not in {"awaiting_payment", "payment_verified", "granted"}:
        raise LocalTunisiaTopUpPaymentError("top-up order is not eligible for payment verification.")
    if (
        order.exchange_rate_usd_tnd is None
        or order.exchange_rate_source is None
        or order.exchange_rate_reference is None
        or order.exchange_rate_observed_at is None
        or order.exchange_rate_expires_at is None
    ):
        raise LocalTunisiaTopUpPaymentError("top-up order is missing its fixed exchange-rate snapshot.")

    expected_amount = _decimal(order.settlement_amount, field_name="order settlement amount")
    if command.amount_tnd != expected_amount:
        raise LocalTunisiaTopUpPaymentError("Tunisia-local payment amount conflicts with the order.")

    existing_payment = await uow.top_up_payments.get_by_provider_reference(command.provider_reference)
    if existing_payment is None:
        payment = CommercialTopUpPaymentEvidence(
            id=uuid.uuid4(),
            order_id=order.id,
            provider_reference=command.provider_reference,
            outcome="verified",
            verified_amount=command.amount_tnd,
            verified_currency="TND",
            immutable_evidence_reference=command.evidence_reference,
            created_at=command.verified_at,
        )
        uow.top_up_payments.add(payment)
    elif (
        existing_payment.order_id != order.id
        or existing_payment.outcome != "verified"
        or _decimal(existing_payment.verified_amount, field_name="existing verified amount")
        != command.amount_tnd
        or existing_payment.verified_currency != "TND"
        or existing_payment.immutable_evidence_reference != command.evidence_reference
    ):
        raise LocalTunisiaTopUpPaymentError(
            "Tunisia-local payment reference conflicts with existing evidence."
        )

    if order.state == "awaiting_payment":
        order.state = "payment_verified"

    try:
        grant = await apply_verified_subscription_top_up_in_uow(
            uow=uow,
            command=SubscriptionTopUpGrantCommand(
                order_id=order.id,
                subscription_id=order.subscription_id,
                quota_cycle_id=order.quota_cycle_id,
                customer_ref=order.customer_ref,
                provider_reference=command.provider_reference,
                granted_at=command.verified_at,
            ),
        )
    except SubscriptionTopUpGrantError as exc:
        raise LocalTunisiaTopUpPaymentError(
            "verified Tunisia-local payment could not be granted safely."
        ) from exc

    return LocalTunisiaTopUpPaymentResult(
        order_id=order.id,
        grant_id=grant.grant_id,
        units=grant.units,
        replayed_grant=grant.idempotent_replay,
        committed=False,
    )


def verify_local_tunisia_top_up_payment_factory(
    *,
    unit_of_work_factory: Callable[[], object],
):
    async def verify(
        command: VerifyLocalTunisiaTopUpPaymentCommand,
    ) -> LocalTunisiaTopUpPaymentResult:
        async with unit_of_work_factory() as uow:
            result = await verify_local_tunisia_top_up_payment_in_uow(
                uow=uow,
                command=command,
            )
            if result.replayed_grant:
                return result
            await uow.commit()
            return LocalTunisiaTopUpPaymentResult(
                order_id=result.order_id,
                grant_id=result.grant_id,
                units=result.units,
                replayed_grant=False,
                committed=True,
            )

    return verify


def _decimal(value: object, *, field_name: str) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise LocalTunisiaTopUpPaymentError(f"{field_name} is invalid.") from exc
    if not amount.is_finite() or amount <= 0:
        raise LocalTunisiaTopUpPaymentError(f"{field_name} is invalid.")
    return amount


def _validate(command: VerifyLocalTunisiaTopUpPaymentCommand) -> None:
    if not command.customer_ref.strip():
        raise ValueError("customer_ref must not be blank.")
    if not command.provider_reference.strip():
        raise ValueError("provider_reference must not be blank.")
    if not command.evidence_reference.strip():
        raise ValueError("evidence_reference must not be blank.")
    if not isinstance(command.amount_tnd, Decimal):
        raise TypeError("amount_tnd must use Decimal.")
    if not command.amount_tnd.is_finite() or command.amount_tnd <= 0:
        raise ValueError("amount_tnd must be positive and finite.")
    if command.verified_at.tzinfo is None:
        raise ValueError("verified_at must be timezone-aware.")


__all__ = [
    "LocalTunisiaTopUpPaymentError",
    "LocalTunisiaTopUpPaymentResult",
    "VerifyLocalTunisiaTopUpPaymentCommand",
    "verify_local_tunisia_top_up_payment_factory",
    "verify_local_tunisia_top_up_payment_in_uow",
]
