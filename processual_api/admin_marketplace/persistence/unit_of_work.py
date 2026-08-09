from __future__ import annotations

from collections.abc import Callable
from types import TracebackType

from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from processual_api.admin_marketplace.assessment_commercial_terms_persistence import (
    SqlAlchemyAssessmentCommercialTermsRepository,
)
from processual_api.admin_marketplace.assessment_quota_profile_persistence import (
    SqlAlchemyAssessmentQuotaProfileRepository,
)
from processual_api.admin_marketplace.assessment_subscription_persistence import (
    SqlAlchemyAssessmentSubscriptionBindingRepository,
)
from processual_api.admin_marketplace.lemon_squeezy_binding_persistence import (
    SqlAlchemyLemonSqueezyBindingRepository,
)
from processual_api.admin_marketplace.lemon_squeezy_persistence import (
    SqlAlchemyLemonSqueezyWebhookInboxRepository,
)
from processual_api.admin_marketplace.lemon_squeezy_reconciliation_persistence import (
    SqlAlchemyLemonSqueezyReconciliationDecisionRepository,
)
from processual_api.admin_marketplace.notification_outbox import (
    SqlAlchemyNotificationOutboxRepository,
)
from processual_api.admin_marketplace.persistence.integrity import translate_database_error
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
from processual_api.admin_marketplace.subscription_delinquency_persistence import (
    SqlAlchemySubscriptionDelinquencyRepository,
)
from processual_api.admin_marketplace.subscription_quota_rollover_persistence import (
    SqlAlchemySubscriptionQuotaCycleRepository,
)
from processual_api.admin_marketplace.subscription_quota_usage_persistence import (
    SqlAlchemySubscriptionQuotaCycleUsageRepository,
)
from processual_api.admin_marketplace.subscription_runtime_persistence import (
    SqlAlchemySubscriptionQuotaRepository,
    SqlAlchemySubscriptionRuntimeRepository,
    SqlAlchemySubscriptionUsageRepository,
)
from processual_api.admin_marketplace.subscription_runtime_transition_persistence import (
    SqlAlchemySubscriptionRuntimeTransitionRepository,
)
from processual_api.admin_marketplace.subscription_top_up_grant_persistence import (
    SqlAlchemySubscriptionTopUpGrantRepository,
)
from processual_api.admin_marketplace.subscription_top_up_reversal_persistence import (
    SqlAlchemySubscriptionTopUpReversalRepository,
)
from processual_api.billing.commercial_top_up_repositories import (
    SqlAlchemyCommercialTopUpAuditRepository,
    SqlAlchemyCommercialTopUpGrantRepository,
    SqlAlchemyCommercialTopUpOrderRepository,
    SqlAlchemyCommercialTopUpPaymentRepository,
)


class SqlAlchemyAdminMarketplaceUnitOfWork:
    """Transaction boundary for Admin Marketplace persistence."""

    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._committed = False

    async def __aenter__(self) -> SqlAlchemyAdminMarketplaceUnitOfWork:
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
        self.lemon_squeezy_webhook_inbox = SqlAlchemyLemonSqueezyWebhookInboxRepository(session)
        self.lemon_squeezy_reconciliation_decisions = (
            SqlAlchemyLemonSqueezyReconciliationDecisionRepository(session)
        )
        self.lemon_squeezy_bindings = SqlAlchemyLemonSqueezyBindingRepository(session)
        self.assessment_quota_profiles = SqlAlchemyAssessmentQuotaProfileRepository(session)
        self.assessment_commercial_terms = SqlAlchemyAssessmentCommercialTermsRepository(session)
        self.assessment_subscription_bindings = (
            SqlAlchemyAssessmentSubscriptionBindingRepository(session)
        )
        self.subscription_runtime = SqlAlchemySubscriptionRuntimeRepository(session)
        self.subscription_delinquency = SqlAlchemySubscriptionDelinquencyRepository(session)
        self.subscription_quotas = SqlAlchemySubscriptionQuotaRepository(session)
        self.subscription_quota_cycles = SqlAlchemySubscriptionQuotaCycleRepository(session)
        self.subscription_quota_cycle_usage = SqlAlchemySubscriptionQuotaCycleUsageRepository(session)
        self.subscription_usage = SqlAlchemySubscriptionUsageRepository(session)
        self.subscription_runtime_transitions = SqlAlchemySubscriptionRuntimeTransitionRepository(session)
        self.top_up_orders = SqlAlchemyCommercialTopUpOrderRepository(session)
        self.top_up_payments = SqlAlchemyCommercialTopUpPaymentRepository(session)
        self.top_up_grants = SqlAlchemyCommercialTopUpGrantRepository(session)
        self.top_up_audit = SqlAlchemyCommercialTopUpAuditRepository(session)
        self.subscription_top_up_grants = SqlAlchemySubscriptionTopUpGrantRepository(session)
        self.subscription_top_up_reversals = SqlAlchemySubscriptionTopUpReversalRepository(session)
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


__all__ = ["SqlAlchemyAdminMarketplaceUnitOfWork"]
