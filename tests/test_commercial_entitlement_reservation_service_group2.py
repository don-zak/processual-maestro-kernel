from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from processual_api.billing.commercial_entitlement_ledger_contracts import (
    EntitlementBalanceSnapshot,
    EntitlementLedgerEntry,
    LedgerEntryType,
)
from processual_api.billing.commercial_entitlement_ledger_persistence_contracts import (
    BalanceCompareAndSwapResult,
    LedgerAppendResult,
    ReservationLock,
)
from processual_api.billing.commercial_entitlement_reservation_service import (
    ENTITLEMENT_RESERVATION_COMMERCIAL_ENFORCEMENT_ENABLED,
    ENTITLEMENT_RESERVATION_RUNTIME_WIRING_ENABLED,
    ENTITLEMENT_RESERVATION_SERVICE_ENABLED,
    ENTITLEMENT_RESERVATION_WRITES_ENABLED,
    CommitReservationCommand,
    EntitlementBalanceConflictError,
    EntitlementInsufficientBalanceError,
    EntitlementReservationLifecycleError,
    EntitlementReservationLockUnavailableError,
    EntitlementReservationService,
    ReleaseReservationCommand,
    ReserveUnitsCommand,
    entitlement_reservation_service_review_payload,
)

TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")
SUBSCRIPTION_ID = UUID("22222222-2222-2222-2222-222222222222")
RESERVATION_ID = UUID("33333333-3333-3333-3333-333333333333")
RESERVE_ENTRY_ID = UUID("44444444-4444-4444-4444-444444444444")
FINAL_ENTRY_ID = UUID("55555555-5555-5555-5555-555555555555")
NOW = datetime(2026, 7, 30, 11, 45, tzinfo=UTC)


def snapshot(
    *,
    available: int = 10_000,
    reserved: int = 0,
    committed: int = 0,
) -> EntitlementBalanceSnapshot:
    return EntitlementBalanceSnapshot(
        tenant_id=TENANT_ID,
        subscription_id=SUBSCRIPTION_ID,
        available_units=available,
        reserved_units=reserved,
        committed_units=committed,
        calculated_at=NOW,
    )


def reserve_entry(
    *,
    units: int = 2_000,
) -> EntitlementLedgerEntry:
    return EntitlementLedgerEntry(
        entry_id=RESERVE_ENTRY_ID,
        tenant_id=TENANT_ID,
        subscription_id=SUBSCRIPTION_ID,
        entry_type=LedgerEntryType.USAGE_RESERVE,
        units=units,
        idempotency_key="reserve:job-1",
        occurred_at=NOW,
        source_reference="job://1",
        reservation_id=RESERVATION_ID,
    )


class FakeLedgerRepository:
    def __init__(self) -> None:
        self.duplicate: EntitlementLedgerEntry | None = None
        self.appended: list[object] = []

    async def get_by_idempotency_key(self, **_: object):
        return self.duplicate

    async def append(self, request):
        self.appended.append(request)
        return LedgerAppendResult(
            entry_id=request.entry.entry_id,
            appended=True,
            duplicate=False,
            resulting_balance_version=(request.expected_balance_version),
        )


class FakeBalanceRepository:
    def __init__(
        self,
        stored: tuple[EntitlementBalanceSnapshot, int] | None,
    ) -> None:
        self.stored = stored
        self.requests: list[object] = []
        self.cas_updated = True

    async def get_snapshot(self, **_: object):
        return self.stored

    async def compare_and_swap(self, request):
        self.requests.append(request)
        if self.cas_updated:
            return BalanceCompareAndSwapResult(
                updated=True,
                previous_version=request.expected_version,
                resulting_version=request.expected_version + 1,
            )
        return BalanceCompareAndSwapResult(
            updated=False,
            previous_version=request.expected_version,
            resulting_version=request.expected_version,
        )


class FakeReservationRepository:
    def __init__(self) -> None:
        self.lock_acquired = True
        self.lifecycle: tuple[EntitlementLedgerEntry, ...] = ()
        self.released: list[ReservationLock] = []

    async def acquire_lock(self, request):
        return ReservationLock(
            tenant_id=request.tenant_id,
            subscription_id=request.subscription_id,
            reservation_id=request.reservation_id,
            owner_token=request.owner_token,
            acquired=self.lock_acquired,
            expires_at=(
                NOW + timedelta(seconds=request.lease_seconds) if self.lock_acquired else NOW + timedelta(seconds=30)
            ),
        )

    async def release_lock(self, lock):
        self.released.append(lock)

    async def list_lifecycle_entries(self, **_: object):
        return self.lifecycle


class FakeUnitOfWork:
    def __init__(
        self,
        stored: tuple[EntitlementBalanceSnapshot, int] | None,
    ) -> None:
        self.ledger = FakeLedgerRepository()
        self.balances = FakeBalanceRepository(stored)
        self.reservations = FakeReservationRepository()
        self.commit_count = 0
        self.rollback_count = 0

    async def __aenter__(self):
        return self

    async def __aexit__(
        self,
        exc_type,
        exc,
        traceback,
    ):
        del exc_type
        del exc
        del traceback

    async def commit(self):
        self.commit_count += 1

    async def rollback(self):
        self.rollback_count += 1


def reserve_command(
    *,
    units: int = 2_000,
    idempotency_key: str = "reserve:job-1",
) -> ReserveUnitsCommand:
    return ReserveUnitsCommand(
        tenant_id=TENANT_ID,
        subscription_id=SUBSCRIPTION_ID,
        reservation_id=RESERVATION_ID,
        units=units,
        idempotency_key=idempotency_key,
        source_reference="job://1",
        owner_token="worker-1",
        occurred_at=NOW,
    )


def commit_command(
    *,
    units: int = 2_000,
) -> CommitReservationCommand:
    return CommitReservationCommand(
        tenant_id=TENANT_ID,
        subscription_id=SUBSCRIPTION_ID,
        reservation_id=RESERVATION_ID,
        units=units,
        idempotency_key="commit:job-1",
        source_reference="job://1",
        owner_token="worker-1",
        occurred_at=NOW,
    )


def release_command(
    *,
    units: int = 2_000,
) -> ReleaseReservationCommand:
    return ReleaseReservationCommand(
        tenant_id=TENANT_ID,
        subscription_id=SUBSCRIPTION_ID,
        reservation_id=RESERVATION_ID,
        units=units,
        idempotency_key="release:job-1",
        source_reference="job://1",
        owner_token="worker-1",
        occurred_at=NOW,
    )


def service_with(unit: FakeUnitOfWork):
    return EntitlementReservationService(
        lambda: unit,
        entry_id_factory=lambda: FINAL_ENTRY_ID,
    )


def test_service_remains_disabled() -> None:
    payload = entitlement_reservation_service_review_payload()

    assert ENTITLEMENT_RESERVATION_SERVICE_ENABLED is False
    assert ENTITLEMENT_RESERVATION_WRITES_ENABLED is False
    assert ENTITLEMENT_RESERVATION_RUNTIME_WIRING_ENABLED is False
    assert ENTITLEMENT_RESERVATION_COMMERCIAL_ENFORCEMENT_ENABLED is False
    assert payload["atomic_uow_required"] is True


@pytest.mark.asyncio
async def test_reserve_moves_available_to_reserved() -> None:
    unit = FakeUnitOfWork((snapshot(), 3))

    result = await service_with(unit).reserve_units(reserve_command())

    request = unit.balances.requests[0]
    assert request.expected_version == 3
    assert request.available_units == 8_000
    assert request.reserved_units == 2_000
    assert request.committed_units == 0
    assert result.resulting_balance_version == 4
    assert unit.commit_count == 1
    assert len(unit.reservations.released) == 1


@pytest.mark.asyncio
async def test_reserve_rejects_insufficient_balance() -> None:
    unit = FakeUnitOfWork((snapshot(available=1_000), 2))

    with pytest.raises(
        EntitlementInsufficientBalanceError,
        match="exceed available",
    ):
        await service_with(unit).reserve_units(reserve_command(units=2_000))

    assert unit.rollback_count == 1
    assert unit.commit_count == 0


@pytest.mark.asyncio
async def test_reserve_rejects_existing_lifecycle() -> None:
    unit = FakeUnitOfWork((snapshot(), 1))
    unit.reservations.lifecycle = (reserve_entry(),)

    with pytest.raises(
        EntitlementReservationLifecycleError,
        match="already has lifecycle",
    ):
        await service_with(unit).reserve_units(reserve_command())


@pytest.mark.asyncio
async def test_lock_contention_fails_closed() -> None:
    unit = FakeUnitOfWork((snapshot(), 1))
    unit.reservations.lock_acquired = False

    with pytest.raises(
        EntitlementReservationLockUnavailableError,
        match="another owner",
    ):
        await service_with(unit).reserve_units(reserve_command())


@pytest.mark.asyncio
async def test_commit_moves_reserved_to_committed() -> None:
    unit = FakeUnitOfWork(
        (
            snapshot(
                available=8_000,
                reserved=2_000,
            ),
            4,
        )
    )
    unit.reservations.lifecycle = (reserve_entry(),)

    result = await service_with(unit).commit_reservation(commit_command())

    request = unit.balances.requests[0]
    assert request.available_units == 8_000
    assert request.reserved_units == 0
    assert request.committed_units == 2_000
    assert result.entry_type is LedgerEntryType.USAGE_COMMIT
    assert result.resulting_balance_version == 5


@pytest.mark.asyncio
async def test_release_restores_available_units() -> None:
    unit = FakeUnitOfWork(
        (
            snapshot(
                available=8_000,
                reserved=2_000,
            ),
            4,
        )
    )
    unit.reservations.lifecycle = (reserve_entry(),)

    result = await service_with(unit).release_reservation(release_command())

    request = unit.balances.requests[0]
    assert request.available_units == 10_000
    assert request.reserved_units == 0
    assert request.committed_units == 0
    assert result.entry_type is LedgerEntryType.USAGE_RELEASE


@pytest.mark.asyncio
async def test_commit_requires_reserve_entry() -> None:
    unit = FakeUnitOfWork(
        (
            snapshot(
                available=8_000,
                reserved=2_000,
            ),
            4,
        )
    )

    with pytest.raises(
        EntitlementReservationLifecycleError,
        match="requires one reserve",
    ):
        await service_with(unit).commit_reservation(commit_command())


@pytest.mark.asyncio
async def test_finalization_rejects_different_units() -> None:
    unit = FakeUnitOfWork(
        (
            snapshot(
                available=8_000,
                reserved=2_000,
            ),
            4,
        )
    )
    unit.reservations.lifecycle = (reserve_entry(units=2_000),)

    with pytest.raises(
        EntitlementReservationLifecycleError,
        match="must equal reserved",
    ):
        await service_with(unit).commit_reservation(commit_command(units=1_000))


@pytest.mark.asyncio
async def test_finalization_rejects_second_terminal_entry() -> None:
    unit = FakeUnitOfWork(
        (
            snapshot(
                available=8_000,
                reserved=2_000,
            ),
            4,
        )
    )
    terminal = EntitlementLedgerEntry(
        entry_id=FINAL_ENTRY_ID,
        tenant_id=TENANT_ID,
        subscription_id=SUBSCRIPTION_ID,
        entry_type=LedgerEntryType.USAGE_COMMIT,
        units=2_000,
        idempotency_key="commit:previous",
        occurred_at=NOW,
        source_reference="job://1",
        reservation_id=RESERVATION_ID,
    )
    unit.reservations.lifecycle = (
        reserve_entry(),
        terminal,
    )

    with pytest.raises(
        EntitlementReservationLifecycleError,
        match="already finalized",
    ):
        await service_with(unit).release_reservation(release_command())


@pytest.mark.asyncio
async def test_balance_cas_conflict_rolls_back() -> None:
    unit = FakeUnitOfWork((snapshot(), 3))
    unit.balances.cas_updated = False

    with pytest.raises(
        EntitlementBalanceConflictError,
        match="compare-and-swap",
    ):
        await service_with(unit).reserve_units(reserve_command())

    assert unit.rollback_count == 1
    assert unit.commit_count == 0


@pytest.mark.asyncio
async def test_duplicate_returns_persisted_balance_without_append() -> None:
    unit = FakeUnitOfWork(
        (
            snapshot(
                available=8_000,
                reserved=2_000,
            ),
            4,
        )
    )
    unit.ledger.duplicate = reserve_entry()

    result = await service_with(unit).reserve_units(reserve_command())

    assert result.duplicate is True
    assert result.entry_id == RESERVE_ENTRY_ID
    assert result.resulting_balance_version == 4
    assert unit.ledger.appended == []
    assert unit.balances.requests == []
    assert unit.commit_count == 1
