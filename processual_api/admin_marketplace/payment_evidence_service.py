from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation

from processual_api.admin_marketplace.audit_contracts import (
    CommercialAuditAction,
    CommercialAuditOutcome,
    CommercialAuditRecord,
    CommercialResourceType,
)
from processual_api.admin_marketplace.authority import (
    AdminMarketplaceAction,
    AdminMarketplaceAuthorityContext,
    require_admin_marketplace_authority,
)
from processual_api.admin_marketplace.errors import (
    CommercialOrderNotFoundError,
    PaymentEvidenceConflictError,
    PaymentEvidenceNotFoundError,
    PaymentVerificationConflictError,
)
from processual_api.admin_marketplace.models import (
    AdminMarketAuditRecord,
    AdminMarketOrder,
    AdminMarketPaymentEvidence,
    AdminMarketPaymentVerification,
)
from processual_api.admin_marketplace.persistence.errors import (
    AdminMarketplaceConflictError,
)
from processual_api.admin_marketplace.persistence.protocols import (
    AdminMarketplaceUnitOfWork,
)


@dataclass(frozen=True, slots=True)
class CustomerPaymentReportResult:
    evidence_id: uuid.UUID
    evidence_ref: str
    order_ref: str
    source_type: str
    status: str
    actual_amount: Decimal
    currency: str
    safe_source_reference: str
    reference_matched: bool
    amount_matched: bool
    currency_matched: bool
    destination_matched: bool
    match_reason_code: str
    reported_at: datetime
    order_status: str
    payment_status: str
    reason_code: str


@dataclass(frozen=True, slots=True)
class AdminPaymentVerificationResult:
    verification_id: uuid.UUID
    verification_ref: str
    evidence_ref: str
    order_ref: str
    status: str
    decision_reason_code: str
    decided_at: datetime
    order_status: str
    payment_status: str
    reason_code: str


class CustomerPaymentEvidenceService:
    """Records customer reports without treating them as payment verification."""

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

    async def report(
        self,
        *,
        actor_user_id: str,
        actor_session_id: str,
        customer_ref: str,
        order_ref: str,
        actual_amount: Decimal,
        currency: str,
        payment_reference: str,
        transfer_reference: str,
        correlation_id: str,
        idempotency_key: str,
    ) -> CustomerPaymentReportResult:
        actor_user_id = _required(actor_user_id, "actor_user_id")
        actor_session_id = _required(actor_session_id, "actor_session_id")
        customer_ref = _required(customer_ref, "customer_ref")
        order_ref = _required(order_ref, "order_ref").lower()
        currency = _currency(currency)
        actual_amount = _amount(actual_amount)
        payment_reference = _required(payment_reference, "payment_reference").upper()
        normalized_source = _source_reference(transfer_reference)
        correlation_id = _required(correlation_id, "correlation_id")
        idempotency_hash = _sha256(_required(idempotency_key, "idempotency_key"))
        source_hash = _sha256(normalized_source)
        now = _aware_now(self._clock(), "Payment evidence")

        try:
            return await self._record_once(
                actor_user_id=actor_user_id,
                actor_session_id=actor_session_id,
                customer_ref=customer_ref,
                order_ref=order_ref,
                actual_amount=actual_amount,
                currency=currency,
                payment_reference=payment_reference,
                source_hash=source_hash,
                safe_source_reference=_masked_reference(normalized_source),
                correlation_id=correlation_id,
                idempotency_hash=idempotency_hash,
                now=now,
            )
        except AdminMarketplaceConflictError:
            replay = await self._replay(
                customer_ref=customer_ref,
                order_ref=order_ref,
                actual_amount=actual_amount,
                currency=currency,
                payment_reference=payment_reference,
                source_hash=source_hash,
                idempotency_hash=idempotency_hash,
            )
            if replay is None:
                raise
            return replay

    async def _record_once(
        self,
        *,
        actor_user_id: str,
        actor_session_id: str,
        customer_ref: str,
        order_ref: str,
        actual_amount: Decimal,
        currency: str,
        payment_reference: str,
        source_hash: str,
        safe_source_reference: str,
        correlation_id: str,
        idempotency_hash: str,
        now: datetime,
    ) -> CustomerPaymentReportResult:
        async with self._unit_of_work_factory() as unit:
            replay = await unit.payment_evidence.get_by_submission_idempotency_key_hash(idempotency_hash)
            if replay is not None:
                order = await unit.orders.get_by_id(replay.order_id)
                _require_replay(
                    evidence=replay,
                    order=order,
                    customer_ref=customer_ref,
                    order_ref=order_ref,
                    actual_amount=actual_amount,
                    currency=currency,
                    payment_reference=payment_reference,
                    source_hash=source_hash,
                )
                return _customer_result(replay, order, "payment_report_idempotent")

            order = await unit.orders.get_by_ref(order_ref, for_update=True)
            _require_customer_payment_order(order, customer_ref)
            previous_digest = _digest(_order_payment_state(order))

            expected_reference = (order.payment_reference or "").strip().upper()
            reference_matched = bool(expected_reference) and hmac.compare_digest(payment_reference, expected_reference)
            amount_matched = actual_amount == Decimal(order.total_amount)
            currency_matched = hmac.compare_digest(currency, order.currency.upper())
            destination_matched = _destination_matches_order(order)
            matched = all(
                (
                    reference_matched,
                    amount_matched,
                    currency_matched,
                    destination_matched,
                )
            )
            match_reason = (
                "customer_report_exact_match"
                if matched
                else _mismatch_reason(
                    reference_matched=reference_matched,
                    amount_matched=amount_matched,
                    currency_matched=currency_matched,
                    destination_matched=destination_matched,
                )
            )
            evidence = AdminMarketPaymentEvidence(
                id=self._id_factory(),
                evidence_ref=f"pev_{self._reference_factory().hex[:24]}",
                order_id=order.id,
                customer_ref=customer_ref,
                source_type="customer_report",
                status="matched" if matched else "requires_review",
                actual_amount=actual_amount,
                currency=currency,
                safe_source_reference=safe_source_reference,
                source_reference_hash=source_hash,
                submission_idempotency_key_hash=idempotency_hash,
                reference_matched=reference_matched,
                amount_matched=amount_matched,
                currency_matched=currency_matched,
                destination_matched=destination_matched,
                match_reason_code=match_reason,
                reported_at=now,
                created_at=now,
            )
            order.payment_status = "customer_reported" if matched else "requires_review"
            order.status = "awaiting_payment" if matched else "payment_under_review"
            order.updated_at = now
            unit.payment_evidence.add(evidence)
            unit.commercial_audit.append(
                _audit_record(
                    event_id=self._event_id_factory(),
                    occurred_at=now,
                    actor_user_id=actor_user_id,
                    actor_session_id=actor_session_id,
                    platform_authority="identity_customer",
                    action=CommercialAuditAction.PAYMENT_EVIDENCE_RECORDED,
                    resource_type=CommercialResourceType.PAYMENT_EVIDENCE,
                    resource_id=evidence.evidence_ref,
                    outcome=(CommercialAuditOutcome.ALLOWED if matched else CommercialAuditOutcome.REQUIRES_REVIEW),
                    reason_code=match_reason,
                    correlation_id=correlation_id,
                    previous_digest=previous_digest,
                    new_digest=_digest(_order_payment_state(order)),
                    metadata={
                        "order_ref": order.order_ref,
                        "source_type": evidence.source_type,
                        "match_reason": match_reason,
                    },
                )
            )
            await unit.commit()
            return _customer_result(evidence, order, "payment_report_recorded")

    async def _replay(
        self,
        *,
        customer_ref: str,
        order_ref: str,
        actual_amount: Decimal,
        currency: str,
        payment_reference: str,
        source_hash: str,
        idempotency_hash: str,
    ) -> CustomerPaymentReportResult | None:
        async with self._unit_of_work_factory() as unit:
            evidence = await unit.payment_evidence.get_by_submission_idempotency_key_hash(idempotency_hash)
            if evidence is None:
                return None
            order = await unit.orders.get_by_id(evidence.order_id)
        _require_replay(
            evidence=evidence,
            order=order,
            customer_ref=customer_ref,
            order_ref=order_ref,
            actual_amount=actual_amount,
            currency=currency,
            payment_reference=payment_reference,
            source_hash=source_hash,
        )
        return _customer_result(evidence, order, "payment_report_idempotent")


class AdminPaymentVerificationService:
    """Applies one explicit, MFA-gated administrator payment decision."""

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

    async def decide(
        self,
        *,
        authority: AdminMarketplaceAuthorityContext,
        evidence_ref: str,
        decision: str,
        reason_code: str,
        correlation_id: str,
        idempotency_key: str,
    ) -> AdminPaymentVerificationResult:
        require_admin_marketplace_authority(
            context=authority,
            action=AdminMarketplaceAction.VERIFY_PAYMENT,
        )
        evidence_ref = _required(evidence_ref, "evidence_ref").lower()
        decision = _required(decision, "decision").lower()
        if decision not in {"verified", "rejected"}:
            raise ValueError("Unsupported payment verification decision.")
        reason_code = _required(reason_code, "reason_code").lower()
        correlation_id = _required(correlation_id, "correlation_id")
        idempotency_hash = _sha256(_required(idempotency_key, "idempotency_key"))
        now = _aware_now(self._clock(), "Payment verification")

        try:
            return await self._decide_once(
                authority=authority,
                evidence_ref=evidence_ref,
                decision=decision,
                reason_code=reason_code,
                correlation_id=correlation_id,
                idempotency_hash=idempotency_hash,
                now=now,
            )
        except AdminMarketplaceConflictError:
            replay = await self._decision_replay(
                evidence_ref=evidence_ref,
                decision=decision,
                reason_code=reason_code,
                idempotency_hash=idempotency_hash,
            )
            if replay is None:
                raise
            return replay

    async def _decide_once(
        self,
        *,
        authority: AdminMarketplaceAuthorityContext,
        evidence_ref: str,
        decision: str,
        reason_code: str,
        correlation_id: str,
        idempotency_hash: str,
        now: datetime,
    ) -> AdminPaymentVerificationResult:
        async with self._unit_of_work_factory() as unit:
            evidence = await unit.payment_evidence.get_by_ref(evidence_ref, for_update=True)
            if evidence is None:
                raise PaymentEvidenceNotFoundError("Payment evidence was not found.")
            order = await unit.orders.get_by_id(evidence.order_id, for_update=True)
            if order is None:
                raise PaymentEvidenceNotFoundError("Payment evidence was not found.")
            existing = await unit.payment_verifications.get_by_order_id(order.id, for_update=True)
            if existing is not None:
                _require_same_decision(
                    existing=existing,
                    evidence=evidence,
                    decision=decision,
                    reason_code=reason_code,
                    idempotency_hash=idempotency_hash,
                )
                return _verification_result(existing, evidence, order, "payment_decision_idempotent")
            _require_verifiable(order=order, evidence=evidence, decision=decision)
            previous_digest = _digest(_order_payment_state(order))
            verification = AdminMarketPaymentVerification(
                id=self._id_factory(),
                verification_ref=f"pvr_{self._reference_factory().hex[:24]}",
                order_id=order.id,
                evidence_id=evidence.id,
                status=decision,
                safe_reference=evidence.evidence_ref,
                decided_by_user_id=authority.user_id,
                decision_reason_code=reason_code,
                decision_idempotency_key_hash=idempotency_hash,
                decided_at=now,
                created_at=now,
                updated_at=now,
            )
            if decision == "verified":
                order.payment_status = "verified"
                order.status = "ready_for_activation"
            elif decision == "rejected":
                order.payment_status = "rejected"
                order.status = "requires_review"
                evidence.status = "rejected"
            order.updated_at = now
            unit.payment_verifications.add(verification)
            unit.commercial_audit.append(
                _audit_record(
                    event_id=self._event_id_factory(),
                    occurred_at=now,
                    actor_user_id=authority.user_id,
                    actor_session_id=authority.session_id,
                    platform_authority="platform_admin",
                    action=CommercialAuditAction.PAYMENT_VERIFICATION_DECIDED,
                    resource_type=CommercialResourceType.PAYMENT_VERIFICATION,
                    resource_id=verification.verification_ref,
                    outcome=(
                        CommercialAuditOutcome.ALLOWED if decision == "verified" else CommercialAuditOutcome.DENIED
                    ),
                    reason_code=reason_code,
                    correlation_id=correlation_id,
                    previous_digest=previous_digest,
                    new_digest=_digest(_order_payment_state(order)),
                    metadata={
                        "order_ref": order.order_ref,
                        "evidence_ref": evidence.evidence_ref,
                        "decision": decision,
                    },
                )
            )
            await unit.commit()
            return _verification_result(verification, evidence, order, "payment_decision_recorded")

    async def _decision_replay(
        self,
        *,
        evidence_ref: str,
        decision: str,
        reason_code: str,
        idempotency_hash: str,
    ) -> AdminPaymentVerificationResult | None:
        async with self._unit_of_work_factory() as unit:
            evidence = await unit.payment_evidence.get_by_ref(evidence_ref)
            if evidence is None:
                return None
            order = await unit.orders.get_by_id(evidence.order_id)
            verification = await unit.payment_verifications.get_by_order_id(evidence.order_id)
        if order is None or verification is None:
            return None
        _require_same_decision(
            existing=verification,
            evidence=evidence,
            decision=decision,
            reason_code=reason_code,
            idempotency_hash=idempotency_hash,
        )
        return _verification_result(verification, evidence, order, "payment_decision_idempotent")


def _require_customer_payment_order(order, customer_ref: str) -> None:
    if order is None or not hmac.compare_digest(order.customer_ref, customer_ref):
        raise CommercialOrderNotFoundError("Commercial order was not found.")
    if order.selected_channel != "maestro_direct" or order.country_code != "TN":
        raise PaymentEvidenceConflictError("Order is not a Tunisian direct order.")
    if order.contract_status != "completed":
        raise PaymentEvidenceConflictError("Contract completion is required.")
    if order.status not in {"awaiting_payment", "payment_under_review"}:
        raise PaymentEvidenceConflictError("Order is not accepting payment reports.")
    if order.payment_status not in {"pending", "customer_reported", "requires_review"}:
        raise PaymentEvidenceConflictError("Payment state does not accept reports.")


def _require_replay(
    *,
    evidence,
    order,
    customer_ref,
    order_ref,
    actual_amount,
    currency,
    payment_reference,
    source_hash,
) -> None:
    if order is None or not hmac.compare_digest(evidence.customer_ref, customer_ref):
        raise PaymentEvidenceConflictError("Idempotency key conflicts with stored state.")
    same = (
        hmac.compare_digest(order.order_ref, order_ref)
        and Decimal(evidence.actual_amount) == actual_amount
        and hmac.compare_digest(evidence.currency, currency)
        and evidence.reference_matched
        == hmac.compare_digest(
            payment_reference,
            (order.payment_reference or "").strip().upper(),
        )
        and hmac.compare_digest(evidence.source_reference_hash, source_hash)
    )
    if not same:
        raise PaymentEvidenceConflictError("Idempotency key conflicts with stored state.")


def _require_verifiable(*, order, evidence, decision: str) -> None:
    if order.contract_status != "completed" or order.selected_channel != "maestro_direct":
        raise PaymentVerificationConflictError("Order cannot be payment-verified.")
    if decision == "verified":
        exact = evidence.status == "matched" and all(
            (
                evidence.reference_matched,
                evidence.amount_matched,
                evidence.currency_matched,
                evidence.destination_matched,
            )
        )
        if not exact or order.payment_status != "customer_reported":
            raise PaymentVerificationConflictError("Only an exact matched customer report can be verified.")
        if order.status != "awaiting_payment":
            raise PaymentVerificationConflictError("Order is not awaiting verification.")


def _require_same_decision(*, existing, evidence, decision, reason_code, idempotency_hash) -> None:
    same = (
        existing.evidence_id == evidence.id
        and existing.status == decision
        and existing.decision_reason_code == reason_code
        and existing.decision_idempotency_key_hash == idempotency_hash
    )
    if not same:
        raise PaymentVerificationConflictError("Payment verification already has a different decision.")


def _destination_matches_order(order: AdminMarketOrder) -> bool:
    snapshot = order.payment_destination_snapshot
    return bool(
        isinstance(snapshot, dict)
        and str(snapshot.get("destination_ref", "")).strip()
        and snapshot.get("country_code") == "TN"
        and snapshot.get("currency") == "TND"
        and snapshot.get("sales_channel") == "maestro_direct"
    )


def _mismatch_reason(**flags: bool) -> str:
    for name in ("reference_matched", "amount_matched", "currency_matched", "destination_matched"):
        if not flags[name]:
            return f"customer_report_{name.removesuffix('_matched')}_mismatch"
    return "customer_report_requires_review"


def _customer_result(evidence, order, reason_code: str) -> CustomerPaymentReportResult:
    return CustomerPaymentReportResult(
        evidence_id=evidence.id,
        evidence_ref=evidence.evidence_ref,
        order_ref=order.order_ref,
        source_type=evidence.source_type,
        status=evidence.status,
        actual_amount=Decimal(evidence.actual_amount),
        currency=evidence.currency,
        safe_source_reference=evidence.safe_source_reference,
        reference_matched=evidence.reference_matched,
        amount_matched=evidence.amount_matched,
        currency_matched=evidence.currency_matched,
        destination_matched=evidence.destination_matched,
        match_reason_code=evidence.match_reason_code,
        reported_at=evidence.reported_at,
        order_status=order.status,
        payment_status=order.payment_status,
        reason_code=reason_code,
    )


def _verification_result(verification, evidence, order, reason_code: str) -> AdminPaymentVerificationResult:
    return AdminPaymentVerificationResult(
        verification_id=verification.id,
        verification_ref=verification.verification_ref,
        evidence_ref=evidence.evidence_ref,
        order_ref=order.order_ref,
        status=verification.status,
        decision_reason_code=verification.decision_reason_code,
        decided_at=verification.decided_at,
        order_status=order.status,
        payment_status=order.payment_status,
        reason_code=reason_code,
    )


def _audit_record(
    *,
    event_id,
    occurred_at,
    actor_user_id,
    actor_session_id,
    platform_authority,
    action,
    resource_type,
    resource_id,
    outcome,
    reason_code,
    correlation_id,
    previous_digest,
    new_digest,
    metadata,
) -> AdminMarketAuditRecord:
    record = CommercialAuditRecord(
        event_id=str(event_id),
        occurred_at=occurred_at,
        actor_user_id=actor_user_id,
        actor_session_id=actor_session_id,
        platform_authority=platform_authority,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=outcome,
        reason_code=reason_code,
        correlation_id=correlation_id,
        previous_state_digest=previous_digest,
        new_state_digest=new_digest,
        metadata=metadata,
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
    normalized = str(value).strip()
    if not normalized:
        raise ValueError(f"{field_name} is required.")
    return normalized


def _currency(value: str) -> str:
    normalized = _required(value, "currency").upper()
    if len(normalized) != 3 or not normalized.isalpha():
        raise ValueError("currency must be a three-letter code.")
    return normalized


def _amount(value: Decimal) -> Decimal:
    try:
        amount = Decimal(value)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("actual_amount is invalid.") from exc
    if not amount.is_finite() or amount < 0 or amount.as_tuple().exponent < -3:
        raise ValueError("actual_amount must be a nonnegative amount with 3 decimals.")
    if amount.adjusted() > 14:
        raise ValueError("actual_amount is too large.")
    return amount


def _source_reference(value: str) -> str:
    normalized = "".join(_required(value, "transfer_reference").upper().split())
    if len(normalized) < 4 or len(normalized) > 128:
        raise ValueError("transfer_reference length is invalid.")
    return normalized


def _masked_reference(value: str) -> str:
    return f"***{value[-4:]}"


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _aware_now(value: datetime, label: str) -> datetime:
    if value.tzinfo is None:
        raise ValueError(f"{label} clock must be timezone-aware.")
    return value


def _order_payment_state(order) -> dict[str, object]:
    return {
        "order_ref": order.order_ref,
        "status": order.status,
        "payment_status": order.payment_status,
        "updated_at": order.updated_at.isoformat(),
    }


def _digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


__all__ = [
    "AdminPaymentVerificationResult",
    "AdminPaymentVerificationService",
    "CustomerPaymentEvidenceService",
    "CustomerPaymentReportResult",
]
