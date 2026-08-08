from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from processual_api.db.base import Base


class AdminMarketSubscriptionDelinquency(Base):
    __tablename__ = "admin_market_subscription_delinquency"
    __table_args__ = (
        CheckConstraint(
            "state IN ('grace_degraded','delinquent_read_only',"
            "'account_frozen','pending_deletion','resolved')",
            name="state",
        ),
        CheckConstraint("missed_billing_cycles >= 0", name="missed_cycles"),
        CheckConstraint(
            "grace_usage_percent BETWEEN 0 AND 100",
            name="grace_usage_percent",
        ),
        UniqueConstraint(
            "subscription_id",
            name="uq_admin_market_subscription_delinquency_subscription",
        ),
        Index(
            "ix_admin_market_subscription_delinquency_state",
            "state",
            "deletion_eligible_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("admin_market_subscriptions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    customer_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    missed_billing_cycles: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    last_failed_cycle_key: Mapped[str | None] = mapped_column(String(7))
    first_failed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    last_failed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    grace_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    grace_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    grace_usage_percent: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=25,
    )
    frozen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deletion_eligible_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class SqlAlchemySubscriptionDelinquencyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_subscription_id(
        self,
        subscription_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketSubscriptionDelinquency | None:
        statement = select(AdminMarketSubscriptionDelinquency).where(
            AdminMarketSubscriptionDelinquency.subscription_id == subscription_id
        )
        if for_update:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    def add(self, record: AdminMarketSubscriptionDelinquency) -> None:
        self._session.add(record)


__all__ = [
    "AdminMarketSubscriptionDelinquency",
    "SqlAlchemySubscriptionDelinquencyRepository",
]
