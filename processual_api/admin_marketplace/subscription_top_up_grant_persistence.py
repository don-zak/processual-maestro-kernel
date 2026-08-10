from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
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


class AdminMarketSubscriptionTopUpGrant(Base):
    __tablename__ = "admin_market_subscription_top_up_grants"
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_admin_market_top_up_grant_order"),
        UniqueConstraint(
            "grant_idempotency_key",
            name="uq_admin_market_top_up_grant_idempotency",
        ),
        Index(
            "ix_admin_market_top_up_grant_subscription_cycle",
            "subscription_id",
            "quota_cycle_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("commercial_top_up_orders.id", ondelete="RESTRICT"),
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
    plan_code: Mapped[str] = mapped_column(String(128), nullable=False)
    plan_catalog_version: Mapped[str] = mapped_column(String(64), nullable=False)
    units: Mapped[int] = mapped_column(BigInteger, nullable=False)
    grant_idempotency_key: Mapped[str] = mapped_column(String(500), nullable=False)
    provider_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class SqlAlchemySubscriptionTopUpGrantRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_order_id(
        self,
        order_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketSubscriptionTopUpGrant | None:
        statement = select(AdminMarketSubscriptionTopUpGrant).where(
            AdminMarketSubscriptionTopUpGrant.order_id == order_id
        )
        if for_update:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    async def get_by_idempotency_key(
        self,
        grant_idempotency_key: str,
        *,
        for_update: bool = False,
    ) -> AdminMarketSubscriptionTopUpGrant | None:
        statement = select(AdminMarketSubscriptionTopUpGrant).where(
            AdminMarketSubscriptionTopUpGrant.grant_idempotency_key
            == grant_idempotency_key
        )
        if for_update:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    def add(self, grant: AdminMarketSubscriptionTopUpGrant) -> None:
        self._session.add(grant)


__all__ = [
    "AdminMarketSubscriptionTopUpGrant",
    "SqlAlchemySubscriptionTopUpGrantRepository",
]
