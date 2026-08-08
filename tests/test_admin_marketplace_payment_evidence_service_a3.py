from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from processual_api.admin_marketplace.authority import authority_context
from processual_api.admin_marketplace.errors import (
    AdminMarketplaceStepUpRequiredError,
    CommercialOrderNotFoundError,
    PaymentVerificationConflictError,
)
from processual_api.admin_marketplace.payment_evidence_service import (
    AdminPaymentVerificationService,
    CustomerPaymentEvidenceService,
)

NOW = datetime(2026, 8, 5, 14, 0, tzinfo=UTC)
ORDER_ID = uuid.UUID("10000000-0000-0000-0000-000000000001")
EVIDENCE_ID = uuid.UUID("20000000-0000-0000-0000-000000000001")
VERIFY_ID = uuid.UUID("30000000-0000-0000-0000-000000000001")
REFERENCE_ID = uuid.UUID("abcdef12-3456-7890-abcd-ef1234567890")
EVENT_ID = uuid.UUID("40000000-0000-0000-0000-000000000001")


class Orders:
    def __init__(self, item) -> None:
        self.item = item
        self.calls = []

    async def get_by_ref(self, order_ref, *, for_update=False):
        self.calls.append(("ref", order_ref, for_update))
        return self.item if self.item.order_ref == order_ref else None

    async def get_by_id(self, order_id, *, for_update=False):
        self.calls.append(("id", order_id, for_update))
        return self.item if self.item.id == order_id else None


class Evidence:
    def __init__(self) -> None:
        self.items = []

    async def get_by_submission_idempotency_key_hash(self, key_hash):
        return next(
            (x for x in self.items if x.submission_idempotency_key_hash == key_hash),
            None,
        )

    async def get_by_ref(self, evidence_ref, *, for_update=False):
        return next((x for x in self.items if x.evidence_ref == evidence_ref), None)

    def add(self, item):
        self.items.append(item)


class Verifications:
    def __init__(self) -> None:
        self.items = []

    async def get_by_order_id(self, order_id, *, for_update=False):
        return next((x for x in self.items if x.order_id == order_id), None)

    def add(self, item):
        self.items.append(item)


class Audit:
    def __init__(self) -> None:
        self.items = []

    def append(self, item):
        self.items.append(item)


class Unit:
    def __init__(self, item) -> None:
        self.orders = Orders(item)
        self.payment_evidence = Evidence()
        self.payment_verifications = Verifications()
        self.commercial_audit = Audit()
        self.commit_calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    async def commit(self):
        self.commit_calls += 1


def order(*, customer_ref="customer_001"):
    return SimpleNamespace(
        id=ORDER_ID,
        order_ref="ord_001",
        customer_ref=customer_ref,
        selected_channel="maestro_direct",
        country_code="TN",
        currency="TND",
        total_amount=Decimal("49.900"),
        status="awaiting_payment",
        contract_status="completed",
        payment_status="pending",
        payment_reference="TN-34567890",
        payment_destination_snapshot={
            "destination_ref": "tn_bank_primary",
            "country_code": "TN",
            "currency": "TND",
            "sales_channel": "maestro_direct",
        },
        updated_at=NOW,
    )


def report_service(unit):
    return CustomerPaymentEvidenceService(
        unit_of_work_factory=lambda: unit,
        clock=lambda: NOW,
        id_factory=lambda: EVIDENCE_ID,
        reference_factory=lambda: REFERENCE_ID,
        event_id_factory=lambda: EVENT_ID,
    )


def report_kwargs(**changes):
    values = {
        "actor_user_id": "user_001",
        "actor_session_id": "session_001",
        "customer_ref": "customer_001",
        "order_ref": "ord_001",
        "actual_amount": Decimal("49.900"),
        "currency": "TND",
        "payment_reference": "TN-34567890",
        "transfer_reference": "BANK-TRANSFER-7788",
        "correlation_id": "corr_001",
        "idempotency_key": "payment-report-idempotency-0001",
    }
    values.update(changes)
    return values


def admin(*, recent_mfa=True):
    return authority_context(
        user_id="admin_001",
        session_id="admin_session_001",
        platform_authorities=("platform_admin",),
        active_platform_admin=True,
        recent_mfa_step_up=recent_mfa,
    )


@pytest.mark.asyncio
async def test_exact_customer_report_is_matched_but_never_verified() -> None:
    unit = Unit(order())

    result = await report_service(unit).report(**report_kwargs())

    assert result.status == "matched"
    assert result.payment_status == "customer_reported"
    assert result.order_status == "awaiting_payment"
    assert result.safe_source_reference == "***7788"
    assert "BANK-TRANSFER" not in result.safe_source_reference
    assert unit.commit_calls == 1
    assert len(unit.payment_verifications.items) == 0
    audit = unit.commercial_audit.items[0]
    assert audit.action == "payment_evidence_recorded"
    assert "BANK-TRANSFER-7788" not in str(audit.metadata_json)


@pytest.mark.asyncio
async def test_mismatched_amount_routes_order_to_review() -> None:
    unit = Unit(order())

    result = await report_service(unit).report(**report_kwargs(actual_amount=Decimal("40.000")))

    assert result.status == "requires_review"
    assert result.amount_matched is False
    assert result.payment_status == "requires_review"
    assert result.order_status == "payment_under_review"


@pytest.mark.asyncio
async def test_customer_cannot_report_against_another_customer_order() -> None:
    unit = Unit(order(customer_ref="different_customer"))

    with pytest.raises(CommercialOrderNotFoundError):
        await report_service(unit).report(**report_kwargs())

    assert unit.commit_calls == 0


@pytest.mark.asyncio
async def test_customer_report_replay_is_idempotent_without_second_audit() -> None:
    unit = Unit(order())
    service = report_service(unit)

    first = await service.report(**report_kwargs())
    replay = await service.report(**report_kwargs())

    assert replay.evidence_ref == first.evidence_ref
    assert replay.reason_code == "payment_report_idempotent"
    assert unit.commit_calls == 1
    assert len(unit.commercial_audit.items) == 1


@pytest.mark.asyncio
async def test_admin_verification_requires_recent_mfa_before_persistence() -> None:
    unit = Unit(order())
    service = AdminPaymentVerificationService(
        unit_of_work_factory=lambda: unit,
        clock=lambda: NOW,
    )

    with pytest.raises(AdminMarketplaceStepUpRequiredError):
        await service.decide(
            authority=admin(recent_mfa=False),
            evidence_ref="pev_001",
            decision="verified",
            reason_code="admin_exact_match_confirmed",
            correlation_id="corr_verify",
            idempotency_key="payment-verify-idempotency-0001",
        )

    assert unit.orders.calls == []


@pytest.mark.asyncio
async def test_admin_exact_match_verification_unlocks_activation_gate() -> None:
    unit = Unit(order())
    await report_service(unit).report(**report_kwargs())
    service = AdminPaymentVerificationService(
        unit_of_work_factory=lambda: unit,
        clock=lambda: NOW,
        id_factory=lambda: VERIFY_ID,
        reference_factory=lambda: REFERENCE_ID,
        event_id_factory=lambda: EVENT_ID,
    )

    result = await service.decide(
        authority=admin(),
        evidence_ref=unit.payment_evidence.items[0].evidence_ref,
        decision="verified",
        reason_code="admin_exact_match_confirmed",
        correlation_id="corr_verify",
        idempotency_key="payment-verify-idempotency-0001",
    )

    assert result.status == "verified"
    assert result.payment_status == "verified"
    assert result.order_status == "ready_for_activation"
    assert unit.commercial_audit.items[-1].platform_authority == "platform_admin"
    assert unit.commercial_audit.items[-1].action == "payment_verification_decided"


@pytest.mark.asyncio
async def test_admin_cannot_verify_mismatched_customer_report() -> None:
    unit = Unit(order())
    await report_service(unit).report(**report_kwargs(actual_amount=Decimal("40.000")))
    service = AdminPaymentVerificationService(
        unit_of_work_factory=lambda: unit,
        clock=lambda: NOW,
    )

    with pytest.raises(PaymentVerificationConflictError):
        await service.decide(
            authority=admin(),
            evidence_ref=unit.payment_evidence.items[0].evidence_ref,
            decision="verified",
            reason_code="admin_exact_match_confirmed",
            correlation_id="corr_verify",
            idempotency_key="payment-verify-idempotency-0001",
        )


@pytest.mark.asyncio
async def test_admin_can_separately_verify_an_explicitly_accepted_exception() -> None:
    unit = Unit(order())
    await report_service(unit).report(**report_kwargs(actual_amount=Decimal("40.000")))
    evidence = unit.payment_evidence.items[0]
    evidence.status = "matched"
    unit.orders.item.status = "awaiting_payment"
    unit.orders.item.payment_status = "customer_reported"
    reconciliation = SimpleNamespace(
        evidence_id=evidence.id,
        status="resolved",
        resolution="accepted_match",
    )

    class Reconciliations:
        async def get_by_evidence_id(self, evidence_id, *, for_update=False):
            assert for_update is True
            return reconciliation if evidence_id == evidence.id else None

    unit.payment_reconciliations = Reconciliations()
    service = AdminPaymentVerificationService(
        unit_of_work_factory=lambda: unit,
        clock=lambda: NOW,
        id_factory=lambda: VERIFY_ID,
        reference_factory=lambda: REFERENCE_ID,
        event_id_factory=lambda: EVENT_ID,
    )

    result = await service.decide(
        authority=admin(),
        evidence_ref=evidence.evidence_ref,
        decision="verified",
        reason_code="admin_accepted_exception_confirmed",
        correlation_id="corr_verify_exception",
        idempotency_key="payment-verify-idempotency-exception-0001",
    )

    assert result.status == "verified"
    assert result.order_status == "ready_for_activation"
