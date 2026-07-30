"""Atomic review-only service for entitlement reservation lifecycle.

The service coordinates reservation locks, immutable ledger appends, balance
compare-and-swap updates, and unit-of-work transactions. It is not wired into
runtime execution or commercial enforcement.
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
    ReservationLock,
    ReservationLockRequest,
)

ENTITLEMENT_RESERVATION_SERVICE_VERSION: Final = "2026-07-group2-entitlement-reservation-service-v1"
ENTITLEMENT_RESERVATION_SERVICE_STATUS: Final = "draft_review"

ENTITLEMENT_RESERVATION_SERVICE_ENABLED: Final = False
ENTITLEMENT_RESERVATION_WRITES_ENABLED: Final = False
ENTITLEMENT_RESERVATION_RUNTIME_WIRING_ENABLED: Final = False
ENTITLEMENT_RESERVATION_COMMERCIAL_ENFORCEMENT_ENABLED: Final = False

DEFAULT_RESERVATION_LEASE_SECONDS: Final = 30


class EntitlementReservationServiceError(RuntimeError):
    """Base error for reservation lifecycle operations."""


class EntitlementReservationLockUnavailableError(EntitlementReservationServiceError):
    """Raised when another owner currently holds the reservation lock."""


class EntitlementInsufficientBalanceError(EntitlementReservationServiceError):
    """Raised when requested units exceed the owned available balance."""


class EntitlementReservationLifecycleError(EntitlementReservationServiceError):
    """Raised when the requested lifecycle transition is invalid."""


class EntitlementBalanceConflictError(EntitlementReservationServiceError):
    """Raised when the balance compare-and-swap operation fails."""


@dataclass(frozen=True, slots=True)
class ReserveUnitsCommand:
    tenant_id: UUID
    subscription_id: UUID
    reservation_id: UUID
    units: int
    idempotency_key: str
    source_reference: str
    owner_token: str
    occurred_at: datetime
    lease_seconds: int = DEFAULT_RESERVATION_LEASE_SECONDS

    def __post_init__(self) -> None:
        _validate_common_command(
            units=self.units,
            idempotency_key=self.idempotency_key,
            source_reference=self.source_reference,
            owner_token=self.owner_token,
            occurred_at=self.occurred_at,
            lease_seconds=self.lease_seconds,
        )


@dataclass(frozen=True, slots=True)
class CommitReservationCommand:
    tenant_id: UUID
    subscription_id: UUID
    reservation_id: UUID
    units: int
    idempotency_key: str
    source_reference: str
    owner_token: str
    occurred_at: datetime
    lease_seconds: int = DEFAULT_RESERVATION_LEASE_SECONDS

    def __post_init__(self) -> None:
        _validate_common_command(
            units=self.units,
            idempotency_key=self.idempotency_key,
            source_reference=self.source_reference,
            owner_token=self.owner_token,
            occurred_at=self.occurred_at,
            lease_seconds=self.lease_seconds,
        )


@dataclass(frozen=True, slots=True)
class ReleaseReservationCommand:
    tenant_id: UUID
    subscription_id: UUID
    reservation_id: UUID
    units: int
    idempotency_key: str
    source_reference: str
    owner_token: str
    occurred_at: datetime
    lease_seconds: int = DEFAULT_RESERVATION_LEASE_SECONDS

    def __post_init__(self) -> None:
        _validate_common_command(
            units=self.units,
            idempotency_key=self.idempotency_key,
            source_reference=self.source_reference,
            owner_token=self.owner_token,
            occurred_at=self.occurred_at,
            lease_seconds=self.lease_seconds,
        )


@dataclass(frozen=True, slots=True)
class EntitlementReservationOperationResult:
    reservation_id: UUID
    entry_id: UUID
    entry_type: LedgerEntryType
    units: int
    duplicate: bool
    previous_balance_version: int
    resulting_balance_version: int
    available_units: int
    reserved_units: int
    committed_units: int


def _validate_common_command(
    *,
    units: int,
    idempotency_key: str,
    source_reference: str,
    owner_token: str,
    occurred_at: datetime,
    lease_seconds: int,
) -> None:
    if units <= 0:
        raise ValueError("units must be positive")
    if not idempotency_key.strip():
        raise ValueError("idempotency_key must not be blank")
    if not source_reference.strip():
        raise ValueError("source_reference must not be blank")
    if not owner_token.strip():
        raise ValueError("owner_token must not be blank")
    if occurred_at.tzinfo is None:
        raise ValueError("occurred_at must be timezone-aware")
    if lease_seconds <= 0:
        raise ValueError("lease_seconds must be positive")


class EntitlementReservationService:
    def __init__(
        self,
        unit_of_work_factory: Callable[
            [],
            EntitlementLedgerUnitOfWork,
        ],
        *,
        entry_id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._entry_id_factory = entry_id_factory

    async def reserve_units(
        self,
        command: ReserveUnitsCommand,
    ) -> EntitlementReservationOperationResult:
        async with self._unit_of_work_factory() as unit:
            lock = await self._acquire_lock(
                unit=unit,
                tenant_id=command.tenant_id,
                subscription_id=command.subscription_id,
                reservation_id=command.reservation_id,
                owner_token=command.owner_token,
                lease_seconds=command.lease_seconds,
            )

            try:
                duplicate = await unit.ledger.get_by_idempotency_key(
                    tenant_id=command.tenant_id,
                    subscription_id=command.subscription_id,
                    idempotency_key=command.idempotency_key,
                )
                if duplicate is not None:
                    return await self._complete_duplicate(
                        unit=unit,
                        lock=lock,
                        entry=duplicate,
                    )

                lifecycle = await unit.reservations.list_lifecycle_entries(
                    tenant_id=command.tenant_id,
                    subscription_id=command.subscription_id,
                    reservation_id=command.reservation_id,
                )
                if lifecycle:
                    raise EntitlementReservationLifecycleError("reservation already has lifecycle entries")

                snapshot, version = await self._load_balance(
                    unit=unit,
                    tenant_id=command.tenant_id,
                    subscription_id=command.subscription_id,
                    calculated_at=command.occurred_at,
                )

                if snapshot.available_units < command.units:
                    raise EntitlementInsufficientBalanceError("requested units exceed available entitlement balance")

                entry = self._entry(
                    command=command,
                    entry_type=LedgerEntryType.USAGE_RESERVE,
                )

                append_result = await unit.ledger.append(
                    LedgerAppendRequest(
                        entry=entry,
                        expected_balance_version=version,
                    )
                )

                updated = await self._swap_balance(
                    unit=unit,
                    snapshot=snapshot,
                    expected_version=version,
                    available_units=(snapshot.available_units - command.units),
                    reserved_units=(snapshot.reserved_units + command.units),
                    committed_units=snapshot.committed_units,
                    calculated_at=command.occurred_at,
                )

                await unit.reservations.release_lock(lock)
                await unit.commit()

                return EntitlementReservationOperationResult(
                    reservation_id=command.reservation_id,
                    entry_id=append_result.entry_id,
                    entry_type=LedgerEntryType.USAGE_RESERVE,
                    units=command.units,
                    duplicate=append_result.duplicate,
                    previous_balance_version=version,
                    resulting_balance_version=updated,
                    available_units=(snapshot.available_units - command.units),
                    reserved_units=(snapshot.reserved_units + command.units),
                    committed_units=snapshot.committed_units,
                )
            except BaseException:
                await unit.rollback()
                raise

    async def commit_reservation(
        self,
        command: CommitReservationCommand,
    ) -> EntitlementReservationOperationResult:
        return await self._finalize_reservation(
            command=command,
            entry_type=LedgerEntryType.USAGE_COMMIT,
        )

    async def release_reservation(
        self,
        command: ReleaseReservationCommand,
    ) -> EntitlementReservationOperationResult:
        return await self._finalize_reservation(
            command=command,
            entry_type=LedgerEntryType.USAGE_RELEASE,
        )

    async def _finalize_reservation(
        self,
        *,
        command: CommitReservationCommand | ReleaseReservationCommand,
        entry_type: LedgerEntryType,
    ) -> EntitlementReservationOperationResult:
        async with self._unit_of_work_factory() as unit:
            lock = await self._acquire_lock(
                unit=unit,
                tenant_id=command.tenant_id,
                subscription_id=command.subscription_id,
                reservation_id=command.reservation_id,
                owner_token=command.owner_token,
                lease_seconds=command.lease_seconds,
            )

            try:
                duplicate = await unit.ledger.get_by_idempotency_key(
                    tenant_id=command.tenant_id,
                    subscription_id=command.subscription_id,
                    idempotency_key=command.idempotency_key,
                )
                if duplicate is not None:
                    return await self._complete_duplicate(
                        unit=unit,
                        lock=lock,
                        entry=duplicate,
                    )

                lifecycle = await unit.reservations.list_lifecycle_entries(
                    tenant_id=command.tenant_id,
                    subscription_id=command.subscription_id,
                    reservation_id=command.reservation_id,
                )

                reservation = self._validate_finalization_lifecycle(
                    lifecycle=lifecycle,
                    entry_type=entry_type,
                    units=command.units,
                )

                snapshot, version = await self._load_balance(
                    unit=unit,
                    tenant_id=command.tenant_id,
                    subscription_id=command.subscription_id,
                    calculated_at=command.occurred_at,
                )

                if snapshot.reserved_units < command.units:
                    raise EntitlementReservationLifecycleError("reserved balance is lower than requested finalization")

                entry = self._entry(
                    command=command,
                    entry_type=entry_type,
                    related_entry_id=reservation.entry_id,
                )

                append_result = await unit.ledger.append(
                    LedgerAppendRequest(
                        entry=entry,
                        expected_balance_version=version,
                    )
                )

                if entry_type is LedgerEntryType.USAGE_COMMIT:
                    available_units = snapshot.available_units
                    reserved_units = snapshot.reserved_units - command.units
                    committed_units = snapshot.committed_units + command.units
                else:
                    available_units = snapshot.available_units + command.units
                    reserved_units = snapshot.reserved_units - command.units
                    committed_units = snapshot.committed_units

                updated = await self._swap_balance(
                    unit=unit,
                    snapshot=snapshot,
                    expected_version=version,
                    available_units=available_units,
                    reserved_units=reserved_units,
                    committed_units=committed_units,
                    calculated_at=command.occurred_at,
                )

                await unit.reservations.release_lock(lock)
                await unit.commit()

                return EntitlementReservationOperationResult(
                    reservation_id=command.reservation_id,
                    entry_id=append_result.entry_id,
                    entry_type=entry_type,
                    units=command.units,
                    duplicate=append_result.duplicate,
                    previous_balance_version=version,
                    resulting_balance_version=updated,
                    available_units=available_units,
                    reserved_units=reserved_units,
                    committed_units=committed_units,
                )
            except BaseException:
                await unit.rollback()
                raise

    async def _acquire_lock(
        self,
        *,
        unit: EntitlementLedgerUnitOfWork,
        tenant_id: UUID,
        subscription_id: UUID,
        reservation_id: UUID,
        owner_token: str,
        lease_seconds: int,
    ) -> ReservationLock:
        lock = await unit.reservations.acquire_lock(
            ReservationLockRequest(
                tenant_id=tenant_id,
                subscription_id=subscription_id,
                reservation_id=reservation_id,
                owner_token=owner_token,
                lease_seconds=lease_seconds,
            )
        )

        if not lock.acquired:
            raise EntitlementReservationLockUnavailableError("reservation lifecycle lock is held by another owner")

        return lock

    async def _load_balance(
        self,
        *,
        unit: EntitlementLedgerUnitOfWork,
        tenant_id: UUID,
        subscription_id: UUID,
        calculated_at: datetime,
    ) -> tuple[EntitlementBalanceSnapshot, int]:
        stored = await unit.balances.get_snapshot(
            tenant_id=tenant_id,
            subscription_id=subscription_id,
        )

        if stored is not None:
            return stored

        return (
            EntitlementBalanceSnapshot(
                tenant_id=tenant_id,
                subscription_id=subscription_id,
                available_units=0,
                reserved_units=0,
                committed_units=0,
                calculated_at=calculated_at.astimezone(UTC),
            ),
            0,
        )

    async def _swap_balance(
        self,
        *,
        unit: EntitlementLedgerUnitOfWork,
        snapshot: EntitlementBalanceSnapshot,
        expected_version: int,
        available_units: int,
        reserved_units: int,
        committed_units: int,
        calculated_at: datetime,
    ) -> int:
        result = await unit.balances.compare_and_swap(
            BalanceCompareAndSwapRequest(
                tenant_id=snapshot.tenant_id,
                subscription_id=snapshot.subscription_id,
                expected_version=expected_version,
                available_units=available_units,
                reserved_units=reserved_units,
                committed_units=committed_units,
                calculated_at=calculated_at,
            )
        )

        if not result.updated:
            raise EntitlementBalanceConflictError("entitlement balance compare-and-swap conflict")

        return result.resulting_version

    async def _complete_duplicate(
        self,
        *,
        unit: EntitlementLedgerUnitOfWork,
        lock: ReservationLock,
        entry: EntitlementLedgerEntry,
    ) -> EntitlementReservationOperationResult:
        stored = await unit.balances.get_snapshot(
            tenant_id=entry.tenant_id,
            subscription_id=entry.subscription_id,
        )

        if stored is None:
            raise EntitlementReservationLifecycleError("duplicate ledger entry has no persisted balance")

        snapshot, version = stored
        await unit.reservations.release_lock(lock)
        await unit.commit()

        return EntitlementReservationOperationResult(
            reservation_id=entry.reservation_id,
            entry_id=entry.entry_id,
            entry_type=entry.entry_type,
            units=entry.units,
            duplicate=True,
            previous_balance_version=version,
            resulting_balance_version=version,
            available_units=snapshot.available_units,
            reserved_units=snapshot.reserved_units,
            committed_units=snapshot.committed_units,
        )

    def _entry(
        self,
        *,
        command: ReserveUnitsCommand | CommitReservationCommand | ReleaseReservationCommand,
        entry_type: LedgerEntryType,
        related_entry_id: UUID | None = None,
    ) -> EntitlementLedgerEntry:
        return EntitlementLedgerEntry(
            entry_id=self._entry_id_factory(),
            tenant_id=command.tenant_id,
            subscription_id=command.subscription_id,
            entry_type=entry_type,
            units=command.units,
            idempotency_key=command.idempotency_key,
            occurred_at=command.occurred_at,
            source_reference=command.source_reference,
            reservation_id=command.reservation_id,
            related_entry_id=related_entry_id,
        )

    @staticmethod
    def _validate_finalization_lifecycle(
        *,
        lifecycle: tuple[EntitlementLedgerEntry, ...],
        entry_type: LedgerEntryType,
        units: int,
    ) -> EntitlementLedgerEntry:
        reservations = tuple(entry for entry in lifecycle if entry.entry_type is LedgerEntryType.USAGE_RESERVE)
        commits = tuple(entry for entry in lifecycle if entry.entry_type is LedgerEntryType.USAGE_COMMIT)
        releases = tuple(entry for entry in lifecycle if entry.entry_type is LedgerEntryType.USAGE_RELEASE)

        if len(reservations) != 1:
            raise EntitlementReservationLifecycleError("reservation finalization requires one reserve entry")

        if commits or releases:
            raise EntitlementReservationLifecycleError("reservation is already finalized")

        reservation = reservations[0]
        if reservation.units != units:
            raise EntitlementReservationLifecycleError("finalization units must equal reserved units")

        if entry_type not in {
            LedgerEntryType.USAGE_COMMIT,
            LedgerEntryType.USAGE_RELEASE,
        }:
            raise EntitlementReservationLifecycleError("unsupported reservation finalization type")

        return reservation


def entitlement_reservation_service_review_payload() -> dict[str, object]:
    return {
        "version": ENTITLEMENT_RESERVATION_SERVICE_VERSION,
        "status": ENTITLEMENT_RESERVATION_SERVICE_STATUS,
        "enabled": ENTITLEMENT_RESERVATION_SERVICE_ENABLED,
        "writes_enabled": ENTITLEMENT_RESERVATION_WRITES_ENABLED,
        "runtime_wiring_enabled": (ENTITLEMENT_RESERVATION_RUNTIME_WIRING_ENABLED),
        "commercial_enforcement_enabled": (ENTITLEMENT_RESERVATION_COMMERCIAL_ENFORCEMENT_ENABLED),
        "reserve_operation_defined": True,
        "commit_operation_defined": True,
        "release_operation_defined": True,
        "reservation_lock_required": True,
        "balance_cas_required": True,
        "atomic_uow_required": True,
    }


__all__ = [
    "DEFAULT_RESERVATION_LEASE_SECONDS",
    "ENTITLEMENT_RESERVATION_COMMERCIAL_ENFORCEMENT_ENABLED",
    "ENTITLEMENT_RESERVATION_RUNTIME_WIRING_ENABLED",
    "ENTITLEMENT_RESERVATION_SERVICE_ENABLED",
    "ENTITLEMENT_RESERVATION_SERVICE_STATUS",
    "ENTITLEMENT_RESERVATION_SERVICE_VERSION",
    "ENTITLEMENT_RESERVATION_WRITES_ENABLED",
    "CommitReservationCommand",
    "EntitlementBalanceConflictError",
    "EntitlementInsufficientBalanceError",
    "EntitlementReservationLifecycleError",
    "EntitlementReservationLockUnavailableError",
    "EntitlementReservationOperationResult",
    "EntitlementReservationService",
    "EntitlementReservationServiceError",
    "ReleaseReservationCommand",
    "ReserveUnitsCommand",
    "entitlement_reservation_service_review_payload",
]
