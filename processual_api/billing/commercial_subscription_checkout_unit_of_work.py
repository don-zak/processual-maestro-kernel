from __future__ import annotations

from collections.abc import Callable
from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession

from processual_api.billing.commercial_subscription_checkout_repositories import (
    SqlAlchemyCommercialActivationDecisionRepository,
    SqlAlchemyCommercialPaymentEvidenceRepository,
    SqlAlchemySubscriptionCheckoutOrderRepository,
    apply_checkout_pending_updates,
)

COMMERCIAL_SUBSCRIPTION_CHECKOUT_SQLALCHEMY_UOW_ENABLED = False
COMMERCIAL_SUBSCRIPTION_CHECKOUT_RUNTIME_WIRING_ENABLED = False


class SqlAlchemyCommercialSubscriptionCheckoutUnitOfWork:
    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._committed = False

    async def __aenter__(self):
        if self._session is not None:
            raise RuntimeError("checkout unit of work is already active")
        self._session = self._session_factory()
        self._committed = False
        self.orders = SqlAlchemySubscriptionCheckoutOrderRepository(self._session)
        self.payments = SqlAlchemyCommercialPaymentEvidenceRepository(self._session)
        self.decisions = SqlAlchemyCommercialActivationDecisionRepository(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc, traceback
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
        if self._session is None:
            raise RuntimeError("checkout unit of work is not active")
        await apply_checkout_pending_updates(self._session)
        await self._session.commit()
        self._committed = True

    async def rollback(self) -> None:
        if self._session is None:
            raise RuntimeError("checkout unit of work is not active")
        await self._session.rollback()
        self._committed = False
