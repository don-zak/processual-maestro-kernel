from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from processual_api.billing.commercial_entitlement_grant_posting_service import (
    AdminAdjustmentCommand,
    EntitlementGrantPostingConflictError,
    EntitlementGrantPostingInsufficientBalanceError,
    EntitlementGrantPostingService,
    MonthlySubscriptionGrantCommand,
    TopUpGrantCommand,
    entitlement_grant_posting_service_review_payload,
)
from processual_api.billing.commercial_entitlement_ledger_contracts import (
    EntitlementBalanceSnapshot,
    EntitlementLedgerEntry,
    LedgerEntryType,
)
from processual_api.billing.commercial_entitlement_ledger_persistence_contracts import (
    BalanceCompareAndSwapResult,
    LedgerAppendResult,
)

TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")
SUBSCRIPTION_ID = UUID("22222222-2222-2222-2222-222222222222")
ENTRY_ID = UUID("33333333-3333-3333-3333-333333333333")
NOW = datetime(2026, 7, 30, 12, 30, tzinfo=UTC)


class FakeLedger:
    def __init__(self) -> None:
        self.entries: list[EntitlementLedgerEntry] = []

    async def get_by_idempotency_key(self, **kwargs):
        key = kwargs["idempotency_key"]
        return next((entry for entry in self.entries if entry.idempotency_key == key), None)

    async def append(self, request):
        self.entries.append(request.entry)
        return LedgerAppendResult(
            entry_id=request.entry.entry_id,
            appended=True,
            duplicate=False,
            resulting_balance_version=request.expected_balance_version,
        )


class FakeBalances:
    def __init__(self, snapshot=None, version=0) -> None:
        self.snapshot = snapshot
        self.version = version
        self.fail = False

    async def get_snapshot(self, **kwargs):
        if self.snapshot is None:
            return None
        return self.snapshot, self.version

    async def compare_and_swap(self, request):
        if self.fail or request.expected_version != self.version:
            return BalanceCompareAndSwapResult(
                updated=False,
                previous_version=self.version,
                resulting_version=self.version,
            )
        previous = self.version
        self.version += 1
        self.snapshot = EntitlementBalanceSnapshot(
            tenant_id=request.tenant_id,
            subscription_id=request.subscription_id,
            available_units=request.available_units,
            reserved_units=request.reserved_units,
            committed_units=request.committed_units,
            calculated_at=request.calculated_at,
        )
        return BalanceCompareAndSwapResult(
            updated=True,
            previous_version=previous,
            resulting_version=self.version,
        )


class FakeReservations:
    pass


class FakeUow:
    def __init__(self, snapshot=None, version=0) -> None:
        self.ledger = FakeLedger()
        self.balances = FakeBalances(snapshot, version)
        self.reservations = FakeReservations()
        self.commits = 0
        self.rollbacks = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return None

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


def snapshot(available=0, reserved=0, committed=0):
    return EntitlementBalanceSnapshot(
        tenant_id=TENANT_ID,
        subscription_id=SUBSCRIPTION_ID,
        available_units=available,
        reserved_units=reserved,
        committed_units=committed,
        calculated_at=NOW,
    )


def make_service(uow):
    return EntitlementGrantPostingService(
        lambda: uow,
        entry_id_factory=lambda: ENTRY_ID,
    )


@pytest.mark.asyncio
async def test_monthly_grant_creates_balance() -> None:
    uow = FakeUow()
    result = await make_service(uow).post_monthly_subscription_grant(
        MonthlySubscriptionGrantCommand(
            tenant_id=TENANT_ID,
            subscription_id=SUBSCRIPTION_ID,
            units=5_000,
            billing_cycle_reference="2026-07",
            plan_snapshot_reference="plan:v1",
            invoice_reference="invoice:1",
            idempotency_key="monthly:2026-07",
            occurred_at=NOW,
        )
    )
    assert result.available_units == 5_000
    assert result.entry_type is LedgerEntryType.MONTHLY_GRANT
    assert result.resulting_balance_version == 1
    assert uow.commits == 1


@pytest.mark.asyncio
async def test_top_up_preserves_other_balance_fields() -> None:
    uow = FakeUow(snapshot(4_000, 1_000, 2_000), version=3)
    result = await make_service(uow).post_top_up_grant(
        TopUpGrantCommand(
            tenant_id=TENANT_ID,
            subscription_id=SUBSCRIPTION_ID,
            units=2_500,
            order_reference="order:1",
            payment_evidence_reference="evidence:1",
            settlement_reference="settlement:1",
            idempotency_key="top-up:1",
            occurred_at=NOW,
        )
    )
    assert result.available_units == 6_500
    assert result.reserved_units == 1_000
    assert result.committed_units == 2_000


@pytest.mark.asyncio
async def test_duplicate_is_idempotent() -> None:
    uow = FakeUow(snapshot(5_000), version=2)
    command = MonthlySubscriptionGrantCommand(
        tenant_id=TENANT_ID,
        subscription_id=SUBSCRIPTION_ID,
        units=5_000,
        billing_cycle_reference="2026-07",
        plan_snapshot_reference="plan:v1",
        invoice_reference="invoice:1",
        idempotency_key="monthly:2026-07",
        occurred_at=NOW,
    )
    uow.ledger.entries.append(
        EntitlementLedgerEntry(
            entry_id=ENTRY_ID,
            tenant_id=TENANT_ID,
            subscription_id=SUBSCRIPTION_ID,
            entry_type=LedgerEntryType.MONTHLY_GRANT,
            units=5_000,
            idempotency_key=command.idempotency_key,
            occurred_at=NOW,
            source_reference=command.source_reference,
        )
    )
    result = await make_service(uow).post_monthly_subscription_grant(command)
    assert result.duplicate is True
    assert len(uow.ledger.entries) == 1
    assert uow.balances.version == 2


@pytest.mark.asyncio
async def test_admin_debit_is_fail_closed() -> None:
    uow = FakeUow(snapshot(500), version=1)
    with pytest.raises(EntitlementGrantPostingInsufficientBalanceError):
        await make_service(uow).post_admin_adjustment(
            AdminAdjustmentCommand(
                tenant_id=TENANT_ID,
                subscription_id=SUBSCRIPTION_ID,
                adjustment_units=-501,
                actor_reference="admin:1",
                authority_reference="platform_admin",
                audit_reference="audit:1",
                reason="correction",
                idempotency_key="adjustment:1",
                occurred_at=NOW,
            )
        )
    assert uow.rollbacks == 1


@pytest.mark.asyncio
async def test_cas_conflict_rolls_back() -> None:
    uow = FakeUow(snapshot(1_000), version=1)
    uow.balances.fail = True
    with pytest.raises(EntitlementGrantPostingConflictError):
        await make_service(uow).post_top_up_grant(
            TopUpGrantCommand(
                tenant_id=TENANT_ID,
                subscription_id=SUBSCRIPTION_ID,
                units=500,
                order_reference="order:2",
                payment_evidence_reference="evidence:2",
                settlement_reference="settlement:2",
                idempotency_key="top-up:2",
                occurred_at=NOW,
            )
        )
    assert uow.rollbacks == 1


def test_status_remains_disabled() -> None:
    status = entitlement_grant_posting_service_review_payload()
    assert status["status"] == "draft_review"
    assert status["enabled"] is False
    assert status["writes_enabled"] is False
    assert status["runtime_wiring_enabled"] is False
    assert status["commercial_activation_enabled"] is False
