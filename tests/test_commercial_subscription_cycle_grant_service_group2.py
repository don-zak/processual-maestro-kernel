from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from processual_api.billing.commercial_entitlement_ledger_contracts import (
    EntitlementBalanceSnapshot,
    EntitlementLedgerEntry,
)
from processual_api.billing.commercial_entitlement_ledger_persistence_contracts import (
    BalanceCompareAndSwapResult,
    LedgerAppendResult,
)
from processual_api.billing.commercial_subscription_cycle_grant_service import (
    ApprovedSubscriptionCycleGrantCommand,
    CommercialSubscriptionCycleGrantService,
    SubscriptionCycleGrantAuthorityError,
    SubscriptionCycleGrantDisabledError,
    SubscriptionCycleGrantPolicy,
    SubscriptionCycleKind,
    build_subscription_cycle_grant_status,
)

TENANT_ID = UUID("941ea235-c836-45f1-95d2-997369324301")
SUBSCRIPTION_ID = UUID("941ea235-c836-45f1-95d2-997369324302")
ENTRY_ONE = UUID("941ea235-c836-45f1-95d2-997369324303")
ENTRY_TWO = UUID("941ea235-c836-45f1-95d2-997369324304")
JULY_START = datetime(2026, 7, 1, tzinfo=UTC)
AUGUST_START = datetime(2026, 8, 1, tzinfo=UTC)
SEPTEMBER_START = datetime(2026, 9, 1, tzinfo=UTC)


class Ledger:
    def __init__(self) -> None:
        self.entries: list[EntitlementLedgerEntry] = []

    async def get_by_idempotency_key(self, **kwargs):
        return next(
            (
                entry
                for entry in self.entries
                if entry.tenant_id == kwargs["tenant_id"]
                and entry.subscription_id == kwargs["subscription_id"]
                and entry.idempotency_key == kwargs["idempotency_key"]
            ),
            None,
        )

    async def append(self, request):
        duplicate = await self.get_by_idempotency_key(
            tenant_id=request.entry.tenant_id,
            subscription_id=request.entry.subscription_id,
            idempotency_key=request.entry.idempotency_key,
        )
        if duplicate:
            return LedgerAppendResult(
                entry_id=duplicate.entry_id,
                appended=False,
                duplicate=True,
                resulting_balance_version=(request.expected_balance_version),
            )
        self.entries.append(request.entry)
        return LedgerAppendResult(
            entry_id=request.entry.entry_id,
            appended=True,
            duplicate=False,
            resulting_balance_version=(request.expected_balance_version),
        )


class Balances:
    def __init__(self, available: int = 0) -> None:
        self.version = 0
        self.snapshot = (
            EntitlementBalanceSnapshot(
                tenant_id=TENANT_ID,
                subscription_id=SUBSCRIPTION_ID,
                available_units=available,
                reserved_units=0,
                committed_units=0,
                calculated_at=JULY_START,
            )
            if available
            else None
        )

    async def get_snapshot(self, **kwargs):
        del kwargs
        if self.snapshot is None:
            return None
        return self.snapshot, self.version

    async def compare_and_swap(self, request):
        if request.expected_version != self.version:
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


class Unit:
    def __init__(self, available: int = 0) -> None:
        self.ledger = Ledger()
        self.balances = Balances(available)
        self.commits = 0
        self.rollbacks = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        del exc
        del traceback
        if exc_type is not None:
            await self.rollback()

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


def command(
    *,
    kind: SubscriptionCycleKind,
    cycle: str,
    start: datetime,
    end: datetime,
) -> ApprovedSubscriptionCycleGrantCommand:
    invoice_prefix = "activation-invoice" if kind is SubscriptionCycleKind.ACTIVATION else "renewal-invoice"
    return ApprovedSubscriptionCycleGrantCommand(
        tenant_id=TENANT_ID,
        subscription_id=SUBSCRIPTION_ID,
        cycle_kind=kind,
        cycle_reference=cycle,
        cycle_started_at=start,
        cycle_ends_at=end,
        units=5_000,
        plan_snapshot_reference="academic:v1",
        invoice_reference=f"{invoice_prefix}:{cycle}",
        authority_reference=("subscription-billing-authority:test"),
        approval_reference=f"billing-cycle-approval:{cycle}",
        approved_by="billing-authority:test",
        occurred_at=start,
    )


def enabled_policy() -> SubscriptionCycleGrantPolicy:
    return SubscriptionCycleGrantPolicy(
        enabled=True,
        writes_enabled=True,
    )


@pytest.mark.asyncio
async def test_service_is_fail_closed_by_default() -> None:
    unit = Unit()
    service = CommercialSubscriptionCycleGrantService(unit_of_work_factory=lambda: unit)

    with pytest.raises(
        SubscriptionCycleGrantDisabledError,
        match="service is disabled",
    ):
        await service.post_approved_cycle(
            command(
                kind=SubscriptionCycleKind.ACTIVATION,
                cycle="2026-07",
                start=JULY_START,
                end=AUGUST_START,
            )
        )

    assert unit.ledger.entries == []


@pytest.mark.asyncio
async def test_activation_replay_and_renewal_preserve_rollover() -> None:
    unit = Unit(available=750)
    ids = iter((ENTRY_ONE, ENTRY_TWO))
    service = CommercialSubscriptionCycleGrantService(
        unit_of_work_factory=lambda: unit,
        policy=enabled_policy(),
        entry_id_factory=lambda: next(ids),
    )

    activation = command(
        kind=SubscriptionCycleKind.ACTIVATION,
        cycle="2026-07",
        start=JULY_START,
        end=AUGUST_START,
    )
    renewal = command(
        kind=SubscriptionCycleKind.RENEWAL,
        cycle="2026-08",
        start=AUGUST_START,
        end=SEPTEMBER_START,
    )

    first = await service.post_approved_cycle(activation)
    replay = await service.post_approved_cycle(activation)
    second = await service.post_approved_cycle(renewal)

    assert first.committed is True
    assert first.ledger_result.available_units == 5_750
    assert replay.committed is False
    assert replay.duplicate is True
    assert replay.ledger_result.available_units == 5_750
    assert second.committed is True
    assert second.ledger_result.available_units == 10_750
    assert len(unit.ledger.entries) == 2
    assert unit.balances.version == 2
    assert unit.commits == 3


@pytest.mark.asyncio
async def test_wrong_invoice_authority_is_rejected_before_write() -> None:
    unit = Unit()
    service = CommercialSubscriptionCycleGrantService(
        unit_of_work_factory=lambda: unit,
        policy=enabled_policy(),
    )
    invalid = ApprovedSubscriptionCycleGrantCommand(
        tenant_id=TENANT_ID,
        subscription_id=SUBSCRIPTION_ID,
        cycle_kind=SubscriptionCycleKind.RENEWAL,
        cycle_reference="2026-08",
        cycle_started_at=AUGUST_START,
        cycle_ends_at=SEPTEMBER_START,
        units=5_000,
        plan_snapshot_reference="academic:v1",
        invoice_reference="activation-invoice:2026-08",
        authority_reference=("subscription-billing-authority:test"),
        approval_reference="billing-cycle-approval:2026-08",
        approved_by="billing-authority:test",
        occurred_at=AUGUST_START,
    )

    with pytest.raises(
        SubscriptionCycleGrantAuthorityError,
        match="renewal cycle requires",
    ):
        await service.post_approved_cycle(invalid)

    assert unit.ledger.entries == []
    assert unit.commits == 0


def test_status_remains_fail_closed() -> None:
    status = build_subscription_cycle_grant_status()

    assert status["status"] == "draft_review"
    assert status["enabled"] is False
    assert status["writes_enabled"] is False
    assert status["runtime_wiring_enabled"] is False
    assert status["commercial_activation_enabled"] is False
    assert status["rollover_preserved"] is True
    assert status["subscription_activation_performed"] is False
