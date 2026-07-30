"""Shared SQLAlchemy unit of work for atomic top-up entitlement posting."""

from __future__ import annotations

from collections.abc import Callable
from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession

from processual_api.billing.commercial_entitlement_ledger_repositories import (
    SqlAlchemyEntitlementBalanceRepository,
    SqlAlchemyEntitlementLedgerRepository,
    SqlAlchemyEntitlementReservationRepository,
)
from processual_api.billing.commercial_top_up_repositories import (
    SqlAlchemyCommercialTopUpAuditRepository,
    SqlAlchemyCommercialTopUpGrantRepository,
    SqlAlchemyCommercialTopUpOrderRepository,
    SqlAlchemyCommercialTopUpPaymentRepository,
)

TOP_UP_ENTITLEMENT_SQLALCHEMY_UOW_ENABLED = False
TOP_UP_ENTITLEMENT_RUNTIME_UOW_WIRING_ENABLED = False


class SqlAlchemyAtomicTopUpEntitlementUnitOfWork:
    def __init__(
        self,
        session_factory: Callable[[], AsyncSession],
    ) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._committed = False

    async def __aenter__(
        self,
    ) -> SqlAlchemyAtomicTopUpEntitlementUnitOfWork:
        if self._session is not None:
            raise RuntimeError("atomic top-up entitlement unit is active")

        self._session = self._session_factory()
        self._committed = False
        self.orders = SqlAlchemyCommercialTopUpOrderRepository(self._session)
        self.payments = SqlAlchemyCommercialTopUpPaymentRepository(self._session)
        self.grants = SqlAlchemyCommercialTopUpGrantRepository(self._session)
        self.audit = SqlAlchemyCommercialTopUpAuditRepository(self._session)
        self.ledger = SqlAlchemyEntitlementLedgerRepository(self._session)
        self.balances = SqlAlchemyEntitlementBalanceRepository(self._session)
        self.reservations = SqlAlchemyEntitlementReservationRepository(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc
        del traceback
        if self._session is None:
            return
        try:
            if exc_type is not None or not self._committed:
                await self._session.rollback()
        finally:
            await self._session.close()
            self._session = None
            self._committed = False

    async def commit(self) -> None:
        session = self._require_session()
        await session.commit()
        self._committed = True

    async def rollback(self) -> None:
        session = self._require_session()
        await session.rollback()
        self._committed = False

    def _require_session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("atomic top-up entitlement unit is not active")
        return self._session


__all__ = [
    "TOP_UP_ENTITLEMENT_RUNTIME_UOW_WIRING_ENABLED",
    "TOP_UP_ENTITLEMENT_SQLALCHEMY_UOW_ENABLED",
    "SqlAlchemyAtomicTopUpEntitlementUnitOfWork",
]
