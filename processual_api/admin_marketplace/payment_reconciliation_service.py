from __future__ import annotations

import hashlib
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

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
    PaymentEvidenceNotFoundError,
    PaymentReconciliationConflictError,
)
from processual_api.admin_marketplace.models import (
    AdminMarketAuditRecord,
    AdminMarketPaymentReconciliationCase,
)
from processual_api.admin_marketplace.notification_outbox import enqueue_commercial_notification
from processual_api.admin_marketplace.persistence.protocols import (
    AdminMarketplaceUnitOfWork,
)

_ACTIONS = frozenset({"accept_match", "reject", "link", "unlink", "reevaluate", "review"})
_EXCEPTION_TYPES = frozenset(
    {
        "underpayment",
        "overpayment",
        "unknown_reference",
        "old_destination",
        "late_payment",
        "duplicate_payment",
        "payer_mismatch",
        "currency_mismatch",
        "untrusted_evidence",
        "other",
    }
)
_NOTE_SECRET_PATTERN = re.compile(
    r"(?:password|secret|token|api[_ -]?key|authorization|cookie|credential|otp|mfa|"
    r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b|\d{8,})",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class PaymentReconciliationResult:
    case_ref: str
    evidence_ref: str
    original_order_ref: str
    candidate_order_ref: str | None
    status: str
    exception_type: str
    resolution: str | None
    reason_code: str
    safe_note: str | None
    evidence_status: str
    updated_at: datetime


class PaymentReconciliationService:
    """Resolves exceptions without erasing source evidence or verifying payment."""

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
        action: str,
        exception_type: str | None,
        reason_code: str,
        safe_note: str | None,
        candidate_order_ref: str | None,
        correlation_id: str,
        idempotency_key: str,
    ) -> PaymentReconciliationResult:
        require_admin_marketplace_authority(
            context=authority,
            action=AdminMarketplaceAction.RECONCILE_PAYMENT,
        )
        evidence_ref = _required(evidence_ref, "evidence_ref").lower()
        action = _required(action, "action").lower()
        if action not in _ACTIONS:
            raise PaymentReconciliationConflictError("Unknown reconciliation action.")
        requested_exception_type = (
            None if exception_type is None else _required(exception_type, "exception_type").lower()
        )
        if requested_exception_type is not None and requested_exception_type not in _EXCEPTION_TYPES:
            raise PaymentReconciliationConflictError("Unknown payment exception type.")
        reason_code = _required(reason_code, "reason_code").lower()
        if len(reason_code) > 128:
            raise PaymentReconciliationConflictError("Reason code is too long.")
        note = _safe_note(safe_note)
        candidate_ref = (
            None if candidate_order_ref is None else _required(candidate_order_ref, "candidate_order_ref").lower()
        )
        if action == "link" and candidate_ref is None:
            raise PaymentReconciliationConflictError("A candidate order is required.")
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("Payment reconciliation clock must be timezone-aware.")
        idempotency_hash = _sha256(_required(idempotency_key, "idempotency_key"))
        correlation_id = _required(correlation_id, "correlation_id")

        async with self._unit_of_work_factory() as unit:
            replay = await unit.payment_reconciliations.get_by_idempotency_key_hash(idempotency_hash)
            if replay is not None:
                evidence = await unit.payment_evidence.get_by_ref(evidence_ref)
                if evidence is None or replay.evidence_id != evidence.id or replay.resolution != _resolution(action):
                    raise PaymentReconciliationConflictError("Idempotency key conflicts with stored state.")
                original = await unit.orders.get_by_id(evidence.order_id)
                candidate = (
                    None
                    if replay.candidate_order_id is None
                    else await unit.orders.get_by_id(replay.candidate_order_id)
                )
                return _result(replay, evidence, original, candidate)

            evidence = await unit.payment_evidence.get_by_ref(evidence_ref, for_update=True)
            if evidence is None:
                raise PaymentEvidenceNotFoundError("Payment evidence was not found.")
            original = await unit.orders.get_by_id(evidence.order_id, for_update=True)
            if original is None:
                raise PaymentEvidenceNotFoundError("Payment evidence was not found.")
            case = await unit.payment_reconciliations.get_by_evidence_id(evidence.id, for_update=True)
            candidate = None
            if candidate_ref is not None:
                candidate = await unit.orders.get_by_ref(candidate_ref, for_update=True)
                if candidate is None or candidate.customer_ref != evidence.customer_ref:
                    raise PaymentReconciliationConflictError("Candidate order does not match the evidence customer.")
            if case is None:
                case = AdminMarketPaymentReconciliationCase(
                    id=self._id_factory(),
                    case_ref=f"prc_{self._reference_factory().hex[:24]}",
                    evidence_id=evidence.id,
                    candidate_order_id=None,
                    status="open",
                    exception_type=_exception_type(evidence, original),
                    resolution=None,
                    reason_code=reason_code,
                    safe_note=None,
                    decided_by_user_id=None,
                    decision_idempotency_key_hash=None,
                    opened_at=now,
                    resolved_at=None,
                    created_at=now,
                    updated_at=now,
                )
                unit.payment_reconciliations.add(case)
            previous_digest = _digest(_case_state(case, evidence))
            if requested_exception_type is not None:
                case.exception_type = requested_exception_type
            if action == "link":
                if candidate is None:
                    raise PaymentReconciliationConflictError("A candidate order is required.")
                case.candidate_order_id = candidate.id
            elif action == "unlink":
                case.candidate_order_id = None
                candidate = None
            elif action == "reevaluate":
                target = candidate
                if target is None and case.candidate_order_id is not None:
                    target = await unit.orders.get_by_id(case.candidate_order_id, for_update=True)
                target = target or original
                evidence.amount_matched = Decimal(evidence.actual_amount) == Decimal(target.total_amount)
                evidence.currency_matched = evidence.currency == target.currency
                evidence.destination_matched = _trusted_destination(target)
                if target.id != original.id:
                    evidence.reference_matched = False
                evidence.status = (
                    "matched"
                    if all(
                        (
                            evidence.reference_matched,
                            evidence.amount_matched,
                            evidence.currency_matched,
                            evidence.destination_matched,
                        )
                    )
                    else "requires_review"
                )
                evidence.match_reason_code = (
                    "reconciliation_exact_match" if evidence.status == "matched" else "reconciliation_requires_review"
                )
                candidate = target if target.id != original.id else None
            elif action == "accept_match":
                evidence.status = "matched"
                evidence.match_reason_code = "admin_exception_match_accepted"
                if original.status != "activated":
                    original.status = "awaiting_payment"
                    original.payment_status = "customer_reported"
                    original.updated_at = now
            elif action == "reject":
                evidence.status = "rejected"
            else:
                evidence.status = "requires_review"

            case.status = (
                "rejected" if action == "reject" else ("resolved" if action == "accept_match" else "requires_review")
            )
            case.resolution = _resolution(action)
            case.reason_code = reason_code
            case.safe_note = note
            case.decided_by_user_id = authority.user_id
            case.decision_idempotency_key_hash = idempotency_hash
            case.resolved_at = now if case.status in {"resolved", "rejected"} else None
            case.updated_at = now
            if original.status != "activated" and action in {"reject", "review"}:
                original.status = "payment_under_review" if action == "review" else "requires_review"
                original.payment_status = "requires_review" if action == "review" else "rejected"
                original.updated_at = now
            unit.commercial_audit.append(
                _audit(
                    event_id=self._event_id_factory(),
                    now=now,
                    authority=authority,
                    case=case,
                    evidence_ref=evidence.evidence_ref,
                    action=action,
                    reason_code=reason_code,
                    correlation_id=correlation_id,
                    previous_digest=previous_digest,
                    new_digest=_digest(_case_state(case, evidence)),
                )
            )
            enqueue_commercial_notification(
                unit,
                event_type="payment_reported" if action == "accept_match" else "payment_requires_review",
                aggregate_type="order",
                aggregate_ref=original.order_ref,
                customer_ref=original.customer_ref,
                payload={
                    "order_ref": original.order_ref,
                    "case_ref": case.case_ref,
                    "status": case.status,
                    "reason_code": case.reason_code,
                },
                deduplication_material=idempotency_hash,
                occurred_at=now,
            )
            await unit.commit()
            if candidate is None and case.candidate_order_id is not None:
                candidate = await unit.orders.get_by_id(case.candidate_order_id)
            return _result(case, evidence, original, candidate)


def _resolution(action: str) -> str:
    return "placed_in_review" if action == "review" else action.replace("accept_match", "accepted_match")


def _exception_type(evidence, order) -> str:
    amount = Decimal(evidence.actual_amount)
    expected = Decimal(order.total_amount)
    if amount < expected:
        return "underpayment"
    if amount > expected:
        return "overpayment"
    if not evidence.currency_matched:
        return "currency_mismatch"
    if not evidence.reference_matched:
        return "unknown_reference"
    if not evidence.destination_matched:
        return "old_destination"
    if evidence.source_type not in {"customer_report", "provider_notification", "reconciliation"}:
        return "untrusted_evidence"
    return "other"


def _trusted_destination(order) -> bool:
    snapshot = order.payment_destination_snapshot
    return bool(
        isinstance(snapshot, dict)
        and snapshot.get("country_code") == "TN"
        and snapshot.get("currency") == "TND"
        and snapshot.get("sales_channel") == "maestro_direct"
        and str(snapshot.get("destination_ref", "")).strip()
    )


def _safe_note(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    normalized = " ".join(value.split())
    if len(normalized) > 500 or _NOTE_SECRET_PATTERN.search(normalized):
        raise PaymentReconciliationConflictError("The reconciliation note is not safe.")
    return normalized


def _required(value: str, name: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise PaymentReconciliationConflictError(f"{name} is required.")
    return normalized


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _digest(value: object) -> str:
    return hashlib.sha256(repr(value).encode()).hexdigest()


def _case_state(case, evidence) -> tuple[object, ...]:
    return (
        case.case_ref,
        case.status,
        case.resolution,
        case.candidate_order_id,
        evidence.status,
        evidence.match_reason_code,
    )


def _result(case, evidence, original, candidate) -> PaymentReconciliationResult:
    return PaymentReconciliationResult(
        case_ref=case.case_ref,
        evidence_ref=evidence.evidence_ref,
        original_order_ref=original.order_ref,
        candidate_order_ref=None if candidate is None else candidate.order_ref,
        status=case.status,
        exception_type=case.exception_type,
        resolution=case.resolution,
        reason_code=case.reason_code,
        safe_note=case.safe_note,
        evidence_status=evidence.status,
        updated_at=case.updated_at,
    )


def _audit(
    *, event_id, now, authority, case, evidence_ref, action, reason_code, correlation_id, previous_digest, new_digest
) -> AdminMarketAuditRecord:
    record = CommercialAuditRecord(
        event_id=str(event_id),
        occurred_at=now,
        actor_user_id=authority.user_id,
        actor_session_id=authority.session_id,
        platform_authority="platform_admin",
        action=CommercialAuditAction.PAYMENT_RECONCILIATION_DECIDED,
        resource_type=CommercialResourceType.PAYMENT_RECONCILIATION,
        resource_id=case.case_ref,
        outcome=CommercialAuditOutcome.DENIED
        if action == "reject"
        else (CommercialAuditOutcome.ALLOWED if action == "accept_match" else CommercialAuditOutcome.REQUIRES_REVIEW),
        reason_code=reason_code,
        correlation_id=correlation_id,
        previous_state_digest=previous_digest,
        new_state_digest=new_digest,
        metadata={"evidence_ref": evidence_ref, "reconciliation_action": action},
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


__all__ = ["PaymentReconciliationResult", "PaymentReconciliationService"]
