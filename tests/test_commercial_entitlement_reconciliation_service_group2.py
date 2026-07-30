from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from processual_api.billing.commercial_entitlement_ledger_contracts import (
    EntitlementBalanceSnapshot,
    EntitlementLedgerEntry,
    LedgerEntryType,
)
from processual_api.billing.commercial_entitlement_reconciliation_service import (
    EntitlementReconciliationDisabledError,
    EntitlementReconciliationInvariantError,
    EntitlementReconciliationOutcome,
    EntitlementReconciliationPolicy,
    EntitlementReconciliationService,
    ReconcileEntitlementCommand,
    build_entitlement_reconciliation_status,
    reconstruct_entitlement_balance,
)

TENANT_ID = UUID("778b2fe8-17a1-47d1-9a0a-c50164f11901")
SUBSCRIPTION_ID = UUID("778b2fe8-17a1-47d1-9a0a-c50164f11902")
NOW = datetime(2026, 7, 30, 15, 20, tzinfo=UTC)


def entry(
    number: int,
    entry_type: LedgerEntryType,
    units: int,
    *,
    adjustment_units: int | None = None,
) -> EntitlementLedgerEntry:
    return EntitlementLedgerEntry(
        entry_id=UUID(f"778b2fe8-17a1-47d1-9a0a-{number:012d}"),
        tenant_id=TENANT_ID,
        subscription_id=SUBSCRIPTION_ID,
        entry_type=entry_type,
        units=units,
        idempotency_key=f"reconciliation-entry-{number}",
        occurred_at=NOW,
        source_reference=f"source:{number}",
        reservation_id=(
            UUID("778b2fe8-17a1-47d1-9a0a-c50164f11999")
            if entry_type
            in {
                LedgerEntryType.USAGE_RESERVE,
                LedgerEntryType.USAGE_COMMIT,
                LedgerEntryType.USAGE_RELEASE,
                LedgerEntryType.USAGE_REVERSAL,
            }
            else None
        ),
        related_entry_id=(
            UUID("778b2fe8-17a1-47d1-9a0a-c50164f11888")
            if entry_type
            in {
                LedgerEntryType.USAGE_REVERSAL,
                LedgerEntryType.REFUND_REVERSAL,
            }
            else None
        ),
        adjustment_units=adjustment_units,
        reason=(
            "test reconciliation"
            if entry_type
            in {
                LedgerEntryType.ADMIN_ADJUSTMENT,
                LedgerEntryType.USAGE_REVERSAL,
                LedgerEntryType.REFUND_REVERSAL,
            }
            else None
        ),
    )


class Ledger:
    def __init__(self, entries) -> None:
        self.entries = tuple(entries)
        self.calls = 0

    async def list_for_subscription(
        self,
        *,
        tenant_id,
        subscription_id,
        after_entry_id=None,
        limit=100,
    ):
        assert tenant_id == TENANT_ID
        assert subscription_id == SUBSCRIPTION_ID
        self.calls += 1
        start = 0
        if after_entry_id is not None:
            ids = [value.entry_id for value in self.entries]
            start = ids.index(after_entry_id) + 1
        return self.entries[start : start + limit]


class Balances:
    def __init__(self, snapshot=None, version=0) -> None:
        self.snapshot = snapshot
        self.version = version

    async def get_snapshot(self, **kwargs):
        del kwargs
        if self.snapshot is None:
            return None
        return self.snapshot, self.version


class Unit:
    def __init__(self, entries, snapshot=None, version=0) -> None:
        self.ledger = Ledger(entries)
        self.balances = Balances(snapshot, version)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        del exc_type
        del exc
        del traceback


def command() -> ReconcileEntitlementCommand:
    return ReconcileEntitlementCommand(
        tenant_id=TENANT_ID,
        subscription_id=SUBSCRIPTION_ID,
        requested_at=NOW,
        actor_reference="reconciliation-worker:test",
        audit_reference="reconciliation-audit:test",
    )


def enabled_policy(page_size=100):
    return EntitlementReconciliationPolicy(
        enabled=True,
        page_size=page_size,
    )


def sequence():
    return (
        entry(1, LedgerEntryType.MONTHLY_GRANT, 5_000),
        entry(2, LedgerEntryType.TOP_UP_GRANT, 2_000),
        entry(3, LedgerEntryType.USAGE_RESERVE, 1_200),
        entry(4, LedgerEntryType.USAGE_COMMIT, 800),
        entry(5, LedgerEntryType.USAGE_RELEASE, 400),
        entry(6, LedgerEntryType.USAGE_REVERSAL, 300),
        entry(7, LedgerEntryType.REFUND_REVERSAL, 500),
        entry(
            8,
            LedgerEntryType.ADMIN_ADJUSTMENT,
            250,
            adjustment_units=250,
        ),
    )


def test_reconstructs_all_balance_components() -> None:
    result = reconstruct_entitlement_balance(sequence())

    assert result.available_units == 6_250
    assert result.reserved_units == 0
    assert result.committed_units == 500
    assert result.entry_count == 8


@pytest.mark.asyncio
async def test_service_is_fail_closed_by_default() -> None:
    unit = Unit(())
    service = EntitlementReconciliationService(unit_of_work_factory=lambda: unit)

    with pytest.raises(
        EntitlementReconciliationDisabledError,
        match="disabled",
    ):
        await service.reconcile(command())


@pytest.mark.asyncio
async def test_matching_balance_returns_digest_and_match() -> None:
    snapshot = EntitlementBalanceSnapshot(
        tenant_id=TENANT_ID,
        subscription_id=SUBSCRIPTION_ID,
        available_units=6_250,
        reserved_units=0,
        committed_units=500,
        calculated_at=NOW,
    )
    unit = Unit(sequence(), snapshot, version=8)
    service = EntitlementReconciliationService(
        unit_of_work_factory=lambda: unit,
        policy=enabled_policy(page_size=3),
    )

    report = await service.reconcile(command())

    assert report.outcome is EntitlementReconciliationOutcome.MATCH
    assert report.available_delta == 0
    assert report.reserved_delta == 0
    assert report.committed_delta == 0
    assert report.actual_balance_version == 8
    assert report.report_digest.startswith("sha256:")
    assert report.auto_repair_performed is False
    assert unit.ledger.calls == 3


@pytest.mark.asyncio
async def test_mismatch_is_reported_without_repair() -> None:
    snapshot = EntitlementBalanceSnapshot(
        tenant_id=TENANT_ID,
        subscription_id=SUBSCRIPTION_ID,
        available_units=6_200,
        reserved_units=25,
        committed_units=525,
        calculated_at=NOW,
    )
    unit = Unit(sequence(), snapshot, version=9)
    service = EntitlementReconciliationService(
        unit_of_work_factory=lambda: unit,
        policy=enabled_policy(),
    )

    report = await service.reconcile(command())

    assert report.outcome is EntitlementReconciliationOutcome.MISMATCH
    assert report.available_delta == -50
    assert report.reserved_delta == 25
    assert report.committed_delta == 25
    assert report.auto_repair_performed is False


@pytest.mark.asyncio
async def test_missing_balance_is_explicit() -> None:
    service = EntitlementReconciliationService(
        unit_of_work_factory=lambda: Unit(sequence()),
        policy=enabled_policy(),
    )

    report = await service.reconcile(command())

    assert report.outcome is EntitlementReconciliationOutcome.MISSING_BALANCE
    assert report.actual_available_units is None
    assert report.available_delta is None


def test_invalid_ledger_sequence_is_rejected() -> None:
    invalid = (
        entry(1, LedgerEntryType.MONTHLY_GRANT, 100),
        entry(2, LedgerEntryType.USAGE_RESERVE, 101),
    )

    with pytest.raises(
        EntitlementReconciliationInvariantError,
        match="negative balance",
    ):
        reconstruct_entitlement_balance(invalid)


def test_status_remains_read_only_and_disabled() -> None:
    status = build_entitlement_reconciliation_status()

    assert status["status"] == "draft_review"
    assert status["enabled"] is False
    assert status["runtime_wiring_enabled"] is False
    assert status["auto_repair_enabled"] is False
    assert status["persistence_enabled"] is False
    assert status["read_only"] is True
    assert status["automatic_correction_prohibited"] is True
