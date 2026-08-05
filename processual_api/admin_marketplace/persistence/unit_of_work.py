from __future__ import annotations

from collections.abc import Callable
from types import TracebackType

from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from processual_api.admin_marketplace.notification_outbox import (
    SqlAlchemyNotificationOutboxRepository,
)
from processual_api.admin_marketplace.persistence.integrity import (
    translate_database_error,
)
from processual_api.admin_marketplace.persistence.repositories import (
    SqlAlchemyChannelEligibilityRepository,
    SqlAlchemyChannelSelectionRepository,
    SqlAlchemyCommercialAuditRepository,
    SqlAlchemyCommercialDecisionRepository,
    SqlAlchemyContractRepository,
    SqlAlchemyEntitlementActivationRepository,
    SqlAlchemyInvoiceRepository,
    SqlAlchemyOfferRepository,
    SqlAlchemyOrderRepository,
    SqlAlchemyPaymentDestinationRepository,
    SqlAlchemyPaymentEvidenceRepository,
    SqlAlchemyPaymentReconciliationRepository,
    SqlAlchemyPaymentVerificationRepository,
    SqlAlchemyPlanRepository,
    SqlAlchemySubscriptionRepository,
    SqlAlchemyTrialRepository,
)


class SqlAlchemyAdminMarketplaceUnitOfWork:
    """Transaction boundary for Admin Marketplace persistence."""

    def __init__(
        self,
        session_factory: Callable[[], AsyncSession],
    ) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._committed = False

        self.plans: SqlAlchemyPlanRepository
        self.offers: SqlAlchemyOfferRepository
        self.subscriptions: SqlAlchemySubscriptionRepository
        self.trials: SqlAlchemyTrialRepository
        self.orders: SqlAlchemyOrderRepository
        self.contracts: SqlAlchemyContractRepository
        self.payment_destinations: SqlAlchemyPaymentDestinationRepository
        self.payment_verifications: SqlAlchemyPaymentVerificationRepository
        self.payment_evidence: SqlAlchemyPaymentEvidenceRepository
        self.payment_reconciliations: SqlAlchemyPaymentReconciliationRepository
        self.invoices: SqlAlchemyInvoiceRepository
        self.entitlement_activations: SqlAlchemyEntitlementActivationRepository
        self.channel_eligibilities: SqlAlchemyChannelEligibilityRepository
        self.channel_selections: SqlAlchemyChannelSelectionRepository
        self.commercial_decisions: SqlAlchemyCommercialDecisionRepository
        self.commercial_audit: SqlAlchemyCommercialAuditRepository
        self.notification_outbox: SqlAlchemyNotificationOutboxRepository

    async def __aenter__(
        self,
    ) -> SqlAlchemyAdminMarketplaceUnitOfWork:
        if self._session is not None:
            raise RuntimeError("Admin Marketplace unit of work is already active.")

        session = self._session_factory()
        self._session = session
        self._committed = False

        self.plans = SqlAlchemyPlanRepository(session)
        self.offers = SqlAlchemyOfferRepository(session)
        self.subscriptions = SqlAlchemySubscriptionRepository(session)
        self.trials = SqlAlchemyTrialRepository(session)
        self.orders = SqlAlchemyOrderRepository(session)
        self.contracts = SqlAlchemyContractRepository(session)
        self.payment_destinations = SqlAlchemyPaymentDestinationRepository(session)
        self.payment_verifications = SqlAlchemyPaymentVerificationRepository(session)
        self.payment_evidence = SqlAlchemyPaymentEvidenceRepository(session)
        self.payment_reconciliations = SqlAlchemyPaymentReconciliationRepository(session)
        self.invoices = SqlAlchemyInvoiceRepository(session)
        self.entitlement_activations = SqlAlchemyEntitlementActivationRepository(session)
        self.channel_eligibilities = SqlAlchemyChannelEligibilityRepository(session)
        self.channel_selections = SqlAlchemyChannelSelectionRepository(session)
        self.commercial_decisions = SqlAlchemyCommercialDecisionRepository(session)
        self.commercial_audit = SqlAlchemyCommercialAuditRepository(session)
        self.notification_outbox = SqlAlchemyNotificationOutboxRepository(session)

        return self

    async def commit(self) -> None:
        session = self._require_active_session()

        try:
            await session.commit()
        except DBAPIError as exc:
            await session.rollback()
            raise translate_database_error(exc) from exc

        self._committed = True

    async def rollback(self) -> None:
        session = self._require_active_session()
        await session.rollback()
        self._committed = False

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        session = self._session
        if session is None:
            return

        try:
            if exc is not None or not self._committed:
                await session.rollback()
        finally:
            await session.close()
            self._session = None
            self._committed = False

    def _require_active_session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("Admin Marketplace unit of work is not active.")

        return self._session


__all__ = [
    "SqlAlchemyAdminMarketplaceUnitOfWork",
]
