from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

import pytest

from processual_api.billing.commercial_entitlement_ledger_contracts import (
    EntitlementLedgerEntry,
    LedgerEntryType,
)
from processual_api.billing.commercial_entitlement_ledger_models import (
    CommercialEntitlementBalance,
    CommercialEntitlementLedgerEntry,
    CommercialEntitlementReservationLock,
)
from processual_api.billing.commercial_entitlement_ledger_persistence_contracts import (
    BalanceCompareAndSwapRequest,
    EntitlementBalanceRepository,
    EntitlementLedgerRepository,
    EntitlementLedgerUnitOfWork,
    EntitlementReservationRepository,
    LedgerAppendRequest,
    ReservationLock,
    ReservationLockRequest,
)
from processual_api.billing.commercial_entitlement_ledger_repositories import (
    ENTITLEMENT_LEDGER_SQLALCHEMY_LOCKING_ENABLED,
    ENTITLEMENT_LEDGER_SQLALCHEMY_REPOSITORIES_ENABLED,
    ENTITLEMENT_LEDGER_SQLALCHEMY_WRITES_ENABLED,
    EntitlementLedgerPersistenceConflictError,
    EntitlementReservationLockOwnershipError,
    SqlAlchemyEntitlementBalanceRepository,
    SqlAlchemyEntitlementLedgerRepository,
    SqlAlchemyEntitlementReservationRepository,
)
from processual_api.billing.commercial_entitlement_ledger_unit_of_work import (
    ENTITLEMENT_LEDGER_RUNTIME_UOW_WIRING_ENABLED,
    ENTITLEMENT_LEDGER_SQLALCHEMY_UOW_ENABLED,
    SqlAlchemyEntitlementLedgerUnitOfWork,
)

TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")
SUBSCRIPTION_ID = UUID("22222222-2222-2222-2222-222222222222")
ENTRY_ID = UUID("33333333-3333-3333-3333-333333333333")
RESERVATION_ID = UUID("44444444-4444-4444-4444-444444444444")
NOW = datetime(2026, 7, 30, 11, 30, tzinfo=UTC)


class ScalarCollection:
    def __init__(self, values: list[object]) -> None:
        self._values = values

    def all(self) -> list[object]:
        return self._values


class FakeAsyncSession:
    def __init__(
        self,
        *,
        scalar_values: list[object | None] | None = None,
        scalar_collections: list[list[object]] | None = None,
        rowcounts: list[int] | None = None,
    ) -> None:
        self.scalar_values = list(scalar_values or [])
        self.scalar_collections = list(scalar_collections or [])
        self.rowcounts = list(rowcounts or [])
        self.added: list[object] = []
        self.deleted: list[object] = []
        self.statements: list[object] = []
        self.flush_count = 0
        self.commit_count = 0
        self.rollback_count = 0
        self.close_count = 0

    async def scalar(self, statement: object) -> object | None:
        self.statements.append(statement)
        return self.scalar_values.pop(0)

    async def scalars(
        self,
        statement: object,
    ) -> ScalarCollection:
        self.statements.append(statement)
        return ScalarCollection(self.scalar_collections.pop(0))

    async def execute(self, statement: object) -> object:
        self.statements.append(statement)
        return SimpleNamespace(rowcount=self.rowcounts.pop(0))

    def add(self, model: object) -> None:
        self.added.append(model)

    async def delete(self, model: object) -> None:
        self.deleted.append(model)

    async def flush(self) -> None:
        self.flush_count += 1

    async def commit(self) -> None:
        self.commit_count += 1

    async def rollback(self) -> None:
        self.rollback_count += 1

    async def close(self) -> None:
        self.close_count += 1


def domain_entry() -> EntitlementLedgerEntry:
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


def ledger_model() -> CommercialEntitlementLedgerEntry:
    return CommercialEntitlementLedgerEntry(
        entry_id=ENTRY_ID,
        tenant_id=TENANT_ID,
        subscription_id=SUBSCRIPTION_ID,
        entry_type=LedgerEntryType.MONTHLY_GRANT.value,
        units=10_000,
        idempotency_key="monthly:2026-07",
        source_reference="billing-cycle:2026-07",
        occurred_at=NOW,
    )


def lock_request(
    owner_token: str,
) -> ReservationLockRequest:
    return ReservationLockRequest(
        tenant_id=TENANT_ID,
        subscription_id=SUBSCRIPTION_ID,
        reservation_id=RESERVATION_ID,
        owner_token=owner_token,
        lease_seconds=30,
    )


def test_runtime_flags_remain_disabled() -> None:
    assert ENTITLEMENT_LEDGER_SQLALCHEMY_REPOSITORIES_ENABLED is False
    assert ENTITLEMENT_LEDGER_SQLALCHEMY_WRITES_ENABLED is False
    assert ENTITLEMENT_LEDGER_SQLALCHEMY_LOCKING_ENABLED is False
    assert ENTITLEMENT_LEDGER_SQLALCHEMY_UOW_ENABLED is False
    assert ENTITLEMENT_LEDGER_RUNTIME_UOW_WIRING_ENABLED is False


def test_repositories_satisfy_protocols() -> None:
    session = FakeAsyncSession()

    assert isinstance(
        SqlAlchemyEntitlementLedgerRepository(session),
        EntitlementLedgerRepository,
    )
    assert isinstance(
        SqlAlchemyEntitlementBalanceRepository(session),
        EntitlementBalanceRepository,
    )
    assert isinstance(
        SqlAlchemyEntitlementReservationRepository(session),
        EntitlementReservationRepository,
    )


@pytest.mark.asyncio
async def test_active_uow_satisfies_protocol() -> None:
    session = FakeAsyncSession()
    uow = SqlAlchemyEntitlementLedgerUnitOfWork(lambda: session)

    async with uow:
        assert isinstance(
            uow,
            EntitlementLedgerUnitOfWork,
        )
        await uow.commit()


@pytest.mark.asyncio
async def test_idempotency_lookup_maps_model_to_domain() -> None:
    session = FakeAsyncSession(scalar_values=[ledger_model()])
    repository = SqlAlchemyEntitlementLedgerRepository(session)

    result = await repository.get_by_idempotency_key(
        tenant_id=TENANT_ID,
        subscription_id=SUBSCRIPTION_ID,
        idempotency_key="monthly:2026-07",
    )

    assert result == domain_entry()


@pytest.mark.asyncio
async def test_append_adds_new_entry_after_version_check() -> None:
    session = FakeAsyncSession(scalar_values=[None, 0])
    repository = SqlAlchemyEntitlementLedgerRepository(session)

    result = await repository.append(
        LedgerAppendRequest(
            entry=domain_entry(),
            expected_balance_version=0,
        )
    )

    assert result.appended is True
    assert result.duplicate is False
    assert len(session.added) == 1
    assert isinstance(
        session.added[0],
        CommercialEntitlementLedgerEntry,
    )
    assert session.flush_count == 1


@pytest.mark.asyncio
async def test_append_returns_duplicate_without_writing() -> None:
    session = FakeAsyncSession(scalar_values=[ledger_model(), 4])
    repository = SqlAlchemyEntitlementLedgerRepository(session)

    result = await repository.append(
        LedgerAppendRequest(
            entry=domain_entry(),
            expected_balance_version=4,
        )
    )

    assert result.appended is False
    assert result.duplicate is True
    assert result.resulting_balance_version == 4
    assert session.added == []
    assert session.flush_count == 0


@pytest.mark.asyncio
async def test_append_rejects_version_conflict() -> None:
    session = FakeAsyncSession(scalar_values=[None, 5])
    repository = SqlAlchemyEntitlementLedgerRepository(session)

    with pytest.raises(
        EntitlementLedgerPersistenceConflictError,
        match="expected balance version",
    ):
        await repository.append(
            LedgerAppendRequest(
                entry=domain_entry(),
                expected_balance_version=4,
            )
        )


@pytest.mark.asyncio
async def test_compare_and_swap_updates_matching_row() -> None:
    session = FakeAsyncSession(rowcounts=[1])
    repository = SqlAlchemyEntitlementBalanceRepository(session)

    result = await repository.compare_and_swap(
        BalanceCompareAndSwapRequest(
            tenant_id=TENANT_ID,
            subscription_id=SUBSCRIPTION_ID,
            expected_version=3,
            available_units=8_000,
            reserved_units=1_000,
            committed_units=1_000,
            calculated_at=NOW,
        )
    )

    assert result.updated is True
    assert result.previous_version == 3
    assert result.resulting_version == 4


@pytest.mark.asyncio
async def test_compare_and_swap_reports_mismatch() -> None:
    session = FakeAsyncSession(
        scalar_values=[5],
        rowcounts=[0],
    )
    repository = SqlAlchemyEntitlementBalanceRepository(session)

    result = await repository.compare_and_swap(
        BalanceCompareAndSwapRequest(
            tenant_id=TENANT_ID,
            subscription_id=SUBSCRIPTION_ID,
            expected_version=3,
            available_units=8_000,
            reserved_units=1_000,
            committed_units=1_000,
            calculated_at=NOW,
        )
    )

    assert result.updated is False
    assert result.previous_version == 5
    assert result.resulting_version == 5


@pytest.mark.asyncio
async def test_compare_and_swap_inserts_initial_balance() -> None:
    session = FakeAsyncSession(
        scalar_values=[None],
        rowcounts=[0],
    )
    repository = SqlAlchemyEntitlementBalanceRepository(session)

    result = await repository.compare_and_swap(
        BalanceCompareAndSwapRequest(
            tenant_id=TENANT_ID,
            subscription_id=SUBSCRIPTION_ID,
            expected_version=0,
            available_units=10_000,
            reserved_units=0,
            committed_units=0,
            calculated_at=NOW,
        )
    )

    assert result.updated is True
    assert result.resulting_version == 1
    assert len(session.added) == 1
    assert isinstance(
        session.added[0],
        CommercialEntitlementBalance,
    )
    assert session.flush_count == 1


@pytest.mark.asyncio
async def test_active_lock_blocks_other_owner() -> None:
    existing = CommercialEntitlementReservationLock(
        tenant_id=TENANT_ID,
        subscription_id=SUBSCRIPTION_ID,
        reservation_id=RESERVATION_ID,
        owner_token="worker-1",
        expires_at=NOW + timedelta(seconds=30),
        created_at=NOW,
        updated_at=NOW,
    )
    session = FakeAsyncSession(scalar_values=[existing])
    repository = SqlAlchemyEntitlementReservationRepository(
        session,
        now_provider=lambda: NOW,
    )

    result = await repository.acquire_lock(lock_request("worker-2"))

    assert result.acquired is False
    assert session.flush_count == 0


@pytest.mark.asyncio
async def test_expired_lock_is_reassigned() -> None:
    existing = CommercialEntitlementReservationLock(
        tenant_id=TENANT_ID,
        subscription_id=SUBSCRIPTION_ID,
        reservation_id=RESERVATION_ID,
        owner_token="worker-1",
        expires_at=NOW - timedelta(seconds=1),
        created_at=NOW - timedelta(seconds=60),
        updated_at=NOW - timedelta(seconds=60),
    )
    session = FakeAsyncSession(scalar_values=[existing])
    repository = SqlAlchemyEntitlementReservationRepository(
        session,
        now_provider=lambda: NOW,
    )

    result = await repository.acquire_lock(lock_request("worker-2"))

    assert result.acquired is True
    assert existing.owner_token == "worker-2"
    assert session.flush_count == 1


@pytest.mark.asyncio
async def test_foreign_owner_cannot_release_lock() -> None:
    existing = CommercialEntitlementReservationLock(
        tenant_id=TENANT_ID,
        subscription_id=SUBSCRIPTION_ID,
        reservation_id=RESERVATION_ID,
        owner_token="worker-1",
        expires_at=NOW + timedelta(seconds=30),
        created_at=NOW,
        updated_at=NOW,
    )
    session = FakeAsyncSession(scalar_values=[existing])
    repository = SqlAlchemyEntitlementReservationRepository(session)

    with pytest.raises(
        EntitlementReservationLockOwnershipError,
        match="only by its owner",
    ):
        await repository.release_lock(
            ReservationLock(
                tenant_id=TENANT_ID,
                subscription_id=SUBSCRIPTION_ID,
                reservation_id=RESERVATION_ID,
                owner_token="worker-2",
                acquired=True,
                expires_at=existing.expires_at,
            )
        )


@pytest.mark.asyncio
async def test_owner_releases_lock() -> None:
    existing = CommercialEntitlementReservationLock(
        tenant_id=TENANT_ID,
        subscription_id=SUBSCRIPTION_ID,
        reservation_id=RESERVATION_ID,
        owner_token="worker-1",
        expires_at=NOW + timedelta(seconds=30),
        created_at=NOW,
        updated_at=NOW,
    )
    session = FakeAsyncSession(scalar_values=[existing])
    repository = SqlAlchemyEntitlementReservationRepository(session)

    await repository.release_lock(
        ReservationLock(
            tenant_id=TENANT_ID,
            subscription_id=SUBSCRIPTION_ID,
            reservation_id=RESERVATION_ID,
            owner_token="worker-1",
            acquired=True,
            expires_at=existing.expires_at,
        )
    )

    assert session.deleted == [existing]
    assert session.flush_count == 1


@pytest.mark.asyncio
async def test_uow_commit_and_close() -> None:
    session = FakeAsyncSession()
    uow = SqlAlchemyEntitlementLedgerUnitOfWork(
        lambda: session,
        now_provider=lambda: NOW,
    )

    async with uow:
        await uow.commit()

    assert session.commit_count == 1
    assert session.rollback_count == 0
    assert session.close_count == 1


@pytest.mark.asyncio
async def test_uow_rolls_back_without_commit() -> None:
    session = FakeAsyncSession()
    uow = SqlAlchemyEntitlementLedgerUnitOfWork(lambda: session)

    async with uow:
        pass

    assert session.commit_count == 0
    assert session.rollback_count == 1
    assert session.close_count == 1


@pytest.mark.asyncio
async def test_uow_rolls_back_on_exception() -> None:
    session = FakeAsyncSession()
    uow = SqlAlchemyEntitlementLedgerUnitOfWork(lambda: session)

    with pytest.raises(RuntimeError, match="forced failure"):
        async with uow:
            raise RuntimeError("forced failure")

    assert session.rollback_count == 1
    assert session.close_count == 1
