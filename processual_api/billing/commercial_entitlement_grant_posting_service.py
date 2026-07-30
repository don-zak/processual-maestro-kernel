"""Atomic entitlement grant, reversal, and adjustment posting service.

This module remains disconnected from checkout, payment webhooks, runtime
execution, and commercial enforcement.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final
from uuid import UUID, uuid4

from processual_api.billing.commercial_entitlement_ledger_contracts import (
    EntitlementBalanceSnapshot,
    EntitlementLedgerEntry,
    LedgerEntryType,
)
from processual_api.billing.commercial_entitlement_ledger_persistence_contracts import (
    BalanceCompareAndSwapRequest,
    EntitlementLedgerUnitOfWork,
    LedgerAppendRequest,
)

ENTITLEMENT_GRANT_POSTING_SERVICE_VERSION: Final = "2026-07-group2-entitlement-grant-posting-v1"
ENTITLEMENT_GRANT_POSTING_SERVICE_STATUS: Final = "draft_review"
ENTITLEMENT_GRANT_POSTING_SERVICE_ENABLED: Final = False
ENTITLEMENT_GRANT_POSTING_WRITES_ENABLED: Final = False
ENTITLEMENT_GRANT_POSTING_RUNTIME_WIRING_ENABLED: Final = False
ENTITLEMENT_GRANT_POSTING_COMMERCIAL_ACTIVATION_ENABLED: Final = False


class EntitlementGrantPostingServiceError(RuntimeError):
    """Base error for entitlement posting operations."""


class EntitlementGrantPostingConflictError(EntitlementGrantPostingServiceError):
    """Raised when persisted state conflicts with the requested operation."""


class EntitlementGrantPostingInsufficientBalanceError(EntitlementGrantPostingServiceError):
    """Raised when a debit would produce a negative available balance."""


@dataclass(frozen=True, slots=True)
class MonthlySubscriptionGrantCommand:
    tenant_id: UUID
    subscription_id: UUID
    units: int
    billing_cycle_reference: str
    plan_snapshot_reference: str
    invoice_reference: str
    idempotency_key: str
    occurred_at: datetime

    def __post_init__(self) -> None:
        _validate_common(self.units, self.idempotency_key, self.occurred_at)
        _require_text(self.billing_cycle_reference, "billing_cycle_reference")
        _require_text(self.plan_snapshot_reference, "plan_snapshot_reference")
        _require_text(self.invoice_reference, "invoice_reference")

    @property
    def source_reference(self) -> str:
        return (
            f"subscription-cycle:{self.billing_cycle_reference}|"
            f"plan:{self.plan_snapshot_reference}|"
            f"invoice:{self.invoice_reference}"
        )


@dataclass(frozen=True, slots=True)
class TopUpGrantCommand:
    tenant_id: UUID
    subscription_id: UUID
    units: int
    order_reference: str
    payment_evidence_reference: str
    settlement_reference: str
    idempotency_key: str
    occurred_at: datetime

    def __post_init__(self) -> None:
        _validate_common(self.units, self.idempotency_key, self.occurred_at)
        _require_text(self.order_reference, "order_reference")
        _require_text(self.payment_evidence_reference, "payment_evidence_reference")
        _require_text(self.settlement_reference, "settlement_reference")

    @property
    def source_reference(self) -> str:
        return (
            f"top-up-order:{self.order_reference}|"
            f"payment:{self.payment_evidence_reference}|"
            f"settlement:{self.settlement_reference}"
        )


@dataclass(frozen=True, slots=True)
class RefundReversalCommand:
    tenant_id: UUID
    subscription_id: UUID
    related_entry_id: UUID
    units: int
    refund_reference: str
    reason: str
    idempotency_key: str
    occurred_at: datetime

    def __post_init__(self) -> None:
        _validate_common(self.units, self.idempotency_key, self.occurred_at)
        _require_text(self.refund_reference, "refund_reference")
        _require_text(self.reason, "reason")


@dataclass(frozen=True, slots=True)
class UsageReversalCommand:
    tenant_id: UUID
    subscription_id: UUID
    related_entry_id: UUID
    reservation_id: UUID
    units: int
    correction_reference: str
    reason: str
    idempotency_key: str
    occurred_at: datetime

    def __post_init__(self) -> None:
        _validate_common(self.units, self.idempotency_key, self.occurred_at)
        _require_text(self.correction_reference, "correction_reference")
        _require_text(self.reason, "reason")


@dataclass(frozen=True, slots=True)
class AdminAdjustmentCommand:
    tenant_id: UUID
    subscription_id: UUID
    adjustment_units: int
    actor_reference: str
    authority_reference: str
    audit_reference: str
    reason: str
    idempotency_key: str
    occurred_at: datetime

    def __post_init__(self) -> None:
        if self.adjustment_units == 0:
            raise ValueError("adjustment_units must not be zero")
        _validate_common(
            abs(self.adjustment_units),
            self.idempotency_key,
            self.occurred_at,
        )
        _require_text(self.actor_reference, "actor_reference")
        _require_text(self.authority_reference, "authority_reference")
        _require_text(self.audit_reference, "audit_reference")
        _require_text(self.reason, "reason")


@dataclass(frozen=True, slots=True)
class EntitlementGrantPostingResult:
    entry_id: UUID
    entry_type: LedgerEntryType
    units: int
    duplicate: bool
    previous_balance_version: int
    resulting_balance_version: int
    available_units: int
    reserved_units: int
    committed_units: int


def _validate_common(units: int, idempotency_key: str, occurred_at: datetime) -> None:
    if units <= 0:
        raise ValueError("units must be positive")
    _require_text(idempotency_key, "idempotency_key")
    if occurred_at.tzinfo is None:
        raise ValueError("occurred_at must be timezone-aware")


def _require_text(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must not be blank")


class EntitlementGrantPostingService:
    def __init__(
        self,
        unit_of_work_factory: Callable[[], EntitlementLedgerUnitOfWork],
        *,
        entry_id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._entry_id_factory = entry_id_factory

    async def post_monthly_subscription_grant(
        self,
        command: MonthlySubscriptionGrantCommand,
    ) -> EntitlementGrantPostingResult:
        return await self._post(
            tenant_id=command.tenant_id,
            subscription_id=command.subscription_id,
            entry_type=LedgerEntryType.MONTHLY_GRANT,
            units=command.units,
            idempotency_key=command.idempotency_key,
            occurred_at=command.occurred_at,
            source_reference=command.source_reference,
            available_delta=command.units,
        )

    async def post_top_up_grant(
        self,
        command: TopUpGrantCommand,
    ) -> EntitlementGrantPostingResult:
        return await self._post(
            tenant_id=command.tenant_id,
            subscription_id=command.subscription_id,
            entry_type=LedgerEntryType.TOP_UP_GRANT,
            units=command.units,
            idempotency_key=command.idempotency_key,
            occurred_at=command.occurred_at,
            source_reference=command.source_reference,
            available_delta=command.units,
        )

    async def post_refund_reversal(
        self,
        command: RefundReversalCommand,
    ) -> EntitlementGrantPostingResult:
        return await self._post(
            tenant_id=command.tenant_id,
            subscription_id=command.subscription_id,
            entry_type=LedgerEntryType.REFUND_REVERSAL,
            units=command.units,
            idempotency_key=command.idempotency_key,
            occurred_at=command.occurred_at,
            source_reference=f"refund:{command.refund_reference}",
            available_delta=-command.units,
            related_entry_id=command.related_entry_id,
            reason=command.reason,
        )

    async def post_usage_reversal(
        self,
        command: UsageReversalCommand,
    ) -> EntitlementGrantPostingResult:
        return await self._post(
            tenant_id=command.tenant_id,
            subscription_id=command.subscription_id,
            entry_type=LedgerEntryType.USAGE_REVERSAL,
            units=command.units,
            idempotency_key=command.idempotency_key,
            occurred_at=command.occurred_at,
            source_reference=f"usage-correction:{command.correction_reference}",
            available_delta=command.units,
            committed_delta=-command.units,
            reservation_id=command.reservation_id,
            related_entry_id=command.related_entry_id,
            reason=command.reason,
        )

    async def post_admin_adjustment(
        self,
        command: AdminAdjustmentCommand,
    ) -> EntitlementGrantPostingResult:
        return await self._post(
            tenant_id=command.tenant_id,
            subscription_id=command.subscription_id,
            entry_type=LedgerEntryType.ADMIN_ADJUSTMENT,
            units=abs(command.adjustment_units),
            idempotency_key=command.idempotency_key,
            occurred_at=command.occurred_at,
            source_reference=(
                f"admin-adjustment:{command.audit_reference}|"
                f"actor:{command.actor_reference}|"
                f"authority:{command.authority_reference}"
            ),
            available_delta=command.adjustment_units,
            adjustment_units=command.adjustment_units,
            reason=command.reason,
        )

    async def _post(
        self,
        *,
        tenant_id: UUID,
        subscription_id: UUID,
        entry_type: LedgerEntryType,
        units: int,
        idempotency_key: str,
        occurred_at: datetime,
        source_reference: str,
        available_delta: int,
        committed_delta: int = 0,
        reservation_id: UUID | None = None,
        related_entry_id: UUID | None = None,
        adjustment_units: int | None = None,
        reason: str | None = None,
    ) -> EntitlementGrantPostingResult:
        async with self._unit_of_work_factory() as unit:
            try:
                duplicate = await unit.ledger.get_by_idempotency_key(
                    tenant_id=tenant_id,
                    subscription_id=subscription_id,
                    idempotency_key=idempotency_key,
                )
                if duplicate is not None:
                    stored = await unit.balances.get_snapshot(
                        tenant_id=tenant_id,
                        subscription_id=subscription_id,
                    )
                    if stored is None:
                        raise EntitlementGrantPostingConflictError("duplicate entry has no persisted balance")
                    snapshot, version = stored
                    await unit.commit()
                    return EntitlementGrantPostingResult(
                        entry_id=duplicate.entry_id,
                        entry_type=duplicate.entry_type,
                        units=duplicate.units,
                        duplicate=True,
                        previous_balance_version=version,
                        resulting_balance_version=version,
                        available_units=snapshot.available_units,
                        reserved_units=snapshot.reserved_units,
                        committed_units=snapshot.committed_units,
                    )

                stored = await unit.balances.get_snapshot(
                    tenant_id=tenant_id,
                    subscription_id=subscription_id,
                )
                if stored is None:
                    snapshot = EntitlementBalanceSnapshot(
                        tenant_id=tenant_id,
                        subscription_id=subscription_id,
                        available_units=0,
                        reserved_units=0,
                        committed_units=0,
                        calculated_at=occurred_at.astimezone(UTC),
                    )
                    version = 0
                else:
                    snapshot, version = stored

                available_units = snapshot.available_units + available_delta
                committed_units = snapshot.committed_units + committed_delta
                if available_units < 0 or committed_units < 0:
                    raise EntitlementGrantPostingInsufficientBalanceError(
                        "posting would create a negative entitlement balance"
                    )

                entry = EntitlementLedgerEntry(
                    entry_id=self._entry_id_factory(),
                    tenant_id=tenant_id,
                    subscription_id=subscription_id,
                    entry_type=entry_type,
                    units=units,
                    idempotency_key=idempotency_key,
                    occurred_at=occurred_at,
                    source_reference=source_reference,
                    reservation_id=reservation_id,
                    related_entry_id=related_entry_id,
                    adjustment_units=adjustment_units,
                    reason=reason,
                )
                append_result = await unit.ledger.append(
                    LedgerAppendRequest(
                        entry=entry,
                        expected_balance_version=version,
                    )
                )
                swap_result = await unit.balances.compare_and_swap(
                    BalanceCompareAndSwapRequest(
                        tenant_id=tenant_id,
                        subscription_id=subscription_id,
                        expected_version=version,
                        available_units=available_units,
                        reserved_units=snapshot.reserved_units,
                        committed_units=committed_units,
                        calculated_at=occurred_at,
                    )
                )
                if not swap_result.updated:
                    raise EntitlementGrantPostingConflictError("entitlement balance compare-and-swap conflict")

                await unit.commit()
                return EntitlementGrantPostingResult(
                    entry_id=append_result.entry_id,
                    entry_type=entry_type,
                    units=units,
                    duplicate=append_result.duplicate,
                    previous_balance_version=version,
                    resulting_balance_version=swap_result.resulting_version,
                    available_units=available_units,
                    reserved_units=snapshot.reserved_units,
                    committed_units=committed_units,
                )
            except BaseException:
                await unit.rollback()
                raise


def entitlement_grant_posting_service_review_payload() -> dict[str, object]:
    return {
        "version": ENTITLEMENT_GRANT_POSTING_SERVICE_VERSION,
        "status": ENTITLEMENT_GRANT_POSTING_SERVICE_STATUS,
        "enabled": ENTITLEMENT_GRANT_POSTING_SERVICE_ENABLED,
        "writes_enabled": ENTITLEMENT_GRANT_POSTING_WRITES_ENABLED,
        "runtime_wiring_enabled": (ENTITLEMENT_GRANT_POSTING_RUNTIME_WIRING_ENABLED),
        "commercial_activation_enabled": (ENTITLEMENT_GRANT_POSTING_COMMERCIAL_ACTIVATION_ENABLED),
        "monthly_grant_defined": True,
        "top_up_grant_defined": True,
        "refund_reversal_defined": True,
        "usage_reversal_defined": True,
        "admin_adjustment_defined": True,
        "idempotency_required": True,
        "balance_cas_required": True,
        "negative_balance_allowed": False,
    }


__all__ = [
    "ENTITLEMENT_GRANT_POSTING_COMMERCIAL_ACTIVATION_ENABLED",
    "ENTITLEMENT_GRANT_POSTING_RUNTIME_WIRING_ENABLED",
    "ENTITLEMENT_GRANT_POSTING_SERVICE_ENABLED",
    "ENTITLEMENT_GRANT_POSTING_SERVICE_STATUS",
    "ENTITLEMENT_GRANT_POSTING_SERVICE_VERSION",
    "ENTITLEMENT_GRANT_POSTING_WRITES_ENABLED",
    "AdminAdjustmentCommand",
    "EntitlementGrantPostingConflictError",
    "EntitlementGrantPostingInsufficientBalanceError",
    "EntitlementGrantPostingResult",
    "EntitlementGrantPostingService",
    "EntitlementGrantPostingServiceError",
    "MonthlySubscriptionGrantCommand",
    "RefundReversalCommand",
    "TopUpGrantCommand",
    "UsageReversalCommand",
    "entitlement_grant_posting_service_review_payload",
]
