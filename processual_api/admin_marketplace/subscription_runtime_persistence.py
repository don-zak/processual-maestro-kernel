from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, Uuid, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from processual_api.db.base import Base


class AdminMarketSubscriptionRuntime(Base):
    __tablename__ = "admin_market_subscription_runtime"
    __table_args__ = (
        CheckConstraint("access_stage IN ('active','grace','suspended','terminated')", name="stage"),
        CheckConstraint("version >= 0", name="version"),
        UniqueConstraint("subscription_id", name="uq_admin_market_subscription_runtime_subscription"),
        Index("ix_admin_market_subscription_runtime_customer_stage", "customer_ref", "access_stage"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subscription_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("admin_market_subscriptions.id", ondelete="RESTRICT"), nullable=False)
    customer_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    entitlement_profile_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    quota_profile_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    access_stage: Mapped[str] = mapped_column(String(24), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    grace_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    terminated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class AdminMarketSubscriptionQuotaAccount(Base):
    __tablename__ = "admin_market_subscription_quota_accounts"
    __table_args__ = (
        CheckConstraint("period_end > period_start", name="period"),
        CheckConstraint("limit_units >= 0 AND used_units >= 0 AND used_units <= limit_units", name="units"),
        CheckConstraint("version >= 0", name="version"),
        UniqueConstraint("subscription_id", "metric_code", "period_start", name="uq_admin_market_subscription_quota_period"),
        Index("ix_admin_market_subscription_quota_customer_metric", "customer_ref", "metric_code", "period_end"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subscription_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("admin_market_subscriptions.id", ondelete="RESTRICT"), nullable=False)
    customer_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    quota_profile_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    metric_code: Mapped[str] = mapped_column(String(128), nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    limit_units: Mapped[int] = mapped_column(BigInteger, nullable=False)
    used_units: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class AdminMarketSubscriptionUsageLedger(Base):
    __tablename__ = "admin_market_subscription_usage_ledger"
    __table_args__ = (
        CheckConstraint("units > 0", name="units"),
        CheckConstraint("length(idempotency_key_hash) = 64 AND length(dimensions_digest) = 64", name="digests"),
        UniqueConstraint("idempotency_key_hash", name="uq_admin_market_subscription_usage_idempotency"),
        Index("ix_admin_market_subscription_usage_subscription_time", "subscription_id", "occurred_at"),
        Index("ix_admin_market_subscription_usage_customer_metric", "customer_ref", "metric_code", "occurred_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quota_account_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("admin_market_subscription_quota_accounts.id", ondelete="RESTRICT"), nullable=False)
    subscription_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("admin_market_subscriptions.id", ondelete="RESTRICT"), nullable=False)
    customer_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    metric_code: Mapped[str] = mapped_column(String(128), nullable=False)
    units: Mapped[int] = mapped_column(BigInteger, nullable=False)
    idempotency_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    dimensions_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class SqlAlchemySubscriptionRuntimeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_subscription_id(self, subscription_id: uuid.UUID, *, for_update: bool = False) -> AdminMarketSubscriptionRuntime | None:
        statement = select(AdminMarketSubscriptionRuntime).where(AdminMarketSubscriptionRuntime.subscription_id == subscription_id)
        if for_update:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    def add(self, runtime: AdminMarketSubscriptionRuntime) -> None:
        self._session.add(runtime)


class SqlAlchemySubscriptionQuotaRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_current(self, *, subscription_id: uuid.UUID, metric_code: str, occurred_at: datetime, for_update: bool = False) -> AdminMarketSubscriptionQuotaAccount | None:
        statement = select(AdminMarketSubscriptionQuotaAccount).where(
            AdminMarketSubscriptionQuotaAccount.subscription_id == subscription_id,
            AdminMarketSubscriptionQuotaAccount.metric_code == metric_code,
            AdminMarketSubscriptionQuotaAccount.period_start <= occurred_at,
            AdminMarketSubscriptionQuotaAccount.period_end > occurred_at,
        )
        if for_update:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    def add(self, account: AdminMarketSubscriptionQuotaAccount) -> None:
        self._session.add(account)


class SqlAlchemySubscriptionUsageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_idempotency_hash(self, value: str, *, for_update: bool = False) -> AdminMarketSubscriptionUsageLedger | None:
        statement = select(AdminMarketSubscriptionUsageLedger).where(AdminMarketSubscriptionUsageLedger.idempotency_key_hash == value)
        if for_update:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    def add(self, usage: AdminMarketSubscriptionUsageLedger) -> None:
        self._session.add(usage)
