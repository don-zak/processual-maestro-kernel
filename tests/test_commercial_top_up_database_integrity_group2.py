from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from processual_api.billing.commercial_top_up_models import (
    CommercialTopUpAuditRecord,
    CommercialTopUpGrant,
    CommercialTopUpOrder,
    CommercialTopUpPaymentEvidence,
)
from processual_api.db.base import Base


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    with Session(engine) as value:
        yield value
    engine.dispose()


def _order(*, key: str = "order-key-001") -> CommercialTopUpOrder:
    return CommercialTopUpOrder(
        id=uuid.uuid4(),
        account_id=uuid.uuid4(),
        subscription_id=uuid.uuid4(),
        plan_code="starter",
        requested_units=20_000,
        bundle_count=2,
        total_price_usd=Decimal("118.00"),
        channel="lemon_squeezy",
        idempotency_key=key,
        state="grant_pending",
    )


def test_unique_order_idempotency_key_is_enforced(session: Session) -> None:
    session.add(_order(key="same-order-key"))
    session.commit()
    session.add(_order(key="same-order-key"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_payment_foreign_key_is_enforced(session: Session) -> None:
    session.add(
        CommercialTopUpPaymentEvidence(
            order_id=uuid.uuid4(),
            provider_reference="provider-orphan",
            outcome="pending",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()


def test_provider_reference_is_unique(session: Session) -> None:
    order = _order()
    session.add(order)
    session.commit()

    first = CommercialTopUpPaymentEvidence(
        id=uuid.uuid4(),
        order_id=order.id,
        provider_reference="provider-unique",
        outcome="verified",
        verified_amount_usd=Decimal("118.00"),
        verified_currency="USD",
        immutable_evidence_reference="audit://payment/a",
    )
    session.add(first)
    session.commit()

    second = CommercialTopUpPaymentEvidence(
        id=uuid.uuid4(),
        order_id=order.id,
        provider_reference="provider-unique",
        outcome="verified",
        verified_amount_usd=Decimal("118.00"),
        verified_currency="USD",
        immutable_evidence_reference="audit://payment/b",
    )
    session.add(second)
    with pytest.raises(IntegrityError):
        session.commit()


def test_only_one_grant_per_order_is_enforced(session: Session) -> None:
    order = _order()
    session.add(order)
    session.commit()

    session.add(
        CommercialTopUpGrant(
            order_id=order.id,
            outcome="granted",
            units=20_000,
            grant_idempotency_key="grant-key-001",
            reason="first",
        )
    )
    session.commit()

    session.add(
        CommercialTopUpGrant(
            order_id=order.id,
            outcome="duplicate",
            units=20_000,
            grant_idempotency_key="grant-key-002",
            reason="second",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()


def test_audit_event_reference_is_unique(session: Session) -> None:
    order = _order()
    session.add(order)
    session.commit()

    def record() -> CommercialTopUpAuditRecord:
        return CommercialTopUpAuditRecord(
            id=uuid.uuid4(),
            event_ref="audit-event-001",
            order_id=order.id,
            action="order_created",
            occurred_at=datetime.now(UTC),
            actor_reference="system",
            evidence_reference="audit://order/001",
            payload_digest="sha256:abc",
        )

    session.add(record())
    session.commit()
    session.add(record())

    with pytest.raises(IntegrityError):
        session.commit()


def test_audit_rows_reject_update_and_delete(session: Session) -> None:
    order = _order()
    audit = CommercialTopUpAuditRecord(
        id=uuid.uuid4(),
        event_ref="audit-event-guard",
        order_id=order.id,
        action="order_created",
        occurred_at=datetime.now(UTC),
        actor_reference="system",
        evidence_reference="audit://order/guard",
        payload_digest="sha256:def",
    )
    session.add(order)
    session.commit()

    session.add(audit)
    session.commit()

    audit.actor_reference = "modified"
    with pytest.raises(ValueError, match="append-only"):
        session.commit()

    session.rollback()
    audit = session.get(CommercialTopUpAuditRecord, audit.id)
    assert audit is not None
    session.delete(audit)
    with pytest.raises(ValueError, match="append-only"):
        session.commit()
