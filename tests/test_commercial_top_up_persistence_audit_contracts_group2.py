from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from processual_api.billing.commercial_settings_top_up_checkout_contracts import (
    TopUpCheckoutChannel,
)
from processual_api.billing.commercial_top_up_order_grant_contracts import (
    PaymentVerificationContract,
    PaymentVerificationOutcome,
    TopUpOrderContract,
    TopUpOrderState,
    UnitGrantDecision,
    UnitGrantOutcome,
)
from processual_api.billing.commercial_top_up_persistence_audit_contracts import (
    APPEND_ONLY_AUDIT_REQUIRED,
    ATOMIC_GRANT_AND_AUDIT_REQUIRED,
    TOP_UP_AUDIT_STORAGE_ENABLED,
    TOP_UP_GRANT_STORAGE_ENABLED,
    TOP_UP_ORDER_STORAGE_ENABLED,
    TOP_UP_PAYMENT_EVIDENCE_STORAGE_ENABLED,
    TOP_UP_RECONCILIATION_EXECUTION_ENABLED,
    UNIQUE_GRANT_IDEMPOTENCY_REQUIRED,
    UNIQUE_ORDER_IDEMPOTENCY_REQUIRED,
    TopUpAuditAction,
    TopUpAuditRecord,
    TopUpReconciliationState,
    build_top_up_persistence_runtime_status,
    reconcile_top_up,
)


def _order() -> TopUpOrderContract:
    return TopUpOrderContract(
        order_id=uuid4(),
        account_id=uuid4(),
        subscription_id=uuid4(),
        plan_code="starter",
        requested_units=20_000,
        bundle_count=2,
        total_price_usd=Decimal("118.00"),
        channel=TopUpCheckoutChannel.LEMON_SQUEEZY,
        idempotency_key="order-001",
        state=TopUpOrderState.GRANT_PENDING,
        confirmed=True,
        payment_verified=True,
        units_granted=False,
    )


def _payment(order: TopUpOrderContract) -> PaymentVerificationContract:
    return PaymentVerificationContract(
        order_id=order.order_id,
        provider_reference="payment-001",
        outcome=PaymentVerificationOutcome.VERIFIED,
        verified_amount_usd=Decimal("118.00"),
        verified_currency="USD",
        immutable_evidence_reference="audit://payment/001",
    )


def _grant(order: TopUpOrderContract) -> UnitGrantDecision:
    return UnitGrantDecision(
        order_id=order.order_id,
        outcome=UnitGrantOutcome.GRANTED,
        units=20_000,
        grant_idempotency_key=f"top-up-grant:{order.order_id}:order-001",
        reason="verified grant record",
    )


def test_audit_record_requires_timezone_and_non_blank_evidence() -> None:
    with pytest.raises(ValueError):
        TopUpAuditRecord(
            audit_id=uuid4(),
            order_id=uuid4(),
            action=TopUpAuditAction.ORDER_CREATED,
            occurred_at=datetime.now(),
            actor_reference="system",
            evidence_reference="audit://order/001",
            payload_digest="sha256:abc",
        )

    record = TopUpAuditRecord(
        audit_id=uuid4(),
        order_id=uuid4(),
        action=TopUpAuditAction.ORDER_CREATED,
        occurred_at=datetime.now(UTC),
        actor_reference="system",
        evidence_reference="audit://order/001",
        payload_digest="sha256:abc",
    )
    assert record.action is TopUpAuditAction.ORDER_CREATED


def test_order_without_payment_or_grant_is_consistent() -> None:
    order = _order()
    decision = reconcile_top_up(order=order, payment=None, grant=None)
    assert decision.state is TopUpReconciliationState.CONSISTENT
    assert decision.requires_manual_review is False


def test_payment_without_grant_requires_manual_review() -> None:
    order = _order()
    decision = reconcile_top_up(
        order=order,
        payment=_payment(order),
        grant=None,
    )
    assert decision.state is TopUpReconciliationState.PAYMENT_WITHOUT_GRANT
    assert decision.requires_manual_review is True


def test_grant_without_payment_requires_manual_review() -> None:
    order = _order()
    decision = reconcile_top_up(
        order=order,
        payment=None,
        grant=_grant(order),
    )
    assert decision.state is TopUpReconciliationState.GRANT_WITHOUT_PAYMENT
    assert decision.requires_manual_review is True


def test_complete_records_are_consistent() -> None:
    order = _order()
    decision = reconcile_top_up(
        order=order,
        payment=_payment(order),
        grant=_grant(order),
    )
    assert decision.state is TopUpReconciliationState.CONSISTENT
    assert decision.requires_manual_review is False


def test_missing_order_requires_manual_review() -> None:
    order = _order()
    decision = reconcile_top_up(
        order=None,
        payment=_payment(order),
        grant=None,
    )
    assert decision.state is TopUpReconciliationState.ORDER_MISSING
    assert decision.requires_manual_review is True


def test_runtime_storage_and_reconciliation_remain_disabled() -> None:
    assert TOP_UP_ORDER_STORAGE_ENABLED is False
    assert TOP_UP_PAYMENT_EVIDENCE_STORAGE_ENABLED is False
    assert TOP_UP_GRANT_STORAGE_ENABLED is False
    assert TOP_UP_AUDIT_STORAGE_ENABLED is False
    assert TOP_UP_RECONCILIATION_EXECUTION_ENABLED is False

    assert APPEND_ONLY_AUDIT_REQUIRED is True
    assert UNIQUE_ORDER_IDEMPOTENCY_REQUIRED is True
    assert UNIQUE_GRANT_IDEMPOTENCY_REQUIRED is True
    assert ATOMIC_GRANT_AND_AUDIT_REQUIRED is True

    status = build_top_up_persistence_runtime_status()
    assert status["status"] == "draft_review"
