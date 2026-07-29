"""Persistence, immutable audit, and reconciliation contracts for top-ups.

The module defines storage ports and reconciliation decisions only. It does not
write to a database, mutate balances, call payment providers, or enable runtime
commercial behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Final, Protocol
from uuid import UUID

from processual_api.billing.commercial_top_up_order_grant_contracts import (
    PaymentVerificationContract,
    TopUpOrderContract,
    UnitGrantDecision,
    UnitGrantOutcome,
)

TOP_UP_PERSISTENCE_CONTRACT_VERSION: Final = "2026-07-group2-top-up-persistence-audit-v1"
TOP_UP_PERSISTENCE_STATUS: Final = "draft_review"

TOP_UP_ORDER_STORAGE_ENABLED: Final = False
TOP_UP_PAYMENT_EVIDENCE_STORAGE_ENABLED: Final = False
TOP_UP_GRANT_STORAGE_ENABLED: Final = False
TOP_UP_AUDIT_STORAGE_ENABLED: Final = False
TOP_UP_RECONCILIATION_EXECUTION_ENABLED: Final = False

APPEND_ONLY_AUDIT_REQUIRED: Final = True
UNIQUE_ORDER_IDEMPOTENCY_REQUIRED: Final = True
UNIQUE_GRANT_IDEMPOTENCY_REQUIRED: Final = True
ATOMIC_GRANT_AND_AUDIT_REQUIRED: Final = True


class TopUpAuditAction(StrEnum):
    ORDER_CREATED = "order_created"
    ORDER_CONFIRMED = "order_confirmed"
    PAYMENT_RECORDED = "payment_recorded"
    PAYMENT_VERIFIED = "payment_verified"
    PAYMENT_REJECTED = "payment_rejected"
    GRANT_REQUESTED = "grant_requested"
    GRANT_APPLIED = "grant_applied"
    GRANT_DUPLICATE = "grant_duplicate"
    GRANT_BLOCKED = "grant_blocked"
    RECONCILIATION_FLAGGED = "reconciliation_flagged"


class TopUpReconciliationState(StrEnum):
    CONSISTENT = "consistent"
    PAYMENT_WITHOUT_GRANT = "payment_without_grant"
    GRANT_WITHOUT_PAYMENT = "grant_without_payment"
    DUPLICATE_GRANT = "duplicate_grant"
    ORDER_MISSING = "order_missing"
    MANUAL_REVIEW = "manual_review"


@dataclass(frozen=True, slots=True)
class TopUpAuditRecord:
    audit_id: UUID
    order_id: UUID
    action: TopUpAuditAction
    occurred_at: datetime
    actor_reference: str
    evidence_reference: str
    payload_digest: str

    def __post_init__(self) -> None:
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone aware")
        if not self.actor_reference.strip():
            raise ValueError("actor_reference must not be blank")
        if not self.evidence_reference.strip():
            raise ValueError("evidence_reference must not be blank")
        if not self.payload_digest.strip():
            raise ValueError("payload_digest must not be blank")


@dataclass(frozen=True, slots=True)
class TopUpReconciliationDecision:
    order_id: UUID
    state: TopUpReconciliationState
    reason: str
    requires_manual_review: bool

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("reason must not be blank")


class TopUpOrderRepository(Protocol):
    def get_by_id(self, order_id: UUID) -> TopUpOrderContract | None: ...

    def get_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> TopUpOrderContract | None: ...

    def add(self, order: TopUpOrderContract) -> None: ...


class TopUpPaymentEvidenceRepository(Protocol):
    def get_for_order(
        self,
        order_id: UUID,
    ) -> PaymentVerificationContract | None: ...

    def add(self, payment: PaymentVerificationContract) -> None: ...


class TopUpGrantRepository(Protocol):
    def get_by_idempotency_key(
        self,
        grant_idempotency_key: str,
    ) -> UnitGrantDecision | None: ...

    def add(self, decision: UnitGrantDecision) -> None: ...


class TopUpAuditRepository(Protocol):
    def append(self, record: TopUpAuditRecord) -> None: ...

    def list_for_order(self, order_id: UUID) -> tuple[TopUpAuditRecord, ...]: ...


class TopUpUnitOfWork(Protocol):
    orders: TopUpOrderRepository
    payments: TopUpPaymentEvidenceRepository
    grants: TopUpGrantRepository
    audit: TopUpAuditRepository

    def commit(self) -> None: ...

    def rollback(self) -> None: ...


def reconcile_top_up(
    *,
    order: TopUpOrderContract | None,
    payment: PaymentVerificationContract | None,
    grant: UnitGrantDecision | None,
) -> TopUpReconciliationDecision:
    order_id = (
        order.order_id
        if order is not None
        else payment.order_id
        if payment is not None
        else grant.order_id
        if grant is not None
        else UUID(int=0)
    )

    if order is None:
        return TopUpReconciliationDecision(
            order_id=order_id,
            state=TopUpReconciliationState.ORDER_MISSING,
            reason="top-up order is missing",
            requires_manual_review=True,
        )

    if payment is None and grant is None:
        return TopUpReconciliationDecision(
            order_id=order.order_id,
            state=TopUpReconciliationState.CONSISTENT,
            reason="order exists without verified payment or grant",
            requires_manual_review=False,
        )

    if payment is None and grant is not None:
        return TopUpReconciliationDecision(
            order_id=order.order_id,
            state=TopUpReconciliationState.GRANT_WITHOUT_PAYMENT,
            reason="grant record exists without payment evidence",
            requires_manual_review=True,
        )

    if payment is not None and grant is None:
        return TopUpReconciliationDecision(
            order_id=order.order_id,
            state=TopUpReconciliationState.PAYMENT_WITHOUT_GRANT,
            reason="payment evidence exists without grant record",
            requires_manual_review=True,
        )

    if grant is not None and grant.outcome is UnitGrantOutcome.DUPLICATE:
        return TopUpReconciliationDecision(
            order_id=order.order_id,
            state=TopUpReconciliationState.DUPLICATE_GRANT,
            reason="duplicate grant outcome requires audit confirmation",
            requires_manual_review=True,
        )

    return TopUpReconciliationDecision(
        order_id=order.order_id,
        state=TopUpReconciliationState.CONSISTENT,
        reason="order, payment evidence, and grant record are consistent",
        requires_manual_review=False,
    )


def new_audit_timestamp() -> datetime:
    return datetime.now(UTC)


def build_top_up_persistence_runtime_status() -> dict[str, bool | str]:
    return {
        "contract_version": TOP_UP_PERSISTENCE_CONTRACT_VERSION,
        "status": TOP_UP_PERSISTENCE_STATUS,
        "order_storage_enabled": TOP_UP_ORDER_STORAGE_ENABLED,
        "payment_evidence_storage_enabled": (TOP_UP_PAYMENT_EVIDENCE_STORAGE_ENABLED),
        "grant_storage_enabled": TOP_UP_GRANT_STORAGE_ENABLED,
        "audit_storage_enabled": TOP_UP_AUDIT_STORAGE_ENABLED,
        "reconciliation_execution_enabled": (TOP_UP_RECONCILIATION_EXECUTION_ENABLED),
        "append_only_audit_required": APPEND_ONLY_AUDIT_REQUIRED,
        "unique_order_idempotency_required": (UNIQUE_ORDER_IDEMPOTENCY_REQUIRED),
        "unique_grant_idempotency_required": (UNIQUE_GRANT_IDEMPOTENCY_REQUIRED),
        "atomic_grant_and_audit_required": ATOMIC_GRANT_AND_AUDIT_REQUIRED,
    }
