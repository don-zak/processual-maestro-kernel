from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from processual_api.admin_marketplace.models import (
    AdminMarketAuditRecord,
    AdminMarketChannelEligibility,
    AdminMarketChannelSelection,
    AdminMarketCommercialDecision,
    AdminMarketEntitlementActivation,
    AdminMarketInvoice,
    AdminMarketOffer,
    AdminMarketOrder,
    AdminMarketPaymentDestination,
    AdminMarketPaymentVerification,
    AdminMarketPlan,
    AdminMarketSubscription,
    AdminMarketTrial,
)


class SqlAlchemyPlanRepository:
    """SQLAlchemy persistence operations for marketplace plans."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(
        self,
        plan_id: uuid.UUID,
    ) -> AdminMarketPlan | None:
        return await self._session.get(
            AdminMarketPlan,
            plan_id,
        )

    def add(
        self,
        plan: AdminMarketPlan,
    ) -> None:
        self._session.add(plan)


class SqlAlchemyOfferRepository:
    """SQLAlchemy persistence operations for marketplace offers."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(
        self,
        offer_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketOffer | None:
        statement = select(AdminMarketOffer).where(
            AdminMarketOffer.id == offer_id,
        )

        if for_update:
            statement = statement.with_for_update()

        return await self._session.scalar(statement)

    def add(
        self,
        offer: AdminMarketOffer,
    ) -> None:
        self._session.add(offer)


class SqlAlchemySubscriptionRepository:
    """SQLAlchemy persistence operations for marketplace subscriptions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(
        self,
        subscription_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketSubscription | None:
        statement = select(AdminMarketSubscription).where(
            AdminMarketSubscription.id == subscription_id,
        )

        if for_update:
            statement = statement.with_for_update()

        return await self._session.scalar(statement)

    def add(
        self,
        subscription: AdminMarketSubscription,
    ) -> None:
        self._session.add(subscription)


class SqlAlchemyTrialRepository:
    """SQLAlchemy persistence operations for marketplace trials."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(
        self,
        trial_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketTrial | None:
        statement = select(AdminMarketTrial).where(
            AdminMarketTrial.id == trial_id,
        )

        if for_update:
            statement = statement.with_for_update()

        return await self._session.scalar(statement)

    def add(
        self,
        trial: AdminMarketTrial,
    ) -> None:
        self._session.add(trial)


class SqlAlchemyOrderRepository:
    """SQLAlchemy persistence operations for marketplace orders."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(
        self,
        order_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketOrder | None:
        statement = select(AdminMarketOrder).where(
            AdminMarketOrder.id == order_id,
        )

        if for_update:
            statement = statement.with_for_update()

        return await self._session.scalar(statement)

    def add(
        self,
        order: AdminMarketOrder,
    ) -> None:
        self._session.add(order)


class SqlAlchemyPaymentDestinationRepository:
    """Persistence operations for Tunisian payment destinations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_all(
        self,
    ) -> Sequence[AdminMarketPaymentDestination]:
        statement = select(AdminMarketPaymentDestination).order_by(
            AdminMarketPaymentDestination.created_at.desc(),
            AdminMarketPaymentDestination.id.desc(),
        )
        result = await self._session.scalars(statement)
        return tuple(result.all())

    async def get_by_id(
        self,
        destination_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketPaymentDestination | None:
        statement = select(AdminMarketPaymentDestination).where(
            AdminMarketPaymentDestination.id == destination_id,
        )

        if for_update:
            statement = statement.with_for_update()

        return await self._session.scalar(statement)

    async def get_by_ref(
        self,
        destination_ref: str,
        *,
        for_update: bool = False,
    ) -> AdminMarketPaymentDestination | None:
        statement = select(AdminMarketPaymentDestination).where(
            AdminMarketPaymentDestination.destination_ref
            == destination_ref.strip().lower(),
        )

        if for_update:
            statement = statement.with_for_update()

        return await self._session.scalar(statement)

    async def get_by_creation_idempotency_key_hash(
        self,
        key_hash: str,
        *,
        for_update: bool = False,
    ) -> AdminMarketPaymentDestination | None:
        statement = select(AdminMarketPaymentDestination).where(
            AdminMarketPaymentDestination.creation_idempotency_key_hash
            == key_hash,
        )

        if for_update:
            statement = statement.with_for_update()

        return await self._session.scalar(statement)

    async def get_active_default(
        self,
        *,
        for_update: bool = False,
    ) -> AdminMarketPaymentDestination | None:
        statement = select(AdminMarketPaymentDestination).where(
            AdminMarketPaymentDestination.sales_channel == "maestro_direct",
            AdminMarketPaymentDestination.country_code == "TN",
            AdminMarketPaymentDestination.currency == "TND",
            AdminMarketPaymentDestination.status == "active",
            AdminMarketPaymentDestination.is_active.is_(True),
            AdminMarketPaymentDestination.is_default.is_(True),
        )

        if for_update:
            statement = statement.with_for_update()

        return await self._session.scalar(statement)

    def add(
        self,
        destination: AdminMarketPaymentDestination,
    ) -> None:
        self._session.add(destination)


class SqlAlchemyPaymentVerificationRepository:
    """Persistence operations for payment-verification decisions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(
        self,
        verification_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketPaymentVerification | None:
        statement = select(AdminMarketPaymentVerification).where(
            AdminMarketPaymentVerification.id == verification_id,
        )

        if for_update:
            statement = statement.with_for_update()

        return await self._session.scalar(statement)

    def add(
        self,
        verification: AdminMarketPaymentVerification,
    ) -> None:
        self._session.add(verification)


class SqlAlchemyInvoiceRepository:
    """SQLAlchemy persistence operations for marketplace invoices."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(
        self,
        invoice_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketInvoice | None:
        statement = select(AdminMarketInvoice).where(
            AdminMarketInvoice.id == invoice_id,
        )

        if for_update:
            statement = statement.with_for_update()

        return await self._session.scalar(statement)

    def add(
        self,
        invoice: AdminMarketInvoice,
    ) -> None:
        self._session.add(invoice)


class SqlAlchemyEntitlementActivationRepository:
    """Persistence for explicit entitlement-activation decisions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(
        self,
        activation_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketEntitlementActivation | None:
        statement = select(AdminMarketEntitlementActivation).where(
            AdminMarketEntitlementActivation.id == activation_id,
        )

        if for_update:
            statement = statement.with_for_update()

        return await self._session.scalar(statement)

    def add(
        self,
        activation: AdminMarketEntitlementActivation,
    ) -> None:
        self._session.add(activation)


class SqlAlchemyChannelEligibilityRepository:
    """Persistence operations for sales-channel eligibility decisions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(
        self,
        eligibility_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketChannelEligibility | None:
        statement = select(AdminMarketChannelEligibility).where(
            AdminMarketChannelEligibility.id == eligibility_id,
        )

        if for_update:
            statement = statement.with_for_update()

        return await self._session.scalar(statement)

    async def get_by_customer_ref(
        self,
        customer_ref: str,
        *,
        for_update: bool = False,
    ) -> AdminMarketChannelEligibility | None:
        statement = select(AdminMarketChannelEligibility).where(
            AdminMarketChannelEligibility.customer_ref == customer_ref,
        )

        if for_update:
            statement = statement.with_for_update()

        return await self._session.scalar(statement)

    def add(
        self,
        eligibility: AdminMarketChannelEligibility,
    ) -> None:
        self._session.add(eligibility)


class SqlAlchemyChannelSelectionRepository:
    """Persistence operations for explicit channel selections."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(
        self,
        selection_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketChannelSelection | None:
        statement = select(AdminMarketChannelSelection).where(
            AdminMarketChannelSelection.id == selection_id,
        )

        if for_update:
            statement = statement.with_for_update()

        return await self._session.scalar(statement)

    def add(
        self,
        selection: AdminMarketChannelSelection,
    ) -> None:
        self._session.add(selection)


class SqlAlchemyCommercialDecisionRepository:
    """Persistence operations for explicit commercial decisions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(
        self,
        decision_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketCommercialDecision | None:
        statement = select(AdminMarketCommercialDecision).where(
            AdminMarketCommercialDecision.id == decision_id,
        )

        if for_update:
            statement = statement.with_for_update()

        return await self._session.scalar(statement)

    def add(
        self,
        decision: AdminMarketCommercialDecision,
    ) -> None:
        self._session.add(decision)


class SqlAlchemyCommercialAuditRepository:
    """Append-only SQLAlchemy repository for commercial audit records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(
        self,
        audit_record_id: uuid.UUID,
    ) -> AdminMarketAuditRecord | None:
        return await self._session.get(
            AdminMarketAuditRecord,
            audit_record_id,
        )

    async def list_by_resource(
        self,
        *,
        resource_type: str,
        resource_id: str,
    ) -> Sequence[AdminMarketAuditRecord]:
        statement = (
            select(AdminMarketAuditRecord)
            .where(
                AdminMarketAuditRecord.resource_type == resource_type,
                AdminMarketAuditRecord.resource_id == resource_id,
            )
            .order_by(
                AdminMarketAuditRecord.occurred_at.asc(),
                AdminMarketAuditRecord.id.asc(),
            )
        )

        result = await self._session.scalars(statement)
        return tuple(result.all())

    def append(
        self,
        audit_record: AdminMarketAuditRecord,
    ) -> None:
        self._session.add(audit_record)


__all__ = [
    "SqlAlchemyChannelEligibilityRepository",
    "SqlAlchemyChannelSelectionRepository",
    "SqlAlchemyCommercialAuditRepository",
    "SqlAlchemyCommercialDecisionRepository",
    "SqlAlchemyEntitlementActivationRepository",
    "SqlAlchemyInvoiceRepository",
    "SqlAlchemyOfferRepository",
    "SqlAlchemyOrderRepository",
    "SqlAlchemyPaymentDestinationRepository",
    "SqlAlchemyPaymentVerificationRepository",
    "SqlAlchemyPlanRepository",
    "SqlAlchemySubscriptionRepository",
    "SqlAlchemyTrialRepository",
]
