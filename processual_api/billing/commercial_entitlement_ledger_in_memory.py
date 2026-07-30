"""In-memory reference persistence for entitlement-ledger tests.

This module proves repository, idempotency, compare-and-swap, reservation-lock,
and unit-of-work semantics before SQLAlchemy persistence is designed. It is not
a production store and is not connected to commercial runtime execution.
"""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Final
from uuid import UUID

from processual_api.billing.commercial_entitlement_ledger_contracts import (
    EntitlementBalanceSnapshot,
    EntitlementLedgerEntry,
)
from processual_api.billing.commercial_entitlement_ledger_persistence_contracts import (
    BalanceCompareAndSwapRequest,
    BalanceCompareAndSwapResult,
    LedgerAppendRequest,
    LedgerAppendResult,
    ReservationLock,
    ReservationLockRequest,
)

IN_MEMORY_ENTITLEMENT_REFERENCE_VERSION: Final = (
    "2026-07-group2-entitlement-in-memory-v1"
)
IN_MEMORY_ENTITLEMENT_REFERENCE_STATUS: Final = "test_reference"

IN_MEMORY_ENTITLEMENT_RUNTIME_ENABLED: Final = False
IN_MEMORY_ENTITLEMENT_PRODUCTION_USE_ALLOWED: Final = False


class InMemoryEntitlementPersistenceError(RuntimeError):
    """Base error for the in-memory reference implementation."""


class InMemoryEntitlementVersionConflictError(
    InMemoryEntitlementPersistenceError
):
    """Raised when an append uses an outdated balance version."""


class InMemoryEntitlementLockOwnershipError(
    InMemoryEntitlementPersistenceError
):
    """Raised when a caller releases a lock owned by another token."""


@dataclass(slots=True)
class InMemoryEntitlementState:
    entries: dict[
        tuple[UUID, UUID],
        list[EntitlementLedgerEntry],
    ] = field(default_factory=dict)
    entries_by_idempotency: dict[
        tuple[UUID, UUID, str],
        EntitlementLedgerEntry,
    ] = field(default_factory=dict)
    snapshots: dict[
        tuple[UUID, UUID],
        EntitlementBalanceSnapshot,
    ] = field(default_factory=dict)
    versions: dict[
        tuple[UUID, UUID],
        int,
    ] = field(default_factory=dict)
    locks: dict[
        tuple[UUID, UUID, UUID],
        ReservationLock,
    ] = field(default_factory=dict)


def _scope_key(
    tenant_id: UUID,
    subscription_id: UUID,
) -> tuple[UUID, UUID]:
    return tenant_id, subscription_id


def _reservation_key(
    tenant_id: UUID,
    subscription_id: UUID,
    reservation_id: UUID,
) -> tuple[UUID, UUID, UUID]:
    return tenant_id, subscription_id, reservation_id


class InMemoryEntitlementLedgerRepository:
    def __init__(
        self,
        state: InMemoryEntitlementState,
    ) -> None:
        self._state = state

    async def get_by_idempotency_key(
        self,
        *,
        tenant_id: UUID,
        subscription_id: UUID,
        idempotency_key: str,
    ) -> EntitlementLedgerEntry | None:
        return self._state.entries_by_idempotency.get(
            (
                tenant_id,
                subscription_id,
                idempotency_key,
            )
        )

    async def append(
        self,
        request: LedgerAppendRequest,
    ) -> LedgerAppendResult:
        entry = request.entry
        scope = _scope_key(
            entry.tenant_id,
            entry.subscription_id,
        )
        idempotency_identity = (
            entry.tenant_id,
            entry.subscription_id,
            entry.idempotency_key,
        )

        existing = self._state.entries_by_idempotency.get(
            idempotency_identity
        )
        current_version = self._state.versions.get(scope, 0)

        if existing is not None:
            return LedgerAppendResult(
                entry_id=existing.entry_id,
                appended=False,
                duplicate=True,
                resulting_balance_version=current_version,
            )

        if request.expected_balance_version != current_version:
            raise InMemoryEntitlementVersionConflictError(
                "ledger append expected balance version does not match "
                "the current version"
            )

        self._state.entries.setdefault(scope, []).append(entry)
        self._state.entries_by_idempotency[
            idempotency_identity
        ] = entry

        return LedgerAppendResult(
            entry_id=entry.entry_id,
            appended=True,
            duplicate=False,
            resulting_balance_version=current_version,
        )

    async def list_for_subscription(
        self,
        *,
        tenant_id: UUID,
        subscription_id: UUID,
        after_entry_id: UUID | None = None,
        limit: int = 100,
    ) -> tuple[EntitlementLedgerEntry, ...]:
        if limit <= 0:
            raise ValueError("limit must be positive")

        entries = self._state.entries.get(
            _scope_key(tenant_id, subscription_id),
            [],
        )

        start_index = 0

        if after_entry_id is not None:
            for index, entry in enumerate(entries):
                if entry.entry_id == after_entry_id:
                    start_index = index + 1
                    break

        return tuple(
            entries[start_index : start_index + limit]
        )


class InMemoryEntitlementBalanceRepository:
    def __init__(
        self,
        state: InMemoryEntitlementState,
    ) -> None:
        self._state = state

    async def get_snapshot(
        self,
        *,
        tenant_id: UUID,
        subscription_id: UUID,
    ) -> tuple[EntitlementBalanceSnapshot, int] | None:
        scope = _scope_key(tenant_id, subscription_id)
        snapshot = self._state.snapshots.get(scope)

        if snapshot is None:
            return None

        return snapshot, self._state.versions.get(scope, 0)

    async def compare_and_swap(
        self,
        request: BalanceCompareAndSwapRequest,
    ) -> BalanceCompareAndSwapResult:
        scope = _scope_key(
            request.tenant_id,
            request.subscription_id,
        )
        current_version = self._state.versions.get(scope, 0)

        if request.expected_version != current_version:
            return BalanceCompareAndSwapResult(
                updated=False,
                previous_version=current_version,
                resulting_version=current_version,
            )

        resulting_version = current_version + 1

        self._state.snapshots[scope] = EntitlementBalanceSnapshot(
            tenant_id=request.tenant_id,
            subscription_id=request.subscription_id,
            available_units=request.available_units,
            reserved_units=request.reserved_units,
            committed_units=request.committed_units,
            calculated_at=request.calculated_at,
        )
        self._state.versions[scope] = resulting_version

        return BalanceCompareAndSwapResult(
            updated=True,
            previous_version=current_version,
            resulting_version=resulting_version,
        )


class InMemoryEntitlementReservationRepository:
    def __init__(
        self,
        state: InMemoryEntitlementState,
        *,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._state = state
        self._now_provider = now_provider or (
            lambda: datetime.now(UTC)
        )

    async def acquire_lock(
        self,
        request: ReservationLockRequest,
    ) -> ReservationLock:
        key = _reservation_key(
            request.tenant_id,
            request.subscription_id,
            request.reservation_id,
        )
        now = self._now_provider()
        existing = self._state.locks.get(key)

        if (
            existing is not None
            and existing.acquired
            and existing.expires_at is not None
            and existing.expires_at > now
            and existing.owner_token != request.owner_token
        ):
            return ReservationLock(
                tenant_id=request.tenant_id,
                subscription_id=request.subscription_id,
                reservation_id=request.reservation_id,
                owner_token=request.owner_token,
                acquired=False,
                expires_at=existing.expires_at,
            )

        lock = ReservationLock(
            tenant_id=request.tenant_id,
            subscription_id=request.subscription_id,
            reservation_id=request.reservation_id,
            owner_token=request.owner_token,
            acquired=True,
            expires_at=now
            + timedelta(seconds=request.lease_seconds),
        )
        self._state.locks[key] = lock
        return lock

    async def release_lock(
        self,
        lock: ReservationLock,
    ) -> None:
        key = _reservation_key(
            lock.tenant_id,
            lock.subscription_id,
            lock.reservation_id,
        )
        existing = self._state.locks.get(key)

        if existing is None:
            return

        if existing.owner_token != lock.owner_token:
            raise InMemoryEntitlementLockOwnershipError(
                "reservation lock may be released only by its owner"
            )

        self._state.locks.pop(key, None)

    async def list_lifecycle_entries(
        self,
        *,
        tenant_id: UUID,
        subscription_id: UUID,
        reservation_id: UUID,
    ) -> tuple[EntitlementLedgerEntry, ...]:
        entries = self._state.entries.get(
            _scope_key(tenant_id, subscription_id),
            [],
        )

        return tuple(
            entry
            for entry in entries
            if entry.reservation_id == reservation_id
        )


class InMemoryEntitlementLedgerUnitOfWork:
    def __init__(
        self,
        state: InMemoryEntitlementState | None = None,
        *,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._state = state or InMemoryEntitlementState()
        self._now_provider = now_provider
        self._backup: InMemoryEntitlementState | None = None
        self._committed = False
        self._entered = False

        self.ledger = InMemoryEntitlementLedgerRepository(
            self._state
        )
        self.balances = InMemoryEntitlementBalanceRepository(
            self._state
        )
        self.reservations = (
            InMemoryEntitlementReservationRepository(
                self._state,
                now_provider=now_provider,
            )
        )

    @property
    def state(self) -> InMemoryEntitlementState:
        return self._state

    async def __aenter__(
        self,
    ) -> InMemoryEntitlementLedgerUnitOfWork:
        if self._entered:
            raise InMemoryEntitlementPersistenceError(
                "unit of work is already entered"
            )

        self._entered = True
        self._committed = False
        self._backup = deepcopy(self._state)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object | None,
    ) -> None:
        del exc_value
        del traceback

        try:
            if exc_type is not None or not self._committed:
                await self.rollback()
        finally:
            self._entered = False
            self._backup = None

    async def commit(self) -> None:
        if not self._entered:
            raise InMemoryEntitlementPersistenceError(
                "unit of work must be entered before commit"
            )

        self._committed = True

    async def rollback(self) -> None:
        if self._backup is None:
            return

        self._state.entries = deepcopy(
            self._backup.entries
        )
        self._state.entries_by_idempotency = deepcopy(
            self._backup.entries_by_idempotency
        )
        self._state.snapshots = deepcopy(
            self._backup.snapshots
        )
        self._state.versions = deepcopy(
            self._backup.versions
        )
        self._state.locks = deepcopy(
            self._backup.locks
        )
        self._committed = False


def in_memory_entitlement_reference_payload() -> dict[str, object]:
    return {
        "version": IN_MEMORY_ENTITLEMENT_REFERENCE_VERSION,
        "status": IN_MEMORY_ENTITLEMENT_REFERENCE_STATUS,
        "runtime_enabled": IN_MEMORY_ENTITLEMENT_RUNTIME_ENABLED,
        "production_use_allowed": (
            IN_MEMORY_ENTITLEMENT_PRODUCTION_USE_ALLOWED
        ),
        "supports_idempotency": True,
        "supports_balance_compare_and_swap": True,
        "supports_reservation_locking": True,
        "supports_uow_rollback": True,
        "durable_storage": False,
    }


__all__ = [
    "IN_MEMORY_ENTITLEMENT_PRODUCTION_USE_ALLOWED",
    "IN_MEMORY_ENTITLEMENT_REFERENCE_STATUS",
    "IN_MEMORY_ENTITLEMENT_REFERENCE_VERSION",
    "IN_MEMORY_ENTITLEMENT_RUNTIME_ENABLED",
    "InMemoryEntitlementBalanceRepository",
    "InMemoryEntitlementLedgerRepository",
    "InMemoryEntitlementLedgerUnitOfWork",
    "InMemoryEntitlementLockOwnershipError",
    "InMemoryEntitlementPersistenceError",
    "InMemoryEntitlementReservationRepository",
    "InMemoryEntitlementState",
    "InMemoryEntitlementVersionConflictError",
    "in_memory_entitlement_reference_payload",
]
