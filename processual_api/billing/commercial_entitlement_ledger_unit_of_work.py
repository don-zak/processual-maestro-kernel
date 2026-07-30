"""SQLAlchemy unit of work for entitlement-ledger persistence."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession

from processual_api.billing.commercial_entitlement_ledger_repositories import (
    SqlAlchemyEntitlementBalanceRepository,
    SqlAlchemyEntitlementLedgerRepository,
    SqlAlchemyEntitlementReservationRepository,
)

ENTITLEMENT_LEDGER_SQLALCHEMY_UOW_ENABLED = False
ENTITLEMENT_LEDGER_RUNTIME_UOW_WIRING_ENABLED = False


class SqlAlchemyEntitlementLedgerUnitOfWork:
    def __init__(
        self,
        session_factory: Callable[[], AsyncSession],
        *,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._now_provider = now_provider
        self._session: AsyncSession | None = None
        self._committed = False

    async def __aenter__(
        self,
    ) -> SqlAlchemyEntitlementLedgerUnitOfWork:
        if self._session is not None:
            raise RuntimeError(
                "entitlement ledger unit of work is already active"
            )

        self._session = self._session_factory()
        self._committed = False

        self.ledger = SqlAlchemyEntitlementLedgerRepository(
            self._session
        )
        self.balances = SqlAlchemyEntitlementBalanceRepository(
            self._session
        )
        self.reservations = (
            SqlAlchemyEntitlementReservationRepository(
                self._session,
                now_provider=self._now_provider,
            )
        )

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
        session = self._require_active_session()
        await session.commit()
        self._committed = True

    async def rollback(self) -> None:
        session = self._require_active_session()
        await session.rollback()
        self._committed = False

    def _require_active_session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError(
                "entitlement ledger unit of work is not active"
            )

        return self._session


__all__ = [
    "ENTITLEMENT_LEDGER_RUNTIME_UOW_WIRING_ENABLED",
    "ENTITLEMENT_LEDGER_SQLALCHEMY_UOW_ENABLED",
    "SqlAlchemyEntitlementLedgerUnitOfWork",
]
