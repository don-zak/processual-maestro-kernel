from __future__ import annotations

from collections.abc import Callable
from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession

from processual_api.billing.commercial_top_up_repositories import (
    SqlAlchemyCommercialTopUpAuditRepository,
    SqlAlchemyCommercialTopUpGrantRepository,
    SqlAlchemyCommercialTopUpOrderRepository,
    SqlAlchemyCommercialTopUpPaymentRepository,
)


class SqlAlchemyCommercialTopUpUnitOfWork:
    def __init__(
        self,
        session_factory: Callable[[], AsyncSession],
    ) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._committed = False

    async def __aenter__(self) -> SqlAlchemyCommercialTopUpUnitOfWork:
        self._session = self._session_factory()
        self.orders = SqlAlchemyCommercialTopUpOrderRepository(self._session)
        self.payments = SqlAlchemyCommercialTopUpPaymentRepository(self._session)
        self.grants = SqlAlchemyCommercialTopUpGrantRepository(self._session)
        self.audit = SqlAlchemyCommercialTopUpAuditRepository(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._session is None:
            return
        try:
            if exc_type is not None or not self._committed:
                await self._session.rollback()
        finally:
            await self._session.close()

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("unit of work is not active")
        await self._session.commit()
        self._committed = True

    async def rollback(self) -> None:
        if self._session is None:
            raise RuntimeError("unit of work is not active")
        await self._session.rollback()
