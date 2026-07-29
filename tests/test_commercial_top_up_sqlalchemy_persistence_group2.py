import uuid
from datetime import UTC, datetime
from decimal import Decimal

from processual_api.billing.commercial_top_up_models import (
    CommercialTopUpAuditRecord,
    CommercialTopUpGrant,
    CommercialTopUpOrder,
    CommercialTopUpPaymentEvidence,
)


def test_models_use_expected_tables_and_unique_constraints() -> None:
    assert CommercialTopUpOrder.__tablename__ == "commercial_top_up_orders"
    assert CommercialTopUpPaymentEvidence.__tablename__ == "commercial_top_up_payment_evidence"
    assert CommercialTopUpGrant.__tablename__ == "commercial_top_up_grants"
    assert CommercialTopUpAuditRecord.__tablename__ == "commercial_top_up_audit_records"

    order_constraints = {constraint.name for constraint in CommercialTopUpOrder.__table__.constraints}
    grant_constraints = {constraint.name for constraint in CommercialTopUpGrant.__table__.constraints}

    assert "uq_commercial_top_up_orders_idempotency_key" in order_constraints
    assert "uq_commercial_top_up_grants_idempotency_key" in grant_constraints
    assert "uq_commercial_top_up_grants_order_id" in grant_constraints


def test_model_instances_accept_valid_values() -> None:
    order_id = uuid.uuid4()
    order = CommercialTopUpOrder(
        id=order_id,
        account_id=uuid.uuid4(),
        subscription_id=uuid.uuid4(),
        plan_code="starter",
        requested_units=20_000,
        bundle_count=2,
        total_price_usd=Decimal("118.00"),
        channel="lemon_squeezy",
        idempotency_key="order-001",
        state="grant_pending",
    )
    payment = CommercialTopUpPaymentEvidence(
        order_id=order_id,
        provider_reference="provider-001",
        outcome="verified",
        verified_amount=Decimal("118.00"),
        verified_currency="USD",
        immutable_evidence_reference="audit://payment/001",
    )
    grant = CommercialTopUpGrant(
        order_id=order_id,
        outcome="granted",
        units=20_000,
        grant_idempotency_key=f"top-up-grant:{order_id}:order-001",
        reason="verified",
    )
    audit = CommercialTopUpAuditRecord(
        event_ref="event-001",
        order_id=order_id,
        action="grant_applied",
        occurred_at=datetime.now(UTC),
        actor_reference="system",
        evidence_reference="audit://grant/001",
        payload_digest="sha256:abc",
    )

    assert order.id == order_id
    assert payment.order_id == order_id
    assert grant.order_id == order_id
    assert audit.order_id == order_id


def test_append_only_audit_has_update_and_delete_guards() -> None:
    manager = CommercialTopUpAuditRecord.__mapper__.dispatch
    assert manager.before_update
    assert manager.before_delete


def test_runtime_flags_remain_disabled() -> None:
    from processual_api.billing.commercial_top_up_persistence_audit_contracts import (
        TOP_UP_AUDIT_STORAGE_ENABLED,
        TOP_UP_GRANT_STORAGE_ENABLED,
        TOP_UP_ORDER_STORAGE_ENABLED,
        TOP_UP_PAYMENT_EVIDENCE_STORAGE_ENABLED,
        TOP_UP_RECONCILIATION_EXECUTION_ENABLED,
    )

    assert TOP_UP_ORDER_STORAGE_ENABLED is False
    assert TOP_UP_PAYMENT_EVIDENCE_STORAGE_ENABLED is False
    assert TOP_UP_GRANT_STORAGE_ENABLED is False
    assert TOP_UP_AUDIT_STORAGE_ENABLED is False
    assert TOP_UP_RECONCILIATION_EXECUTION_ENABLED is False
