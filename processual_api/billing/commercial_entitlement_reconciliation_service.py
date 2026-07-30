"""Read-only reconciliation for entitlement ledger and materialized balance.

The service reconstructs available, reserved, and committed units from the
immutable ledger, compares them with the persisted balance snapshot, and emits
an auditable report. It never mutates, repairs, or activates runtime behavior.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Final
from uuid import UUID

from processual_api.billing.commercial_entitlement_ledger_contracts import (
    EntitlementLedgerEntry,
    LedgerEntryType,
)
from processual_api.billing.commercial_entitlement_ledger_persistence_contracts import (
    EntitlementLedgerUnitOfWork,
)

ENTITLEMENT_RECONCILIATION_VERSION: Final = "2026-07-group2-entitlement-reconciliation-v1"
ENTITLEMENT_RECONCILIATION_STATUS: Final = "draft_review"
ENTITLEMENT_RECONCILIATION_ENABLED: Final = False
ENTITLEMENT_RECONCILIATION_RUNTIME_WIRING_ENABLED: Final = False
ENTITLEMENT_RECONCILIATION_AUTO_REPAIR_ENABLED: Final = False
ENTITLEMENT_RECONCILIATION_PERSISTENCE_ENABLED: Final = False


class EntitlementReconciliationError(RuntimeError):
    """Base reconciliation error."""


class EntitlementReconciliationDisabledError(EntitlementReconciliationError):
    """Raised when reconciliation remains disabled."""


class EntitlementReconciliationInvariantError(EntitlementReconciliationError):
    """Raised when ledger reconstruction violates balance invariants."""


class EntitlementReconciliationOutcome(StrEnum):
    MATCH = "match"
    MISMATCH = "mismatch"
    MISSING_BALANCE = "missing_balance"


@dataclass(frozen=True, slots=True)
class EntitlementReconciliationPolicy:
    enabled: bool = ENTITLEMENT_RECONCILIATION_ENABLED
    runtime_wiring_enabled: bool = ENTITLEMENT_RECONCILIATION_RUNTIME_WIRING_ENABLED
    auto_repair_enabled: bool = ENTITLEMENT_RECONCILIATION_AUTO_REPAIR_ENABLED
    persistence_enabled: bool = ENTITLEMENT_RECONCILIATION_PERSISTENCE_ENABLED
    page_size: int = 100

    def __post_init__(self) -> None:
        if self.page_size <= 0:
            raise ValueError("page_size must be positive")


@dataclass(frozen=True, slots=True)
class ReconcileEntitlementCommand:
    tenant_id: UUID
    subscription_id: UUID
    requested_at: datetime
    actor_reference: str
    audit_reference: str

    def __post_init__(self) -> None:
        if self.requested_at.tzinfo is None:
            raise ValueError("requested_at must be timezone-aware")
        if not self.actor_reference.strip():
            raise ValueError("actor_reference must not be blank")
        if not self.audit_reference.strip():
            raise ValueError("audit_reference must not be blank")


@dataclass(frozen=True, slots=True)
class ReconstructedEntitlementBalance:
    available_units: int
    reserved_units: int
    committed_units: int
    entry_count: int
    last_entry_id: UUID | None

    def __post_init__(self) -> None:
        if (
            min(
                self.available_units,
                self.reserved_units,
                self.committed_units,
                self.entry_count,
            )
            < 0
        ):
            raise EntitlementReconciliationInvariantError("reconstructed entitlement values must not be negative")


@dataclass(frozen=True, slots=True)
class EntitlementReconciliationReport:
    tenant_id: UUID
    subscription_id: UUID
    outcome: EntitlementReconciliationOutcome
    expected_available_units: int
    expected_reserved_units: int
    expected_committed_units: int
    actual_available_units: int | None
    actual_reserved_units: int | None
    actual_committed_units: int | None
    actual_balance_version: int | None
    available_delta: int | None
    reserved_delta: int | None
    committed_delta: int | None
    entry_count: int
    last_entry_id: UUID | None
    requested_at: datetime
    actor_reference: str
    audit_reference: str
    report_digest: str
    auto_repair_performed: bool = False

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["tenant_id"] = str(self.tenant_id)
        payload["subscription_id"] = str(self.subscription_id)
        payload["outcome"] = self.outcome.value
        payload["last_entry_id"] = None if self.last_entry_id is None else str(self.last_entry_id)
        payload["requested_at"] = self.requested_at.astimezone(UTC).isoformat()
        return payload


class EntitlementReconciliationService:
    def __init__(
        self,
        *,
        unit_of_work_factory: Callable[[], EntitlementLedgerUnitOfWork],
        policy: EntitlementReconciliationPolicy | None = None,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._policy = policy or EntitlementReconciliationPolicy()

    async def reconcile(
        self,
        command: ReconcileEntitlementCommand,
    ) -> EntitlementReconciliationReport:
        if not self._policy.enabled:
            raise EntitlementReconciliationDisabledError("entitlement reconciliation is disabled")
        if self._policy.auto_repair_enabled:
            raise EntitlementReconciliationError("automatic entitlement repair is prohibited")

        async with self._unit_of_work_factory() as unit:
            entries = await self._list_all_entries(
                unit=unit,
                tenant_id=command.tenant_id,
                subscription_id=command.subscription_id,
            )
            reconstructed = reconstruct_entitlement_balance(entries)
            stored = await unit.balances.get_snapshot(
                tenant_id=command.tenant_id,
                subscription_id=command.subscription_id,
            )

        if stored is None:
            outcome = EntitlementReconciliationOutcome.MISSING_BALANCE
            actual_available = None
            actual_reserved = None
            actual_committed = None
            version = None
            available_delta = None
            reserved_delta = None
            committed_delta = None
        else:
            snapshot, version = stored
            actual_available = snapshot.available_units
            actual_reserved = snapshot.reserved_units
            actual_committed = snapshot.committed_units
            available_delta = actual_available - reconstructed.available_units
            reserved_delta = actual_reserved - reconstructed.reserved_units
            committed_delta = actual_committed - reconstructed.committed_units
            outcome = (
                EntitlementReconciliationOutcome.MATCH
                if (available_delta == 0 and reserved_delta == 0 and committed_delta == 0)
                else EntitlementReconciliationOutcome.MISMATCH
            )

        digest = _report_digest(
            tenant_id=command.tenant_id,
            subscription_id=command.subscription_id,
            outcome=outcome,
            reconstructed=reconstructed,
            actual_available=actual_available,
            actual_reserved=actual_reserved,
            actual_committed=actual_committed,
            version=version,
            audit_reference=command.audit_reference,
        )

        return EntitlementReconciliationReport(
            tenant_id=command.tenant_id,
            subscription_id=command.subscription_id,
            outcome=outcome,
            expected_available_units=(reconstructed.available_units),
            expected_reserved_units=reconstructed.reserved_units,
            expected_committed_units=(reconstructed.committed_units),
            actual_available_units=actual_available,
            actual_reserved_units=actual_reserved,
            actual_committed_units=actual_committed,
            actual_balance_version=version,
            available_delta=available_delta,
            reserved_delta=reserved_delta,
            committed_delta=committed_delta,
            entry_count=reconstructed.entry_count,
            last_entry_id=reconstructed.last_entry_id,
            requested_at=command.requested_at,
            actor_reference=command.actor_reference,
            audit_reference=command.audit_reference,
            report_digest=digest,
            auto_repair_performed=False,
        )

    async def _list_all_entries(
        self,
        *,
        unit: EntitlementLedgerUnitOfWork,
        tenant_id: UUID,
        subscription_id: UUID,
    ) -> tuple[EntitlementLedgerEntry, ...]:
        entries: list[EntitlementLedgerEntry] = []
        after_entry_id: UUID | None = None

        while True:
            page = await unit.ledger.list_for_subscription(
                tenant_id=tenant_id,
                subscription_id=subscription_id,
                after_entry_id=after_entry_id,
                limit=self._policy.page_size,
            )
            if not page:
                break
            entries.extend(page)
            if len(page) < self._policy.page_size:
                break
            next_anchor = page[-1].entry_id
            if next_anchor == after_entry_id:
                raise EntitlementReconciliationInvariantError("ledger pagination did not advance")
            after_entry_id = next_anchor

        return tuple(entries)


def reconstruct_entitlement_balance(
    entries: tuple[EntitlementLedgerEntry, ...],
) -> ReconstructedEntitlementBalance:
    available = 0
    reserved = 0
    committed = 0
    seen_entry_ids: set[UUID] = set()
    seen_idempotency_keys: set[str] = set()

    for entry in entries:
        if entry.entry_id in seen_entry_ids:
            raise EntitlementReconciliationInvariantError("duplicate ledger entry id")
        if entry.idempotency_key in seen_idempotency_keys:
            raise EntitlementReconciliationInvariantError("duplicate ledger idempotency key")
        seen_entry_ids.add(entry.entry_id)
        seen_idempotency_keys.add(entry.idempotency_key)

        if entry.entry_type in {
            LedgerEntryType.MONTHLY_GRANT,
            LedgerEntryType.TOP_UP_GRANT,
        }:
            available += entry.units
        elif entry.entry_type is LedgerEntryType.USAGE_RESERVE:
            available -= entry.units
            reserved += entry.units
        elif entry.entry_type is LedgerEntryType.USAGE_COMMIT:
            reserved -= entry.units
            committed += entry.units
        elif entry.entry_type is LedgerEntryType.USAGE_RELEASE:
            reserved -= entry.units
            available += entry.units
        elif entry.entry_type is LedgerEntryType.USAGE_REVERSAL:
            committed -= entry.units
            available += entry.units
        elif entry.entry_type is LedgerEntryType.REFUND_REVERSAL:
            available -= entry.units
        elif entry.entry_type is LedgerEntryType.ADMIN_ADJUSTMENT:
            if entry.adjustment_units is None:
                raise EntitlementReconciliationInvariantError("admin adjustment requires adjustment_units")
            available += entry.adjustment_units

        if min(available, reserved, committed) < 0:
            raise EntitlementReconciliationInvariantError("ledger sequence reconstructs a negative balance")

    return ReconstructedEntitlementBalance(
        available_units=available,
        reserved_units=reserved,
        committed_units=committed,
        entry_count=len(entries),
        last_entry_id=entries[-1].entry_id if entries else None,
    )


def _report_digest(
    *,
    tenant_id: UUID,
    subscription_id: UUID,
    outcome: EntitlementReconciliationOutcome,
    reconstructed: ReconstructedEntitlementBalance,
    actual_available: int | None,
    actual_reserved: int | None,
    actual_committed: int | None,
    version: int | None,
    audit_reference: str,
) -> str:
    payload = {
        "tenant_id": str(tenant_id),
        "subscription_id": str(subscription_id),
        "outcome": outcome.value,
        "expected_available": reconstructed.available_units,
        "expected_reserved": reconstructed.reserved_units,
        "expected_committed": reconstructed.committed_units,
        "actual_available": actual_available,
        "actual_reserved": actual_reserved,
        "actual_committed": actual_committed,
        "version": version,
        "entry_count": reconstructed.entry_count,
        "last_entry_id": (None if reconstructed.last_entry_id is None else str(reconstructed.last_entry_id)),
        "audit_reference": audit_reference,
    }
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def build_entitlement_reconciliation_status() -> dict[str, object]:
    return {
        "version": ENTITLEMENT_RECONCILIATION_VERSION,
        "status": ENTITLEMENT_RECONCILIATION_STATUS,
        "enabled": ENTITLEMENT_RECONCILIATION_ENABLED,
        "runtime_wiring_enabled": (ENTITLEMENT_RECONCILIATION_RUNTIME_WIRING_ENABLED),
        "auto_repair_enabled": (ENTITLEMENT_RECONCILIATION_AUTO_REPAIR_ENABLED),
        "persistence_enabled": (ENTITLEMENT_RECONCILIATION_PERSISTENCE_ENABLED),
        "read_only": True,
        "available_reserved_committed_reconstructed": True,
        "pagination_required": True,
        "report_digest_required": True,
        "automatic_correction_prohibited": True,
        "fail_closed_by_default": True,
    }


__all__ = [
    "ENTITLEMENT_RECONCILIATION_AUTO_REPAIR_ENABLED",
    "ENTITLEMENT_RECONCILIATION_ENABLED",
    "ENTITLEMENT_RECONCILIATION_PERSISTENCE_ENABLED",
    "ENTITLEMENT_RECONCILIATION_RUNTIME_WIRING_ENABLED",
    "ENTITLEMENT_RECONCILIATION_STATUS",
    "ENTITLEMENT_RECONCILIATION_VERSION",
    "EntitlementReconciliationDisabledError",
    "EntitlementReconciliationError",
    "EntitlementReconciliationInvariantError",
    "EntitlementReconciliationOutcome",
    "EntitlementReconciliationPolicy",
    "EntitlementReconciliationReport",
    "EntitlementReconciliationService",
    "ReconcileEntitlementCommand",
    "ReconstructedEntitlementBalance",
    "build_entitlement_reconciliation_status",
    "reconstruct_entitlement_balance",
]
