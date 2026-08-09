from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Uuid, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from processual_api.db.base import Base


class AdminMarketAssessmentSubscriptionBinding(Base):
    __tablename__ = "admin_market_assessment_subscription_bindings"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    binding_ref: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("admin_market_subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    assessment_binding_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
    )
    assessment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    customer_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    public_plan_id: Mapped[str] = mapped_column(String(128), nullable=False)
    entitlement_source_plan_code: Mapped[str] = mapped_column(String(128), nullable=False)
    entitlement_plan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("admin_market_plans.id", ondelete="RESTRICT"),
        nullable=False,
    )
    entitlement_profile_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    quota_profile_ref: Mapped[str] = mapped_column(
        String(128),
        ForeignKey(
            "admin_market_assessment_quota_profiles.profile_ref",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    activation_idempotency_key_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class SqlAlchemyAssessmentSubscriptionBindingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_subscription_id(
        self,
        subscription_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketAssessmentSubscriptionBinding | None:
        statement = select(AdminMarketAssessmentSubscriptionBinding).where(
            AdminMarketAssessmentSubscriptionBinding.subscription_id == subscription_id
        )
        if for_update:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    async def get_by_assessment_binding_hash(
        self,
        assessment_binding_hash: str,
        *,
        for_update: bool = False,
    ) -> AdminMarketAssessmentSubscriptionBinding | None:
        statement = select(AdminMarketAssessmentSubscriptionBinding).where(
            AdminMarketAssessmentSubscriptionBinding.assessment_binding_hash
            == assessment_binding_hash.strip().lower()
        )
        if for_update:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    async def get_by_idempotency_key_hash(
        self,
        key_hash: str,
        *,
        for_update: bool = False,
    ) -> AdminMarketAssessmentSubscriptionBinding | None:
        statement = select(AdminMarketAssessmentSubscriptionBinding).where(
            AdminMarketAssessmentSubscriptionBinding.activation_idempotency_key_hash
            == key_hash
        )
        if for_update:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    def add(self, binding: AdminMarketAssessmentSubscriptionBinding) -> None:
        self._session.add(binding)


__all__ = [
    "AdminMarketAssessmentSubscriptionBinding",
    "SqlAlchemyAssessmentSubscriptionBindingRepository",
]
