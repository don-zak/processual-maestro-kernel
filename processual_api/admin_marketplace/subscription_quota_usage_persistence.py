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


class AdminMarketSubscriptionQuotaCycleUsage(Base):
    __tablename__ = "admin_market_subscription_quota_cycle_usage"
    __table_args__ = (
        UniqueConstraint(
            "idempotency_key_hash",
            name="uq_admin_market_quota_cycle_usage_idempotency",
        ),
        Index(
            "ix_admin_market_quota_cycle_usage_cycle_time",
            "quota_cycle_id",
            "occurred_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    quota_cycle_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("admin_market_subscription_quota_cycles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("admin_market_subscriptions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    customer_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    metric_code: Mapped[str] = mapped_column(String(128), nullable=False)
    units: Mapped[int] = mapped_column(BigInteger, nullable=False)
    idempotency_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    dimensions_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SqlAlchemySubscriptionQuotaCycleUsageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_idempotency_hash(
        self,
        value: str,
        *,
        for_update: bool = False,
    ) -> AdminMarketSubscriptionQuotaCycleUsage | None:
        statement = select(AdminMarketSubscriptionQuotaCycleUsage).where(
            AdminMarketSubscriptionQuotaCycleUsage.idempotency_key_hash == value
        )
        if for_update:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    async def sum_units_since(
        self,
        *,
        quota_cycle_id: uuid.UUID,
        occurred_at: datetime,
    ) -> int:
        statement = select(
            func.coalesce(func.sum(AdminMarketSubscriptionQuotaCycleUsage.units), 0)
        ).where(
            AdminMarketSubscriptionQuotaCycleUsage.quota_cycle_id == quota_cycle_id,
            AdminMarketSubscriptionQuotaCycleUsage.occurred_at >= occurred_at,
        )
        return int(await self._session.scalar(statement) or 0)

    def add(self, usage: AdminMarketSubscriptionQuotaCycleUsage) -> None:
        self._session.add(usage)


__all__ = [
    "AdminMarketSubscriptionQuotaCycleUsage",
    "SqlAlchemySubscriptionQuotaCycleUsageRepository",
]
