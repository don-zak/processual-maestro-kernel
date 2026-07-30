from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from processual_api.billing.commercial_entitlement_ledger_contracts import (
    EntitlementLedgerEntry,
    LedgerEntryType,
)
from processual_api.billing.commercial_entitlement_ledger_in_memory import (
    IN_MEMORY_ENTITLEMENT_PRODUCTION_USE_ALLOWED,
    IN_MEMORY_ENTITLEMENT_RUNTIME_ENABLED,
    InMemoryEntitlementLedgerUnitOfWork,
    InMemoryEntitlementLockOwnershipError,
    InMemoryEntitlementState,
    InMemoryEntitlementVersionConflictError,
    in_memory_entitlement_reference_payload,
)
from processual_api.billing.commercial_entitlement_ledger_persistence_contracts import (
    BalanceCompareAndSwapRequest,
    EntitlementLedgerUnitOfWork,
    LedgerAppendRequest,
    ReservationLock,
    ReservationLockRequest,
)

TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")
SUBSCRIPTION_ID = UUID("22222222-2222-2222-2222-222222222222")
RESERVATION_ID = UUID("33333333-3333-3333-3333-333333333333")
NOW = datetime(2026, 7, 30, 10, 45, tzinfo=UTC)


def entry(
    *,
    entry_id: str,
    idempotency_key: str,
    entry_type: LedgerEntryType = LedgerEntryType.MONTHLY_GRANT,
    reservation_id: UUID | None = None,
) -> EntitlementLedgerEntry:
    return EntitlementLedgerEntry(
        entry_id=UUID(entry_id),
        tenant_id=TENANT_ID,
        subscription_id=SUBSCRIPTION_ID,
        entry_type=entry_type,
        units=10_000,
        idempotency_key=idempotency_key,
        occurred_at=NOW,
        source_reference="test://in-memory",
        reservation_id=reservation_id,
    )


def balance_request(
    *,
    expected_version: int,
    available_units: int = 10_000,
) -> BalanceCompareAndSwapRequest:
    return BalanceCompareAndSwapRequest(
        tenant_id=TENANT_ID,
        subscription_id=SUBSCRIPTION_ID,
        expected_version=expected_version,
        available_units=available_units,
        reserved_units=0,
        committed_units=0,
        calculated_at=NOW,
    )


def lock_request(
    *,
    owner_token: str,
    lease_seconds: int = 30,
) -> ReservationLockRequest:
    return ReservationLockRequest(
        tenant_id=TENANT_ID,
        subscription_id=SUBSCRIPTION_ID,
        reservation_id=RESERVATION_ID,
        owner_token=owner_token,
        lease_seconds=lease_seconds,
    )


def test_in_memory_reference_is_not_production_runtime() -> None:
    payload = in_memory_entitlement_reference_payload()

    assert IN_MEMORY_ENTITLEMENT_RUNTIME_ENABLED is False
    assert IN_MEMORY_ENTITLEMENT_PRODUCTION_USE_ALLOWED is False
    assert payload["status"] == "test_reference"
    assert payload["runtime_enabled"] is False
    assert payload["production_use_allowed"] is False
    assert payload["durable_storage"] is False


def test_uow_satisfies_persistence_protocol() -> None:
    assert isinstance(
        InMemoryEntitlementLedgerUnitOfWork(),
        EntitlementLedgerUnitOfWork,
    )


@pytest.mark.asyncio
async def test_append_and_idempotent_retry() -> None:
    uow = InMemoryEntitlementLedgerUnitOfWork()
    ledger_entry = entry(
        entry_id="44444444-4444-4444-4444-444444444444",
        idempotency_key="monthly:2026-07",
    )
    request = LedgerAppendRequest(
        entry=ledger_entry,
        expected_balance_version=0,
    )

    async with uow:
        first = await uow.ledger.append(request)
        second = await uow.ledger.append(request)
        await uow.commit()

    assert first.appended is True
    assert first.duplicate is False
    assert second.appended is False
    assert second.duplicate is True
    assert second.entry_id == ledger_entry.entry_id


@pytest.mark.asyncio
async def test_same_idempotency_key_is_scoped_by_subscription() -> None:
    state = InMemoryEntitlementState()
    first_uow = InMemoryEntitlementLedgerUnitOfWork(state)

    first = entry(
        entry_id="44444444-4444-4444-4444-444444444444",
        idempotency_key="monthly:shared",
    )

    async with first_uow:
        result = await first_uow.ledger.append(
            LedgerAppendRequest(
                entry=first,
                expected_balance_version=0,
            )
        )
        await first_uow.commit()

    assert result.appended is True


@pytest.mark.asyncio
async def test_append_rejects_outdated_balance_version() -> None:
    uow = InMemoryEntitlementLedgerUnitOfWork()

    async with uow:
        updated = await uow.balances.compare_and_swap(balance_request(expected_version=0))
        assert updated.updated is True

        with pytest.raises(
            InMemoryEntitlementVersionConflictError,
            match="expected balance version",
        ):
            await uow.ledger.append(
                LedgerAppendRequest(
                    entry=entry(
                        entry_id=("44444444-4444-4444-4444-444444444444"),
                        idempotency_key="monthly:stale",
                    ),
                    expected_balance_version=0,
                )
            )


@pytest.mark.asyncio
async def test_compare_and_swap_updates_snapshot_once() -> None:
    uow = InMemoryEntitlementLedgerUnitOfWork()

    async with uow:
        first = await uow.balances.compare_and_swap(balance_request(expected_version=0))
        second = await uow.balances.compare_and_swap(
            balance_request(
                expected_version=0,
                available_units=9_000,
            )
        )
        await uow.commit()

    assert first.updated is True
    assert first.previous_version == 0
    assert first.resulting_version == 1
    assert second.updated is False
    assert second.previous_version == 1
    assert second.resulting_version == 1


@pytest.mark.asyncio
async def test_committed_uow_preserves_state() -> None:
    state = InMemoryEntitlementState()
    uow = InMemoryEntitlementLedgerUnitOfWork(state)

    async with uow:
        await uow.balances.compare_and_swap(balance_request(expected_version=0))
        await uow.commit()

    reader = InMemoryEntitlementLedgerUnitOfWork(state)

    async with reader:
        stored = await reader.balances.get_snapshot(
            tenant_id=TENANT_ID,
            subscription_id=SUBSCRIPTION_ID,
        )

    assert stored is not None
    snapshot, version = stored
    assert snapshot.available_units == 10_000
    assert version == 1


@pytest.mark.asyncio
async def test_uncommitted_uow_rolls_back() -> None:
    state = InMemoryEntitlementState()
    uow = InMemoryEntitlementLedgerUnitOfWork(state)

    async with uow:
        await uow.balances.compare_and_swap(balance_request(expected_version=0))

    reader = InMemoryEntitlementLedgerUnitOfWork(state)

    async with reader:
        stored = await reader.balances.get_snapshot(
            tenant_id=TENANT_ID,
            subscription_id=SUBSCRIPTION_ID,
        )

    assert stored is None


@pytest.mark.asyncio
async def test_exception_rolls_back_ledger_append() -> None:
    state = InMemoryEntitlementState()
    uow = InMemoryEntitlementLedgerUnitOfWork(state)

    with pytest.raises(RuntimeError, match="forced failure"):
        async with uow:
            await uow.ledger.append(
                LedgerAppendRequest(
                    entry=entry(
                        entry_id=("44444444-4444-4444-4444-444444444444"),
                        idempotency_key="monthly:rollback",
                    ),
                    expected_balance_version=0,
                )
            )
            raise RuntimeError("forced failure")

    reader = InMemoryEntitlementLedgerUnitOfWork(state)

    async with reader:
        entries = await reader.ledger.list_for_subscription(
            tenant_id=TENANT_ID,
            subscription_id=SUBSCRIPTION_ID,
        )

    assert entries == ()


@pytest.mark.asyncio
async def test_active_lock_rejects_other_owner() -> None:
    uow = InMemoryEntitlementLedgerUnitOfWork(now_provider=lambda: NOW)

    async with uow:
        first = await uow.reservations.acquire_lock(lock_request(owner_token="worker-1"))
        second = await uow.reservations.acquire_lock(lock_request(owner_token="worker-2"))
        await uow.commit()

    assert first.acquired is True
    assert second.acquired is False
    assert second.expires_at == NOW + timedelta(seconds=30)


@pytest.mark.asyncio
async def test_same_owner_can_refresh_lock() -> None:
    uow = InMemoryEntitlementLedgerUnitOfWork(now_provider=lambda: NOW)

    async with uow:
        first = await uow.reservations.acquire_lock(lock_request(owner_token="worker-1"))
        refreshed = await uow.reservations.acquire_lock(
            lock_request(
                owner_token="worker-1",
                lease_seconds=60,
            )
        )
        await uow.commit()

    assert first.acquired is True
    assert refreshed.acquired is True
    assert refreshed.expires_at == NOW + timedelta(seconds=60)


@pytest.mark.asyncio
async def test_expired_lock_can_be_reacquired() -> None:
    current = NOW

    def now_provider() -> datetime:
        return current

    state = InMemoryEntitlementState()
    first_uow = InMemoryEntitlementLedgerUnitOfWork(
        state,
        now_provider=now_provider,
    )

    async with first_uow:
        first = await first_uow.reservations.acquire_lock(
            lock_request(
                owner_token="worker-1",
                lease_seconds=30,
            )
        )
        await first_uow.commit()

    assert first.acquired is True

    current = NOW + timedelta(seconds=31)

    second_uow = InMemoryEntitlementLedgerUnitOfWork(
        state,
        now_provider=now_provider,
    )

    async with second_uow:
        second = await second_uow.reservations.acquire_lock(lock_request(owner_token="worker-2"))
        await second_uow.commit()

    assert second.acquired is True
    assert second.owner_token == "worker-2"


@pytest.mark.asyncio
async def test_lock_may_be_released_only_by_owner() -> None:
    uow = InMemoryEntitlementLedgerUnitOfWork(now_provider=lambda: NOW)

    async with uow:
        lock = await uow.reservations.acquire_lock(lock_request(owner_token="worker-1"))

        foreign_lock = ReservationLock(
            tenant_id=lock.tenant_id,
            subscription_id=lock.subscription_id,
            reservation_id=lock.reservation_id,
            owner_token="worker-2",
            acquired=True,
            expires_at=lock.expires_at,
        )

        with pytest.raises(
            InMemoryEntitlementLockOwnershipError,
            match="only by its owner",
        ):
            await uow.reservations.release_lock(foreign_lock)


@pytest.mark.asyncio
async def test_owner_can_release_and_another_owner_can_acquire() -> None:
    uow = InMemoryEntitlementLedgerUnitOfWork(now_provider=lambda: NOW)

    async with uow:
        first = await uow.reservations.acquire_lock(lock_request(owner_token="worker-1"))
        await uow.reservations.release_lock(first)

        second = await uow.reservations.acquire_lock(lock_request(owner_token="worker-2"))
        await uow.commit()

    assert second.acquired is True
    assert second.owner_token == "worker-2"


@pytest.mark.asyncio
async def test_reservation_repository_lists_lifecycle_entries() -> None:
    uow = InMemoryEntitlementLedgerUnitOfWork()
    reserve = entry(
        entry_id="55555555-5555-5555-5555-555555555555",
        idempotency_key="reserve:job-1",
        entry_type=LedgerEntryType.USAGE_RESERVE,
        reservation_id=RESERVATION_ID,
    )

    async with uow:
        await uow.ledger.append(
            LedgerAppendRequest(
                entry=reserve,
                expected_balance_version=0,
            )
        )
        lifecycle = await uow.reservations.list_lifecycle_entries(
            tenant_id=TENANT_ID,
            subscription_id=SUBSCRIPTION_ID,
            reservation_id=RESERVATION_ID,
        )
        await uow.commit()

    assert lifecycle == (reserve,)
