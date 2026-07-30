"""Review-only persistence ports for the entitlement ledger.

The contracts in this module describe repository and unit-of-work boundaries.
They do not provide SQLAlchemy models, database migrations, concrete storage,
or production runtime charging.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final, Protocol, runtime_checkable
from uuid import UUID

from processual_api.billing.commercial_entitlement_ledger_contracts import (
    EntitlementBalanceSnapshot,
    EntitlementLedgerEntry,
)

ENTITLEMENT_LEDGER_PERSISTENCE_VERSION: Final = "2026-07-group2-entitlement-ledger-persistence-v1"
ENTITLEMENT_LEDGER_PERSISTENCE_STATUS: Final = "draft_review"

ENTITLEMENT_LEDGER_REPOSITORIES_ENABLED: Final = False
ENTITLEMENT_LEDGER_UOW_ENABLED: Final = False
ENTITLEMENT_LEDGER_DATABASE_WRITES_ENABLED: Final = False
ENTITLEMENT_BALANCE_CAS_ENABLED: Final = False
ENTITLEMENT_RESERVATION_LOCKING_ENABLED: Final = False
ENTITLEMENT_LEDGER_RUNTIME_INTEGRATION_ENABLED: Final = False

ATOMIC_APPEND_REQUIRED: Final = True
IDEMPOTENCY_LOOKUP_REQUIRED: Final = True
BALANCE_VERSION_REQUIRED: Final = True
RESERVATION_LOCK_REQUIRED: Final = True
ROLLBACK_ON_FAILURE_REQUIRED: Final = True


class EntitlementPersistenceContractError(ValueError):
    """Raised when a persistence contract value is invalid."""


@dataclass(frozen=True, slots=True)
class LedgerAppendRequest:
    entry: EntitlementLedgerEntry
    expected_balance_version: int

    def __post_init__(self) -> None:
        if self.expected_balance_version < 0:
            raise EntitlementPersistenceContractError("expected_balance_version must not be negative")


@dataclass(frozen=True, slots=True)
class LedgerAppendResult:
    entry_id: UUID
    appended: bool
    duplicate: bool
    resulting_balance_version: int

    def __post_init__(self) -> None:
        if self.appended and self.duplicate:
            raise EntitlementPersistenceContractError("append result cannot be appended and duplicate")

        if not self.appended and not self.duplicate:
            raise EntitlementPersistenceContractError("append result must be appended or duplicate")

        if self.resulting_balance_version < 0:
            raise EntitlementPersistenceContractError("resulting_balance_version must not be negative")


@dataclass(frozen=True, slots=True)
class BalanceCompareAndSwapRequest:
    tenant_id: UUID
    subscription_id: UUID
    expected_version: int
    available_units: int
    reserved_units: int
    committed_units: int
    calculated_at: datetime

    def __post_init__(self) -> None:
        if self.expected_version < 0:
            raise EntitlementPersistenceContractError("expected_version must not be negative")

        values = (
            self.available_units,
            self.reserved_units,
            self.committed_units,
        )

        if any(value < 0 for value in values):
            raise EntitlementPersistenceContractError("balance values must not be negative")

        if self.calculated_at.tzinfo is None:
            raise EntitlementPersistenceContractError("calculated_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class BalanceCompareAndSwapResult:
    updated: bool
    previous_version: int
    resulting_version: int

    def __post_init__(self) -> None:
        if self.previous_version < 0:
            raise EntitlementPersistenceContractError("previous_version must not be negative")

        if self.resulting_version < 0:
            raise EntitlementPersistenceContractError("resulting_version must not be negative")

        if self.updated:
            if self.resulting_version != self.previous_version + 1:
                raise EntitlementPersistenceContractError("successful compare-and-swap must increment version once")
        elif self.resulting_version != self.previous_version:
            raise EntitlementPersistenceContractError("failed compare-and-swap must preserve version")


@dataclass(frozen=True, slots=True)
class ReservationLockRequest:
    tenant_id: UUID
    subscription_id: UUID
    reservation_id: UUID
    owner_token: str
    lease_seconds: int

    def __post_init__(self) -> None:
        if not self.owner_token.strip():
            raise EntitlementPersistenceContractError("owner_token must not be blank")

        if self.lease_seconds <= 0:
            raise EntitlementPersistenceContractError("lease_seconds must be positive")


@dataclass(frozen=True, slots=True)
class ReservationLock:
    tenant_id: UUID
    subscription_id: UUID
    reservation_id: UUID
    owner_token: str
    acquired: bool
    expires_at: datetime | None

    def __post_init__(self) -> None:
        if not self.owner_token.strip():
            raise EntitlementPersistenceContractError("owner_token must not be blank")

        if self.acquired and self.expires_at is None:
            raise EntitlementPersistenceContractError("acquired reservation lock requires expires_at")

        if self.expires_at is not None and self.expires_at.tzinfo is None:
            raise EntitlementPersistenceContractError("expires_at must be timezone-aware")


@runtime_checkable
class EntitlementLedgerRepository(Protocol):
    async def get_by_idempotency_key(
        self,
        *,
        tenant_id: UUID,
        subscription_id: UUID,
        idempotency_key: str,
    ) -> EntitlementLedgerEntry | None: ...

    async def append(
        self,
        request: LedgerAppendRequest,
    ) -> LedgerAppendResult: ...

    async def list_for_subscription(
        self,
        *,
        tenant_id: UUID,
        subscription_id: UUID,
        after_entry_id: UUID | None = None,
        limit: int = 100,
    ) -> tuple[EntitlementLedgerEntry, ...]: ...


@runtime_checkable
class EntitlementBalanceRepository(Protocol):
    async def get_snapshot(
        self,
        *,
        tenant_id: UUID,
        subscription_id: UUID,
    ) -> tuple[EntitlementBalanceSnapshot, int] | None: ...

    async def compare_and_swap(
        self,
        request: BalanceCompareAndSwapRequest,
    ) -> BalanceCompareAndSwapResult: ...


@runtime_checkable
class EntitlementReservationRepository(Protocol):
    async def acquire_lock(
        self,
        request: ReservationLockRequest,
    ) -> ReservationLock: ...

    async def release_lock(
        self,
        lock: ReservationLock,
    ) -> None: ...

    async def list_lifecycle_entries(
        self,
        *,
        tenant_id: UUID,
        subscription_id: UUID,
        reservation_id: UUID,
    ) -> tuple[EntitlementLedgerEntry, ...]: ...


@runtime_checkable
class EntitlementLedgerUnitOfWork(Protocol):
    ledger: EntitlementLedgerRepository
    balances: EntitlementBalanceRepository
    reservations: EntitlementReservationRepository

    async def __aenter__(
        self,
    ) -> EntitlementLedgerUnitOfWork: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object | None,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


def entitlement_ledger_persistence_review_payload() -> dict[str, object]:
    return {
        "version": ENTITLEMENT_LEDGER_PERSISTENCE_VERSION,
        "status": ENTITLEMENT_LEDGER_PERSISTENCE_STATUS,
        "repositories_enabled": (ENTITLEMENT_LEDGER_REPOSITORIES_ENABLED),
        "unit_of_work_enabled": ENTITLEMENT_LEDGER_UOW_ENABLED,
        "database_writes_enabled": (ENTITLEMENT_LEDGER_DATABASE_WRITES_ENABLED),
        "balance_compare_and_swap_enabled": (ENTITLEMENT_BALANCE_CAS_ENABLED),
        "reservation_locking_enabled": (ENTITLEMENT_RESERVATION_LOCKING_ENABLED),
        "runtime_integration_enabled": (ENTITLEMENT_LEDGER_RUNTIME_INTEGRATION_ENABLED),
        "atomic_append_required": ATOMIC_APPEND_REQUIRED,
        "idempotency_lookup_required": IDEMPOTENCY_LOOKUP_REQUIRED,
        "balance_version_required": BALANCE_VERSION_REQUIRED,
        "reservation_lock_required": RESERVATION_LOCK_REQUIRED,
        "rollback_on_failure_required": ROLLBACK_ON_FAILURE_REQUIRED,
    }


__all__ = [
    "ATOMIC_APPEND_REQUIRED",
    "BALANCE_VERSION_REQUIRED",
    "BalanceCompareAndSwapRequest",
    "BalanceCompareAndSwapResult",
    "ENTITLEMENT_BALANCE_CAS_ENABLED",
    "ENTITLEMENT_LEDGER_DATABASE_WRITES_ENABLED",
    "ENTITLEMENT_LEDGER_PERSISTENCE_STATUS",
    "ENTITLEMENT_LEDGER_PERSISTENCE_VERSION",
    "ENTITLEMENT_LEDGER_REPOSITORIES_ENABLED",
    "ENTITLEMENT_LEDGER_RUNTIME_INTEGRATION_ENABLED",
    "ENTITLEMENT_LEDGER_UOW_ENABLED",
    "ENTITLEMENT_RESERVATION_LOCKING_ENABLED",
    "EntitlementBalanceRepository",
    "EntitlementLedgerRepository",
    "EntitlementLedgerUnitOfWork",
    "EntitlementPersistenceContractError",
    "EntitlementReservationRepository",
    "IDEMPOTENCY_LOOKUP_REQUIRED",
    "LedgerAppendRequest",
    "LedgerAppendResult",
    "RESERVATION_LOCK_REQUIRED",
    "ROLLBACK_ON_FAILURE_REQUIRED",
    "ReservationLock",
    "ReservationLockRequest",
    "entitlement_ledger_persistence_review_payload",
]
