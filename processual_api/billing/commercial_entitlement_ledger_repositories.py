"""SQLAlchemy persistence adapters for the commercial entitlement ledger.

The adapters implement the reviewed persistence ports. They are not wired into
commercial execution or runtime charging.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from processual_api.billing.commercial_entitlement_ledger_contracts import (
    EntitlementBalanceSnapshot,
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
    BalanceCompareAndSwapResult,
    LedgerAppendRequest,
    LedgerAppendResult,
    ReservationLock,
    ReservationLockRequest,
)

ENTITLEMENT_LEDGER_SQLALCHEMY_REPOSITORIES_ENABLED = False
ENTITLEMENT_LEDGER_SQLALCHEMY_WRITES_ENABLED = False
ENTITLEMENT_LEDGER_SQLALCHEMY_LOCKING_ENABLED = False


class EntitlementLedgerPersistenceConflictError(RuntimeError):
    """Raised when persistence state violates the requested ledger boundary."""


class EntitlementReservationLockOwnershipError(RuntimeError):
    """Raised when a reservation lock is released by a non-owner."""


def _entry_from_model(
    model: CommercialEntitlementLedgerEntry,
) -> EntitlementLedgerEntry:
    return EntitlementLedgerEntry(
        entry_id=model.entry_id,
        tenant_id=model.tenant_id,
        subscription_id=model.subscription_id,
        entry_type=LedgerEntryType(model.entry_type),
        units=model.units,
        idempotency_key=model.idempotency_key,
        occurred_at=model.occurred_at,
        source_reference=model.source_reference,
        reservation_id=model.reservation_id,
        related_entry_id=model.related_entry_id,
        adjustment_units=model.adjustment_units,
        reason=model.reason,
    )


def _entry_to_model(
    entry: EntitlementLedgerEntry,
) -> CommercialEntitlementLedgerEntry:
    return CommercialEntitlementLedgerEntry(
        entry_id=entry.entry_id,
        tenant_id=entry.tenant_id,
        subscription_id=entry.subscription_id,
        entry_type=entry.entry_type.value,
        units=entry.units,
        idempotency_key=entry.idempotency_key,
        source_reference=entry.source_reference,
        reservation_id=entry.reservation_id,
        related_entry_id=entry.related_entry_id,
        adjustment_units=entry.adjustment_units,
        reason=entry.reason,
        occurred_at=entry.occurred_at,
    )


def _snapshot_from_model(
    model: CommercialEntitlementBalance,
) -> EntitlementBalanceSnapshot:
    return EntitlementBalanceSnapshot(
        tenant_id=model.tenant_id,
        subscription_id=model.subscription_id,
        available_units=model.available_units,
        reserved_units=model.reserved_units,
        committed_units=model.committed_units,
        calculated_at=model.calculated_at,
    )


class SqlAlchemyEntitlementLedgerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_idempotency_key(
        self,
        *,
        tenant_id: UUID,
        subscription_id: UUID,
        idempotency_key: str,
    ) -> EntitlementLedgerEntry | None:
        model = await self._session.scalar(
            select(CommercialEntitlementLedgerEntry).where(
                CommercialEntitlementLedgerEntry.tenant_id
                == tenant_id,
                CommercialEntitlementLedgerEntry.subscription_id
                == subscription_id,
                CommercialEntitlementLedgerEntry.idempotency_key
                == idempotency_key,
            )
        )

        if model is None:
            return None

        return _entry_from_model(model)

    async def append(
        self,
        request: LedgerAppendRequest,
    ) -> LedgerAppendResult:
        entry = request.entry

        existing = await self.get_by_idempotency_key(
            tenant_id=entry.tenant_id,
            subscription_id=entry.subscription_id,
            idempotency_key=entry.idempotency_key,
        )

        current_version = await self._session.scalar(
            select(CommercialEntitlementBalance.version)
            .where(
                CommercialEntitlementBalance.tenant_id
                == entry.tenant_id,
                CommercialEntitlementBalance.subscription_id
                == entry.subscription_id,
            )
            .with_for_update()
        )
        normalized_version = (
            0
            if current_version is None
            else int(current_version)
        )

        if existing is not None:
            return LedgerAppendResult(
                entry_id=existing.entry_id,
                appended=False,
                duplicate=True,
                resulting_balance_version=normalized_version,
            )

        if (
            normalized_version
            != request.expected_balance_version
        ):
            raise EntitlementLedgerPersistenceConflictError(
                "ledger append expected balance version does not "
                "match persisted balance version"
            )

        self._session.add(_entry_to_model(entry))
        await self._session.flush()

        return LedgerAppendResult(
            entry_id=entry.entry_id,
            appended=True,
            duplicate=False,
            resulting_balance_version=normalized_version,
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

        statement = select(
            CommercialEntitlementLedgerEntry
        ).where(
            CommercialEntitlementLedgerEntry.tenant_id
            == tenant_id,
            CommercialEntitlementLedgerEntry.subscription_id
            == subscription_id,
        )

        if after_entry_id is not None:
            anchor = await self._session.scalar(
                select(CommercialEntitlementLedgerEntry).where(
                    CommercialEntitlementLedgerEntry.entry_id
                    == after_entry_id,
                    CommercialEntitlementLedgerEntry.tenant_id
                    == tenant_id,
                    CommercialEntitlementLedgerEntry.subscription_id
                    == subscription_id,
                )
            )

            if anchor is not None:
                statement = statement.where(
                    or_(
                        CommercialEntitlementLedgerEntry.occurred_at
                        > anchor.occurred_at,
                        and_(
                            CommercialEntitlementLedgerEntry.occurred_at
                            == anchor.occurred_at,
                            CommercialEntitlementLedgerEntry.entry_id
                            > anchor.entry_id,
                        ),
                    )
                )

        result = await self._session.scalars(
            statement.order_by(
                CommercialEntitlementLedgerEntry.occurred_at,
                CommercialEntitlementLedgerEntry.entry_id,
            ).limit(limit)
        )

        return tuple(
            _entry_from_model(model)
            for model in result.all()
        )


class SqlAlchemyEntitlementBalanceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_snapshot(
        self,
        *,
        tenant_id: UUID,
        subscription_id: UUID,
    ) -> tuple[EntitlementBalanceSnapshot, int] | None:
        model = await self._session.scalar(
            select(CommercialEntitlementBalance).where(
                CommercialEntitlementBalance.tenant_id
                == tenant_id,
                CommercialEntitlementBalance.subscription_id
                == subscription_id,
            )
        )

        if model is None:
            return None

        return _snapshot_from_model(model), model.version

    async def compare_and_swap(
        self,
        request: BalanceCompareAndSwapRequest,
    ) -> BalanceCompareAndSwapResult:
        resulting_version = request.expected_version + 1

        result = await self._session.execute(
            update(CommercialEntitlementBalance)
            .where(
                CommercialEntitlementBalance.tenant_id
                == request.tenant_id,
                CommercialEntitlementBalance.subscription_id
                == request.subscription_id,
                CommercialEntitlementBalance.version
                == request.expected_version,
            )
            .values(
                available_units=request.available_units,
                reserved_units=request.reserved_units,
                committed_units=request.committed_units,
                calculated_at=request.calculated_at,
                updated_at=request.calculated_at,
                version=resulting_version,
            )
        )

        if int(result.rowcount or 0) == 1:
            return BalanceCompareAndSwapResult(
                updated=True,
                previous_version=request.expected_version,
                resulting_version=resulting_version,
            )

        current_version = await self._session.scalar(
            select(CommercialEntitlementBalance.version)
            .where(
                CommercialEntitlementBalance.tenant_id
                == request.tenant_id,
                CommercialEntitlementBalance.subscription_id
                == request.subscription_id,
            )
            .with_for_update()
        )

        if (
            current_version is None
            and request.expected_version == 0
        ):
            self._session.add(
                CommercialEntitlementBalance(
                    tenant_id=request.tenant_id,
                    subscription_id=request.subscription_id,
                    available_units=request.available_units,
                    reserved_units=request.reserved_units,
                    committed_units=request.committed_units,
                    version=1,
                    calculated_at=request.calculated_at,
                    updated_at=request.calculated_at,
                )
            )
            await self._session.flush()

            return BalanceCompareAndSwapResult(
                updated=True,
                previous_version=0,
                resulting_version=1,
            )

        normalized_version = (
            request.expected_version
            if current_version is None
            else int(current_version)
        )

        return BalanceCompareAndSwapResult(
            updated=False,
            previous_version=normalized_version,
            resulting_version=normalized_version,
        )


class SqlAlchemyEntitlementReservationRepository:
    def __init__(
        self,
        session: AsyncSession,
        *,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._session = session
        self._now_provider = now_provider or (
            lambda: datetime.now(UTC)
        )

    async def acquire_lock(
        self,
        request: ReservationLockRequest,
    ) -> ReservationLock:
        now = self._now_provider()

        model = await self._session.scalar(
            select(CommercialEntitlementReservationLock)
            .where(
                CommercialEntitlementReservationLock.tenant_id
                == request.tenant_id,
                CommercialEntitlementReservationLock.subscription_id
                == request.subscription_id,
                CommercialEntitlementReservationLock.reservation_id
                == request.reservation_id,
            )
            .with_for_update()
        )

        if (
            model is not None
            and model.expires_at > now
            and model.owner_token != request.owner_token
        ):
            return ReservationLock(
                tenant_id=request.tenant_id,
                subscription_id=request.subscription_id,
                reservation_id=request.reservation_id,
                owner_token=request.owner_token,
                acquired=False,
                expires_at=model.expires_at,
            )

        expires_at = now + timedelta(
            seconds=request.lease_seconds
        )

        if model is None:
            model = CommercialEntitlementReservationLock(
                tenant_id=request.tenant_id,
                subscription_id=request.subscription_id,
                reservation_id=request.reservation_id,
                owner_token=request.owner_token,
                expires_at=expires_at,
                created_at=now,
                updated_at=now,
            )
            self._session.add(model)
        else:
            model.owner_token = request.owner_token
            model.expires_at = expires_at
            model.updated_at = now

        await self._session.flush()

        return ReservationLock(
            tenant_id=request.tenant_id,
            subscription_id=request.subscription_id,
            reservation_id=request.reservation_id,
            owner_token=request.owner_token,
            acquired=True,
            expires_at=expires_at,
        )

    async def release_lock(
        self,
        lock: ReservationLock,
    ) -> None:
        model = await self._session.scalar(
            select(CommercialEntitlementReservationLock)
            .where(
                CommercialEntitlementReservationLock.tenant_id
                == lock.tenant_id,
                CommercialEntitlementReservationLock.subscription_id
                == lock.subscription_id,
                CommercialEntitlementReservationLock.reservation_id
                == lock.reservation_id,
            )
            .with_for_update()
        )

        if model is None:
            return

        if model.owner_token != lock.owner_token:
            raise EntitlementReservationLockOwnershipError(
                "reservation lock may be released only by its owner"
            )

        await self._session.delete(model)
        await self._session.flush()

    async def list_lifecycle_entries(
        self,
        *,
        tenant_id: UUID,
        subscription_id: UUID,
        reservation_id: UUID,
    ) -> tuple[EntitlementLedgerEntry, ...]:
        result = await self._session.scalars(
            select(CommercialEntitlementLedgerEntry)
            .where(
                CommercialEntitlementLedgerEntry.tenant_id
                == tenant_id,
                CommercialEntitlementLedgerEntry.subscription_id
                == subscription_id,
                CommercialEntitlementLedgerEntry.reservation_id
                == reservation_id,
            )
            .order_by(
                CommercialEntitlementLedgerEntry.occurred_at,
                CommercialEntitlementLedgerEntry.entry_id,
            )
        )

        return tuple(
            _entry_from_model(model)
            for model in result.all()
        )


__all__ = [
    "ENTITLEMENT_LEDGER_SQLALCHEMY_LOCKING_ENABLED",
    "ENTITLEMENT_LEDGER_SQLALCHEMY_REPOSITORIES_ENABLED",
    "ENTITLEMENT_LEDGER_SQLALCHEMY_WRITES_ENABLED",
    "EntitlementLedgerPersistenceConflictError",
    "EntitlementReservationLockOwnershipError",
    "SqlAlchemyEntitlementBalanceRepository",
    "SqlAlchemyEntitlementLedgerRepository",
    "SqlAlchemyEntitlementReservationRepository",
]
