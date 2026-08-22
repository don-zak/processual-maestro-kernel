from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, Uuid, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from processual_api.db.base import Base


class AdminMarketSubscriptionRuntime(Base):
    __tablename__ = "admin_market_subscription_runtime"
    __table_args__ = (
        CheckConstraint("access_stage IN ('active','grace','suspended','terminated')", name="stage"),
        CheckConstraint("version >= 0", name="version"),
        UniqueConstraint(
            "subscription_id",
            name="uq_admin_market_subscription_runtime_subscription",
        ),
        Index(
            "ix_admin_market_subscription_runtime_customer_stage",
            "customer_ref",
            "access_stage",
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
    entitlement_profile_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    quota_profile_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    access_stage: Mapped[str] = mapped_column(String(24), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    effective_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    grace_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    terminated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
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


class SqlAlchemySubscriptionRuntimeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_subscription_id(
        self,
        subscription_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketSubscriptionRuntime | None:
        statement = select(AdminMarketSubscriptionRuntime).where(
            AdminMarketSubscriptionRuntime.subscription_id == subscription_id
        )
        if for_update:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    def add(self, runtime: AdminMarketSubscriptionRuntime) -> None:
        self._session.add(runtime)


__all__ = [
    "AdminMarketSubscriptionRuntime",
    "SqlAlchemySubscriptionRuntimeRepository",
]
