from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    func,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from processual_api.db.base import Base


class AdminMarketSubscriptionTopUpReversal(Base):
    __tablename__ = "admin_market_subscription_top_up_reversals"
    __table_args__ = (
        CheckConstraint("units > 0", name="units_positive"),
        CheckConstraint(
            "outcome IN ('reversed','manual_review')",
            name="outcome_allowed",
        ),
        UniqueConstraint("provider_event_ref", name="uq_admin_market_top_up_reversal_provider_event"),
        UniqueConstraint("grant_id", name="uq_admin_market_top_up_reversal_grant"),
        Index(
            "ix_admin_market_top_up_reversal_subscription_cycle",
            "subscription_id",
            "quota_cycle_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("commercial_top_up_orders.id", ondelete="RESTRICT"),
        nullable=False,
    )
    grant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("admin_market_subscription_top_up_grants.id", ondelete="RESTRICT"),
        nullable=False,
    )
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("admin_market_subscriptions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    quota_cycle_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("admin_market_subscription_quota_cycles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    customer_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_event_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    units: Mapped[int] = mapped_column(BigInteger, nullable=False)
    outcome: Mapped[str] = mapped_column(String(24), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(128), nullable=False)
    reversed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class SqlAlchemySubscriptionTopUpReversalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_grant_id(
        self,
        grant_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketSubscriptionTopUpReversal | None:
        statement = select(AdminMarketSubscriptionTopUpReversal).where(
            AdminMarketSubscriptionTopUpReversal.grant_id == grant_id
        )
        if for_update:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    async def get_by_provider_event_ref(
        self,
        provider_event_ref: str,
        *,
        for_update: bool = False,
    ) -> AdminMarketSubscriptionTopUpReversal | None:
        statement = select(AdminMarketSubscriptionTopUpReversal).where(
            AdminMarketSubscriptionTopUpReversal.provider_event_ref == provider_event_ref
        )
        if for_update:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    async def list_manual_review(
        self,
        *,
        limit: int = 100,
    ) -> Sequence[AdminMarketSubscriptionTopUpReversal]:
        result = await self._session.scalars(
            select(AdminMarketSubscriptionTopUpReversal)
            .where(AdminMarketSubscriptionTopUpReversal.outcome == "manual_review")
            .order_by(
                AdminMarketSubscriptionTopUpReversal.reversed_at.asc(),
                AdminMarketSubscriptionTopUpReversal.id.asc(),
            )
            .limit(max(1, min(limit, 500)))
        )
        return tuple(result.all())

    def add(self, reversal: AdminMarketSubscriptionTopUpReversal) -> None:
        self._session.add(reversal)


__all__ = [
    "AdminMarketSubscriptionTopUpReversal",
    "SqlAlchemySubscriptionTopUpReversalRepository",
]
