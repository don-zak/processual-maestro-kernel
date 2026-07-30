from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from processual_api.billing.commercial_entitlement_ledger_contracts import (
    EntitlementBalanceSnapshot,
    EntitlementLedgerEntry,
    LedgerEntryType,
)
from processual_api.billing.commercial_entitlement_ledger_persistence_contracts import (
    ENTITLEMENT_BALANCE_CAS_ENABLED,
    ENTITLEMENT_LEDGER_DATABASE_WRITES_ENABLED,
    ENTITLEMENT_LEDGER_REPOSITORIES_ENABLED,
    ENTITLEMENT_LEDGER_RUNTIME_INTEGRATION_ENABLED,
    ENTITLEMENT_LEDGER_UOW_ENABLED,
    ENTITLEMENT_RESERVATION_LOCKING_ENABLED,
    BalanceCompareAndSwapRequest,
    BalanceCompareAndSwapResult,
    EntitlementBalanceRepository,
    EntitlementLedgerRepository,
    EntitlementLedgerUnitOfWork,
    EntitlementPersistenceContractError,
    EntitlementReservationRepository,
    LedgerAppendRequest,
    LedgerAppendResult,
    ReservationLock,
    ReservationLockRequest,
    entitlement_ledger_persistence_review_payload,
)

TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")
SUBSCRIPTION_ID = UUID(
    "22222222-2222-2222-2222-222222222222"
)
ENTRY_ID = UUID("33333333-3333-3333-3333-333333333333")
RESERVATION_ID = UUID(
    "44444444-4444-4444-4444-444444444444"
)
NOW = datetime(2026, 7, 30, 10, 30, tzinfo=UTC)


def ledger_entry() -> EntitlementLedgerEntry:
    return EntitlementLedgerEntry(
        entry_id=ENTRY_ID,
        tenant_id=TENANT_ID,
        subscription_id=SUBSCRIPTION_ID,
        entry_type=LedgerEntryType.MONTHLY_GRANT,
        units=10_000,
        idempotency_key="monthly:2026-07",
        occurred_at=NOW,
        source_reference="billing-cycle:2026-07",
    )


class FakeLedgerRepository:
    async def get_by_idempotency_key(
        self,
        *,
        tenant_id: UUID,
        subscription_id: UUID,
        idempotency_key: str,
    ) -> EntitlementLedgerEntry | None:
        del tenant_id
        del subscription_id
        del idempotency_key
        return None

    async def append(
        self,
        request: LedgerAppendRequest,
    ) -> LedgerAppendResult:
        return LedgerAppendResult(
            entry_id=request.entry.entry_id,
            appended=True,
            duplicate=False,
            resulting_balance_version=(
                request.expected_balance_version + 1
            ),
        )

    async def list_for_subscription(
        self,
        *,
        tenant_id: UUID,
        subscription_id: UUID,
        after_entry_id: UUID | None = None,
        limit: int = 100,
    ) -> tuple[EntitlementLedgerEntry, ...]:
        del tenant_id
        del subscription_id
        del after_entry_id
        del limit
        return ()


class FakeBalanceRepository:
    async def get_snapshot(
        self,
        *,
        tenant_id: UUID,
        subscription_id: UUID,
    ) -> tuple[EntitlementBalanceSnapshot, int] | None:
        return (
            EntitlementBalanceSnapshot(
                tenant_id=tenant_id,
                subscription_id=subscription_id,
                available_units=10_000,
                reserved_units=0,
                committed_units=0,
                calculated_at=NOW,
            ),
            0,
        )

    async def compare_and_swap(
        self,
        request: BalanceCompareAndSwapRequest,
    ) -> BalanceCompareAndSwapResult:
        return BalanceCompareAndSwapResult(
            updated=True,
            previous_version=request.expected_version,
            resulting_version=request.expected_version + 1,
        )


class FakeReservationRepository:
    async def acquire_lock(
        self,
        request: ReservationLockRequest,
    ) -> ReservationLock:
        return ReservationLock(
            tenant_id=request.tenant_id,
            subscription_id=request.subscription_id,
            reservation_id=request.reservation_id,
            owner_token=request.owner_token,
            acquired=True,
            expires_at=NOW + timedelta(
                seconds=request.lease_seconds
            ),
        )

    async def release_lock(
        self,
        lock: ReservationLock,
    ) -> None:
        del lock

    async def list_lifecycle_entries(
        self,
        *,
        tenant_id: UUID,
        subscription_id: UUID,
        reservation_id: UUID,
    ) -> tuple[EntitlementLedgerEntry, ...]:
        del tenant_id
        del subscription_id
        del reservation_id
        return ()


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.ledger = FakeLedgerRepository()
        self.balances = FakeBalanceRepository()
        self.reservations = FakeReservationRepository()
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self) -> FakeUnitOfWork:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object | None,
    ) -> None:
        del exc_value
        del traceback

        if exc_type is not None:
            await self.rollback()

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


def test_persistence_runtime_remains_disabled() -> None:
    payload = entitlement_ledger_persistence_review_payload()

    assert ENTITLEMENT_LEDGER_REPOSITORIES_ENABLED is False
    assert ENTITLEMENT_LEDGER_UOW_ENABLED is False
    assert ENTITLEMENT_LEDGER_DATABASE_WRITES_ENABLED is False
    assert ENTITLEMENT_BALANCE_CAS_ENABLED is False
    assert ENTITLEMENT_RESERVATION_LOCKING_ENABLED is False
    assert ENTITLEMENT_LEDGER_RUNTIME_INTEGRATION_ENABLED is False

    assert payload["status"] == "draft_review"
    assert payload["repositories_enabled"] is False
    assert payload["unit_of_work_enabled"] is False
    assert payload["database_writes_enabled"] is False
    assert payload["runtime_integration_enabled"] is False


def test_fake_repositories_satisfy_runtime_protocols() -> None:
    assert isinstance(
        FakeLedgerRepository(),
        EntitlementLedgerRepository,
    )
    assert isinstance(
        FakeBalanceRepository(),
        EntitlementBalanceRepository,
    )
    assert isinstance(
        FakeReservationRepository(),
        EntitlementReservationRepository,
    )
    assert isinstance(
        FakeUnitOfWork(),
        EntitlementLedgerUnitOfWork,
    )


def test_append_request_requires_non_negative_version() -> None:
    with pytest.raises(
        EntitlementPersistenceContractError,
        match="must not be negative",
    ):
        LedgerAppendRequest(
            entry=ledger_entry(),
            expected_balance_version=-1,
        )


def test_append_result_rejects_conflicting_outcome() -> None:
    with pytest.raises(
        EntitlementPersistenceContractError,
        match="cannot be appended and duplicate",
    ):
        LedgerAppendResult(
            entry_id=ENTRY_ID,
            appended=True,
            duplicate=True,
            resulting_balance_version=1,
        )


def test_append_result_requires_terminal_outcome() -> None:
    with pytest.raises(
        EntitlementPersistenceContractError,
        match="must be appended or duplicate",
    ):
        LedgerAppendResult(
            entry_id=ENTRY_ID,
            appended=False,
            duplicate=False,
            resulting_balance_version=0,
        )


def test_successful_compare_and_swap_increments_once() -> None:
    result = BalanceCompareAndSwapResult(
        updated=True,
        previous_version=4,
        resulting_version=5,
    )

    assert result.updated is True
    assert result.resulting_version == 5


def test_successful_compare_and_swap_rejects_version_jump() -> None:
    with pytest.raises(
        EntitlementPersistenceContractError,
        match="increment version once",
    ):
        BalanceCompareAndSwapResult(
            updated=True,
            previous_version=4,
            resulting_version=6,
        )


def test_failed_compare_and_swap_preserves_version() -> None:
    result = BalanceCompareAndSwapResult(
        updated=False,
        previous_version=4,
        resulting_version=4,
    )

    assert result.updated is False


def test_failed_compare_and_swap_rejects_version_change() -> None:
    with pytest.raises(
        EntitlementPersistenceContractError,
        match="must preserve version",
    ):
        BalanceCompareAndSwapResult(
            updated=False,
            previous_version=4,
            resulting_version=5,
        )


def test_balance_request_rejects_negative_values() -> None:
    with pytest.raises(
        EntitlementPersistenceContractError,
        match="balance values must not be negative",
    ):
        BalanceCompareAndSwapRequest(
            tenant_id=TENANT_ID,
            subscription_id=SUBSCRIPTION_ID,
            expected_version=0,
            available_units=-1,
            reserved_units=0,
            committed_units=0,
            calculated_at=NOW,
        )


def test_reservation_lock_request_requires_owner_token() -> None:
    with pytest.raises(
        EntitlementPersistenceContractError,
        match="owner_token must not be blank",
    ):
        ReservationLockRequest(
            tenant_id=TENANT_ID,
            subscription_id=SUBSCRIPTION_ID,
            reservation_id=RESERVATION_ID,
            owner_token=" ",
            lease_seconds=30,
        )


def test_acquired_lock_requires_expiration() -> None:
    with pytest.raises(
        EntitlementPersistenceContractError,
        match="requires expires_at",
    ):
        ReservationLock(
            tenant_id=TENANT_ID,
            subscription_id=SUBSCRIPTION_ID,
            reservation_id=RESERVATION_ID,
            owner_token="worker-1",
            acquired=True,
            expires_at=None,
        )


@pytest.mark.asyncio
async def test_uow_commit_boundary() -> None:
    uow = FakeUnitOfWork()

    async with uow:
        await uow.commit()

    assert uow.committed is True
    assert uow.rolled_back is False


@pytest.mark.asyncio
async def test_uow_rolls_back_on_exception() -> None:
    uow = FakeUnitOfWork()

    with pytest.raises(RuntimeError, match="forced failure"):
        async with uow:
            raise RuntimeError("forced failure")

    assert uow.committed is False
    assert uow.rolled_back is True


@pytest.mark.asyncio
async def test_repository_append_preserves_expected_version_contract() -> None:
    repository = FakeLedgerRepository()
    request = LedgerAppendRequest(
        entry=ledger_entry(),
        expected_balance_version=7,
    )

    result = await repository.append(request)

    assert result.appended is True
    assert result.duplicate is False
    assert result.resulting_balance_version == 8


@pytest.mark.asyncio
async def test_reservation_lock_contract() -> None:
    repository = FakeReservationRepository()
    request = ReservationLockRequest(
        tenant_id=TENANT_ID,
        subscription_id=SUBSCRIPTION_ID,
        reservation_id=RESERVATION_ID,
        owner_token="worker-1",
        lease_seconds=30,
    )

    lock = await repository.acquire_lock(request)

    assert lock.acquired is True
    assert lock.owner_token == "worker-1"
    assert lock.expires_at == NOW + timedelta(seconds=30)
