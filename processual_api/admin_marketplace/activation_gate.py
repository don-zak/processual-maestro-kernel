from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping


@dataclass(frozen=True, slots=True)
class ActivationGateInput:
    order_ref: str
    customer_ref: str
    offer_ref: str
    plan_ref: str
    order_status: str
    contract_status: str
    payment_requirement: str
    payment_status: str
    selected_channel: str
    country_code: str
    currency: str
    total_amount: Decimal
    offer_snapshot: Mapping[str, object]
    payment_customer_ref: str | None = None
    payment_order_ref: str | None = None
    payment_amount: Decimal | None = None
    payment_currency: str | None = None
    existing_subscription_order_ref: str | None = None
    existing_active_subscription_customer_ref: str | None = None


@dataclass(frozen=True, slots=True)
class ActivationGateDecision:
    allowed: bool
    reasons: tuple[str, ...]


_REQUIRED_ORDER_STATUS = "ready_for_activation"
_ALLOWED_CONTRACT_STATUSES = frozenset({"completed", "not_required"})
_ALLOWED_PAYMENT_STATUSES = frozenset({"verified", "not_required"})
_ALLOWED_CHANNELS = frozenset({"maestro_direct", "lemon_squeezy"})


def _snapshot_text(snapshot: Mapping[str, object], key: str) -> str:
    value = snapshot.get(key)
    return value.strip() if isinstance(value, str) else ""


def evaluate_activation_gate(candidate: ActivationGateInput) -> ActivationGateDecision:
    """Return a fail-closed activation decision without mutating persistence.

    The gate duplicates high-value identity and commercial checks before a
    transactional activation service creates a subscription. Database unique
    constraints remain the final concurrency authority.
    """

    reasons: list[str] = []

    if not candidate.order_ref.strip():
        reasons.append("missing_order_ref")
    if not candidate.customer_ref.strip():
        reasons.append("missing_customer_ref")
    if not candidate.offer_ref.strip():
        reasons.append("missing_offer_ref")
    if not candidate.plan_ref.strip():
        reasons.append("missing_plan_ref")

    if candidate.order_status != _REQUIRED_ORDER_STATUS:
        reasons.append("order_not_ready_for_activation")
    if candidate.contract_status not in _ALLOWED_CONTRACT_STATUSES:
        reasons.append("contract_not_completed")
    if candidate.payment_status not in _ALLOWED_PAYMENT_STATUSES:
        reasons.append("payment_not_verified")
    if candidate.payment_requirement == "required" and candidate.payment_status != "verified":
        reasons.append("required_payment_not_verified")

    if candidate.selected_channel not in _ALLOWED_CHANNELS:
        reasons.append("unsupported_sales_channel")
    if candidate.selected_channel == "maestro_direct":
        if candidate.country_code != "TN":
            reasons.append("direct_channel_requires_tunisia")
        if candidate.currency != "TND":
            reasons.append("direct_channel_requires_tnd")

    if candidate.total_amount < Decimal("0"):
        reasons.append("negative_order_total")

    snapshot_offer_ref = _snapshot_text(candidate.offer_snapshot, "offer_ref")
    snapshot_plan_ref = _snapshot_text(candidate.offer_snapshot, "plan_ref")
    snapshot_currency = _snapshot_text(candidate.offer_snapshot, "currency")
    snapshot_channel = _snapshot_text(candidate.offer_snapshot, "sales_channel")
    snapshot_at = _snapshot_text(candidate.offer_snapshot, "snapshot_at")

    if not snapshot_offer_ref or snapshot_offer_ref != candidate.offer_ref:
        reasons.append("offer_snapshot_mismatch")
    if not snapshot_plan_ref or snapshot_plan_ref != candidate.plan_ref:
        reasons.append("plan_snapshot_mismatch")
    if not snapshot_currency or snapshot_currency != candidate.currency:
        reasons.append("currency_snapshot_mismatch")
    if not snapshot_channel or snapshot_channel != candidate.selected_channel:
        reasons.append("channel_snapshot_mismatch")
    if not snapshot_at:
        reasons.append("missing_offer_snapshot_timestamp")

    if candidate.payment_status == "verified":
        if candidate.payment_customer_ref != candidate.customer_ref:
            reasons.append("payment_customer_mismatch")
        if candidate.payment_order_ref != candidate.order_ref:
            reasons.append("payment_order_mismatch")
        if candidate.payment_amount != candidate.total_amount:
            reasons.append("payment_amount_mismatch")
        if candidate.payment_currency != candidate.currency:
            reasons.append("payment_currency_mismatch")

    if candidate.existing_subscription_order_ref is not None:
        reasons.append("order_already_has_subscription")
    if (
        candidate.existing_active_subscription_customer_ref is not None
        and candidate.existing_active_subscription_customer_ref != candidate.customer_ref
    ):
        reasons.append("active_subscription_customer_mismatch")
    elif candidate.existing_active_subscription_customer_ref == candidate.customer_ref:
        reasons.append("customer_already_has_active_subscription")

    return ActivationGateDecision(allowed=not reasons, reasons=tuple(reasons))
