from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from processual_api.admin_marketplace.authority import authority_context
from processual_api.admin_marketplace.errors import AdminMarketplaceStepUpRequiredError
from processual_api.admin_marketplace.payment_reconciliation_service import (
    PaymentReconciliationService,
)

NOW = datetime(2026, 8, 5, 16, 0, tzinfo=UTC)


class Repository:
    def __init__(self, items=None):
        self.items = list(items or [])

    async def get_by_ref(self, reference, *, for_update=False):
        return next(
            (
                item
                for item in self.items
                if getattr(item, "evidence_ref", getattr(item, "order_ref", None)) == reference
            ),
            None,
        )

    async def get_by_id(self, item_id, *, for_update=False):
        return next((item for item in self.items if item.id == item_id), None)

    async def get_by_evidence_id(self, evidence_id, *, for_update=False):
        return next((item for item in self.items if item.evidence_id == evidence_id), None)

    async def get_by_idempotency_key_hash(self, key_hash):
        return next(
            (item for item in self.items if item.decision_idempotency_key_hash == key_hash),
            None,
        )

    def add(self, item):
        self.items.append(item)


class Audit:
    def __init__(self):
        self.items = []

    def append(self, item):
        self.items.append(item)


class Unit:
    def __init__(self, order, evidence):
        self.orders = Repository([order])
        self.payment_evidence = Repository([evidence])
        self.payment_reconciliations = Repository()
        self.commercial_audit = Audit()
        self.commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    async def commit(self):
        self.commits += 1


def objects(*, amount=Decimal("40.000")):
    order_id = uuid.uuid4()
    order = SimpleNamespace(
        id=order_id,
        order_ref="ord_tn_001",
        customer_ref="customer_001",
        total_amount=Decimal("49.900"),
        currency="TND",
        status="payment_under_review",
        payment_status="requires_review",
        updated_at=NOW,
        payment_destination_snapshot={
            "destination_ref": "tn_primary",
            "country_code": "TN",
            "currency": "TND",
            "sales_channel": "maestro_direct",
        },
    )
    evidence = SimpleNamespace(
        id=uuid.uuid4(),
        evidence_ref="pev_001",
        order_id=order_id,
        customer_ref="customer_001",
        source_type="customer_report",
        status="requires_review",
        actual_amount=amount,
        currency="TND",
        reference_matched=True,
        amount_matched=False,
        currency_matched=True,
        destination_matched=True,
        match_reason_code="customer_report_amount_mismatch",
    )
    return order, evidence


def authority(*, mfa=True):
    return authority_context(
        user_id="admin_001",
        session_id="session_001",
        platform_authorities=["platform_admin"],
        active_platform_admin=True,
        recent_mfa_step_up=mfa,
    )


def service(unit):
    ids = iter(
        [
            uuid.UUID("10000000-0000-0000-0000-000000000001"),
            uuid.UUID("20000000-0000-0000-0000-000000000001"),
            uuid.UUID("30000000-0000-0000-0000-000000000001"),
        ]
    )
    return PaymentReconciliationService(
        unit_of_work_factory=lambda: unit,
        clock=lambda: NOW,
        id_factory=lambda: next(ids),
        reference_factory=lambda: next(ids),
        event_id_factory=lambda: next(ids),
    )


def kwargs(**changes):
    values = {
        "authority": authority(),
        "evidence_ref": "pev_001",
        "action": "review",
        "exception_type": "underpayment",
        "reason_code": "admin_underpayment_review",
        "safe_note": "Awaiting corrected transfer.",
        "candidate_order_ref": None,
        "correlation_id": "correlation-001",
        "idempotency_key": "reconciliation-key-001",
    }
    values.update(changes)
    return values


@pytest.mark.asyncio
async def test_review_creates_audited_case_without_verifying_payment():
    order, evidence = objects()
    unit = Unit(order, evidence)

    result = await service(unit).decide(**kwargs())

    assert result.exception_type == "underpayment"
    assert result.status == "requires_review"
    assert evidence.status == "requires_review"
    assert order.payment_status == "requires_review"
    assert unit.commits == 1
    assert unit.commercial_audit.items[0].action == "payment_reconciliation_decided"
    assert unit.commercial_audit.items[0].resource_type == "payment_reconciliation"


@pytest.mark.asyncio
async def test_accept_match_stays_separate_from_final_verification_and_activation():
    order, evidence = objects()
    unit = Unit(order, evidence)

    result = await service(unit).decide(**kwargs(action="accept_match", reason_code="admin_exception_accepted"))

    assert result.evidence_status == "matched"
    assert order.status == "awaiting_payment"
    assert order.payment_status == "customer_reported"
    assert not hasattr(unit, "payment_verifications")
    assert not hasattr(unit, "subscriptions")


@pytest.mark.asyncio
async def test_reconciliation_requires_recent_mfa_before_opening_transaction():
    order, evidence = objects()
    unit = Unit(order, evidence)

    with pytest.raises(AdminMarketplaceStepUpRequiredError):
        await service(unit).decide(**kwargs(authority=authority(mfa=False)))

    assert unit.commits == 0
    assert unit.payment_reconciliations.items == []


@pytest.mark.asyncio
async def test_reevaluation_fails_closed_for_amount_mismatch():
    order, evidence = objects()
    unit = Unit(order, evidence)

    result = await service(unit).decide(**kwargs(action="reevaluate", reason_code="admin_reevaluation"))

    assert result.evidence_status == "requires_review"
    assert evidence.amount_matched is False
    assert evidence.match_reason_code == "reconciliation_requires_review"
