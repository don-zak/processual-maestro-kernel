from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from processual_api.admin_marketplace.models import (
    AdminMarketAuditRecord,
    AdminMarketOffer,
    AdminMarketOrder,
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
    "SqlAlchemyCommercialAuditRepository",
    "SqlAlchemyOfferRepository",
    "SqlAlchemyOrderRepository",
    "SqlAlchemyPlanRepository",
    "SqlAlchemySubscriptionRepository",
    "SqlAlchemyTrialRepository",
]
