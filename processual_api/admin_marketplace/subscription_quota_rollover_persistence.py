from __future__ import annotations

import uuid
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


class AdminMarketSubscriptionQuotaCycle(Base):
    __tablename__ = "admin_market_subscription_quota_cycles"
    __table_args__ = (
        CheckConstraint("period_end > period_start", name="period_valid"),
        CheckConstraint("base_limit_units >= 0", name="base_nonnegative"),
        CheckConstraint("rollover_units >= 0", name="rollover_nonnegative"),
        CheckConstraint(
            "rollover_status IN ('available','locked_for_delinquency','restored','expired')",
            name="rollover_status",
        ),
        CheckConstraint(
            "used_units >= 0 AND used_units <= base_limit_units + rollover_units",
            name="usage_within_available",
        ),
        CheckConstraint("version >= 0", name="version_nonnegative"),
        UniqueConstraint(
            "subscription_id",
            "metric_code",
            "period_start",
            name="uq_admin_market_quota_cycle_period",
        ),
        UniqueConstraint(
            "source_cycle_id",
            name="uq_admin_market_quota_cycle_source",
        ),
        Index(
            "ix_admin_market_quota_cycle_customer_metric",
            "customer_ref",
            "metric_code",
            "period_end",
        ),
        Index(
            "ix_admin_market_quota_cycle_rollover_expiry",
            "rollover_status",
            "rollover_expires_at",
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
    source_cycle_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("admin_market_subscription_quota_cycles.id", ondelete="RESTRICT"),
    )
    customer_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    quota_profile_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    metric_code: Mapped[str] = mapped_column(String(128), nullable=False)
    period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    base_limit_units: Mapped[int] = mapped_column(BigInteger, nullable=False)
    rollover_units: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
    )
    rollover_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="available",
    )
    rollover_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    rollover_locked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    rollover_restored_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    rollover_expired_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    used_units: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
    )
    version: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
    )
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

    @property
    def spendable_rollover_units(self) -> int:
        if self.rollover_status not in {"available", "restored"}:
            return 0
        return self.rollover_units

    @property
    def available_units(self) -> int:
        return self.base_limit_units + self.spendable_rollover_units - self.used_units


class SqlAlchemySubscriptionQuotaCycleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(
        self,
        cycle_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketSubscriptionQuotaCycle | None:
        statement = select(AdminMarketSubscriptionQuotaCycle).where(
            AdminMarketSubscriptionQuotaCycle.id == cycle_id
        )
        if for_update:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    async def get_by_period(
        self,
        *,
        subscription_id: uuid.UUID,
        metric_code: str,
        period_start: datetime,
        for_update: bool = False,
    ) -> AdminMarketSubscriptionQuotaCycle | None:
        statement = select(AdminMarketSubscriptionQuotaCycle).where(
            AdminMarketSubscriptionQuotaCycle.subscription_id == subscription_id,
            AdminMarketSubscriptionQuotaCycle.metric_code == metric_code,
            AdminMarketSubscriptionQuotaCycle.period_start == period_start,
        )
        if for_update:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    async def get_by_source_cycle_id(
        self,
        source_cycle_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketSubscriptionQuotaCycle | None:
        statement = select(AdminMarketSubscriptionQuotaCycle).where(
            AdminMarketSubscriptionQuotaCycle.source_cycle_id == source_cycle_id
        )
        if for_update:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    async def list_rollover_cycles(
        self,
        *,
        subscription_id: uuid.UUID,
        for_update: bool = False,
    ) -> list[AdminMarketSubscriptionQuotaCycle]:
        statement = select(AdminMarketSubscriptionQuotaCycle).where(
            AdminMarketSubscriptionQuotaCycle.subscription_id == subscription_id,
            AdminMarketSubscriptionQuotaCycle.rollover_units > 0,
            AdminMarketSubscriptionQuotaCycle.rollover_status != "expired",
        )
        if for_update:
            statement = statement.with_for_update()
        result = await self._session.scalars(statement)
        return list(result)

    def add(self, cycle: AdminMarketSubscriptionQuotaCycle) -> None:
        self._session.add(cycle)


__all__ = [
    "AdminMarketSubscriptionQuotaCycle",
    "SqlAlchemySubscriptionQuotaCycleRepository",
]
