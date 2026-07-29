"""Order, payment verification, and idempotent unit-grant contracts.

This module defines the lifecycle for quota top-up orders. It does not persist
orders, verify real payments, or mutate entitlement balances.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Any, Final
from uuid import UUID

from processual_api.billing.commercial_settings_top_up_checkout_contracts import (
    TopUpCheckoutChannel,
)

TOP_UP_ORDER_CONTRACT_VERSION: Final = "2026-07-group2-top-up-order-grant-v1"
TOP_UP_ORDER_STATUS: Final = "draft_review"

ORDER_CREATION_ENABLED: Final = False
PAYMENT_VERIFICATION_ENABLED: Final = False
UNIT_GRANT_EXECUTION_ENABLED: Final = False
ORDER_PERSISTENCE_ENABLED: Final = False
AUDIT_PERSISTENCE_ENABLED: Final = False

IDEMPOTENCY_REQUIRED: Final = True
IMMUTABLE_AUDIT_REQUIRED: Final = True
EXACTLY_ONCE_GRANT_REQUIRED: Final = True


class TopUpOrderState(StrEnum):
    DRAFT = "draft"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    AWAITING_PAYMENT = "awaiting_payment"
    PAYMENT_PENDING = "payment_pending"
    PAYMENT_VERIFIED = "payment_verified"
    PAYMENT_REJECTED = "payment_rejected"
    GRANT_PENDING = "grant_pending"
    GRANTED = "granted"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PaymentVerificationOutcome(StrEnum):
    VERIFIED = "verified"
    REJECTED = "rejected"
    PENDING = "pending"


class UnitGrantOutcome(StrEnum):
    GRANTED = "granted"
    DUPLICATE = "duplicate"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class TopUpOrderContract:
    order_id: UUID
    account_id: UUID
    subscription_id: UUID
    plan_code: str
    requested_units: int
    bundle_count: int
    total_price_usd: Decimal
    channel: TopUpCheckoutChannel
    idempotency_key: str
    state: TopUpOrderState
    confirmed: bool
    payment_verified: bool
    units_granted: bool

    def __post_init__(self) -> None:
        if not self.plan_code.strip():
            raise ValueError("plan_code must not be blank")
        if self.requested_units <= 0:
            raise ValueError("requested_units must be positive")
        if self.bundle_count <= 0:
            raise ValueError("bundle_count must be positive")
        if self.total_price_usd <= 0:
            raise ValueError("total_price_usd must be positive")
        if not self.idempotency_key.strip():
            raise ValueError("idempotency_key must not be blank")
        if self.units_granted and not self.payment_verified:
            raise ValueError("units cannot be granted before payment verification")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["order_id"] = str(self.order_id)
        payload["account_id"] = str(self.account_id)
        payload["subscription_id"] = str(self.subscription_id)
        payload["channel"] = self.channel.value
        payload["state"] = self.state.value
        payload["total_price_usd"] = str(self.total_price_usd)
        return payload


@dataclass(frozen=True, slots=True)
class PaymentVerificationContract:
    order_id: UUID
    provider_reference: str
    outcome: PaymentVerificationOutcome
    verified_amount_usd: Decimal | None
    verified_currency: str | None
    immutable_evidence_reference: str | None

    def __post_init__(self) -> None:
        if not self.provider_reference.strip():
            raise ValueError("provider_reference must not be blank")
        if self.verified_amount_usd is not None and self.verified_amount_usd <= 0:
            raise ValueError("verified_amount_usd must be positive")
        if self.verified_currency is not None:
            normalized = self.verified_currency.strip().upper()
            if len(normalized) != 3:
                raise ValueError("verified_currency must be ISO-4217")
        if self.outcome is PaymentVerificationOutcome.VERIFIED:
            if self.verified_amount_usd is None:
                raise ValueError("verified payment requires amount")
            if self.verified_currency != "USD":
                raise ValueError("verified payment currency must be USD")
            if not self.immutable_evidence_reference:
                raise ValueError("verified payment requires immutable evidence")


@dataclass(frozen=True, slots=True)
class UnitGrantDecision:
    order_id: UUID
    outcome: UnitGrantOutcome
    units: int
    grant_idempotency_key: str
    reason: str

    def __post_init__(self) -> None:
        if self.units <= 0:
            raise ValueError("units must be positive")
        if not self.grant_idempotency_key.strip():
            raise ValueError("grant_idempotency_key must not be blank")
        if not self.reason.strip():
            raise ValueError("reason must not be blank")


def decide_unit_grant(
    *,
    order: TopUpOrderContract,
    payment: PaymentVerificationContract,
    previously_granted_idempotency_keys: frozenset[str],
    execution_enabled: bool = UNIT_GRANT_EXECUTION_ENABLED,
) -> UnitGrantDecision:
    grant_key = f"top-up-grant:{order.order_id}:{order.idempotency_key}"

    if grant_key in previously_granted_idempotency_keys or order.units_granted:
        return UnitGrantDecision(
            order_id=order.order_id,
            outcome=UnitGrantOutcome.DUPLICATE,
            units=order.requested_units,
            grant_idempotency_key=grant_key,
            reason="grant already recorded",
        )

    if not order.confirmed:
        return UnitGrantDecision(
            order_id=order.order_id,
            outcome=UnitGrantOutcome.BLOCKED,
            units=order.requested_units,
            grant_idempotency_key=grant_key,
            reason="order confirmation required",
        )

    if payment.order_id != order.order_id:
        return UnitGrantDecision(
            order_id=order.order_id,
            outcome=UnitGrantOutcome.BLOCKED,
            units=order.requested_units,
            grant_idempotency_key=grant_key,
            reason="payment does not match order",
        )

    if payment.outcome is not PaymentVerificationOutcome.VERIFIED:
        return UnitGrantDecision(
            order_id=order.order_id,
            outcome=UnitGrantOutcome.BLOCKED,
            units=order.requested_units,
            grant_idempotency_key=grant_key,
            reason="payment is not verified",
        )

    if payment.verified_amount_usd != order.total_price_usd:
        return UnitGrantDecision(
            order_id=order.order_id,
            outcome=UnitGrantOutcome.BLOCKED,
            units=order.requested_units,
            grant_idempotency_key=grant_key,
            reason="verified amount does not match order",
        )

    if not execution_enabled:
        return UnitGrantDecision(
            order_id=order.order_id,
            outcome=UnitGrantOutcome.BLOCKED,
            units=order.requested_units,
            grant_idempotency_key=grant_key,
            reason="unit grant execution is disabled",
        )

    return UnitGrantDecision(
        order_id=order.order_id,
        outcome=UnitGrantOutcome.GRANTED,
        units=order.requested_units,
        grant_idempotency_key=grant_key,
        reason="payment verified and grant approved",
    )


def build_top_up_order_runtime_status() -> dict[str, Any]:
    return {
        "contract_version": TOP_UP_ORDER_CONTRACT_VERSION,
        "status": TOP_UP_ORDER_STATUS,
        "order_creation_enabled": ORDER_CREATION_ENABLED,
        "payment_verification_enabled": PAYMENT_VERIFICATION_ENABLED,
        "unit_grant_execution_enabled": UNIT_GRANT_EXECUTION_ENABLED,
        "order_persistence_enabled": ORDER_PERSISTENCE_ENABLED,
        "audit_persistence_enabled": AUDIT_PERSISTENCE_ENABLED,
        "idempotency_required": IDEMPOTENCY_REQUIRED,
        "immutable_audit_required": IMMUTABLE_AUDIT_REQUIRED,
        "exactly_once_grant_required": EXACTLY_ONCE_GRANT_REQUIRED,
    }
