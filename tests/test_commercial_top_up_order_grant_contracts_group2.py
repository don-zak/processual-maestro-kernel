from decimal import Decimal
from uuid import uuid4

import pytest

from processual_api.billing.commercial_settings_top_up_checkout_contracts import (
    TopUpCheckoutChannel,
)
from processual_api.billing.commercial_top_up_order_grant_contracts import (
    AUDIT_PERSISTENCE_ENABLED,
    ORDER_CREATION_ENABLED,
    ORDER_PERSISTENCE_ENABLED,
    PAYMENT_VERIFICATION_ENABLED,
    UNIT_GRANT_EXECUTION_ENABLED,
    PaymentVerificationContract,
    PaymentVerificationOutcome,
    TopUpOrderContract,
    TopUpOrderState,
    UnitGrantOutcome,
    build_top_up_order_runtime_status,
    decide_unit_grant,
)


def _order(*, confirmed: bool = True, granted: bool = False) -> TopUpOrderContract:
    return TopUpOrderContract(
        order_id=uuid4(),
        account_id=uuid4(),
        subscription_id=uuid4(),
        plan_code="starter",
        requested_units=20_000,
        bundle_count=2,
        total_price_usd=Decimal("118.00"),
        channel=TopUpCheckoutChannel.LEMON_SQUEEZY,
        idempotency_key="client-request-001",
        state=TopUpOrderState.GRANT_PENDING,
        confirmed=confirmed,
        payment_verified=True,
        units_granted=granted,
    )


def _payment(order: TopUpOrderContract) -> PaymentVerificationContract:
    return PaymentVerificationContract(
        order_id=order.order_id,
        provider_reference="provider-payment-001",
        outcome=PaymentVerificationOutcome.VERIFIED,
        verified_amount=Decimal("118.00"),
        verified_currency="USD",
        immutable_evidence_reference="audit://payment/001",
    )


def test_verified_payment_requires_evidence_and_iso_currency() -> None:
    order = _order()
    with pytest.raises(ValueError):
        PaymentVerificationContract(
            order_id=order.order_id,
            provider_reference="provider-payment-001",
            outcome=PaymentVerificationOutcome.VERIFIED,
            verified_amount=Decimal("118.00"),
            verified_currency="US",
            immutable_evidence_reference="audit://payment/001",
        )


def test_unconfirmed_order_is_blocked() -> None:
    order = _order(confirmed=False)
    decision = decide_unit_grant(
        order=order,
        payment=_payment(order),
        previously_granted_idempotency_keys=frozenset(),
    )
    assert decision.outcome is UnitGrantOutcome.BLOCKED
    assert decision.reason == "order confirmation required"


def test_mismatched_payment_is_blocked() -> None:
    order = _order()
    payment = PaymentVerificationContract(
        order_id=uuid4(),
        provider_reference="provider-payment-002",
        outcome=PaymentVerificationOutcome.VERIFIED,
        verified_amount=Decimal("118.00"),
        verified_currency="USD",
        immutable_evidence_reference="audit://payment/002",
    )
    decision = decide_unit_grant(
        order=order,
        payment=payment,
        previously_granted_idempotency_keys=frozenset(),
    )
    assert decision.outcome is UnitGrantOutcome.BLOCKED
    assert decision.reason == "payment does not match order"


def test_amount_mismatch_is_blocked() -> None:
    order = _order()
    payment = PaymentVerificationContract(
        order_id=order.order_id,
        provider_reference="provider-payment-003",
        outcome=PaymentVerificationOutcome.VERIFIED,
        verified_amount=Decimal("117.99"),
        verified_currency="USD",
        immutable_evidence_reference="audit://payment/003",
    )
    decision = decide_unit_grant(
        order=order,
        payment=payment,
        previously_granted_idempotency_keys=frozenset(),
    )
    assert decision.outcome is UnitGrantOutcome.BLOCKED
    assert decision.reason == "verified amount does not match order settlement"


def test_duplicate_grant_is_idempotent() -> None:
    order = _order()
    payment = _payment(order)
    grant_key = f"top-up-grant:{order.order_id}:{order.idempotency_key}"
    decision = decide_unit_grant(
        order=order,
        payment=payment,
        previously_granted_idempotency_keys=frozenset({grant_key}),
    )
    assert decision.outcome is UnitGrantOutcome.DUPLICATE
    assert decision.reason == "grant already recorded"


def test_valid_grant_remains_blocked_while_execution_disabled() -> None:
    order = _order()
    decision = decide_unit_grant(
        order=order,
        payment=_payment(order),
        previously_granted_idempotency_keys=frozenset(),
    )
    assert decision.outcome is UnitGrantOutcome.BLOCKED
    assert decision.reason == "unit grant execution is disabled"


def test_all_runtime_flags_remain_disabled() -> None:
    assert ORDER_CREATION_ENABLED is False
    assert PAYMENT_VERIFICATION_ENABLED is False
    assert UNIT_GRANT_EXECUTION_ENABLED is False
    assert ORDER_PERSISTENCE_ENABLED is False
    assert AUDIT_PERSISTENCE_ENABLED is False

    status = build_top_up_order_runtime_status()
    assert status["status"] == "draft_review"
    assert status["idempotency_required"] is True
    assert status["immutable_audit_required"] is True
    assert status["exactly_once_grant_required"] is True
