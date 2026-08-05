from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, Uuid, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from processual_api.db.base import Base


class AdminMarketSubscriptionRuntimeTransition(Base):
    __tablename__ = "admin_market_subscription_runtime_transitions"
    __table_args__ = (
        CheckConstraint("from_stage IN ('active','grace','suspended','terminated')", name="from_stage"),
        CheckConstraint("to_stage IN ('active','grace','suspended','terminated')", name="to_stage"),
        UniqueConstraint("reconciliation_decision_id", name="uq_admin_market_subscription_transition_decision"),
        Index("ix_admin_market_subscription_transition_subscription_time", "subscription_id", "effective_at"),
        Index("ix_admin_market_subscription_transition_customer_time", "customer_ref", "effective_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    runtime_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("admin_market_subscription_runtime.id", ondelete="RESTRICT"), nullable=False)
    subscription_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("admin_market_subscriptions.id", ondelete="RESTRICT"), nullable=False)
    reconciliation_decision_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("admin_market_lemon_squeezy_reconciliation_decisions.id", ondelete="RESTRICT"), nullable=False)
    customer_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    event_name: Mapped[str] = mapped_column(String(64), nullable=False)
    from_stage: Mapped[str] = mapped_column(String(24), nullable=False)
    to_stage: Mapped[str] = mapped_column(String(24), nullable=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class SqlAlchemySubscriptionRuntimeTransitionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_decision_id(self, decision_id: uuid.UUID, *, for_update: bool = False) -> AdminMarketSubscriptionRuntimeTransition | None:
        statement = select(AdminMarketSubscriptionRuntimeTransition).where(
            AdminMarketSubscriptionRuntimeTransition.reconciliation_decision_id == decision_id
        )
        if for_update:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    def add(self, transition: AdminMarketSubscriptionRuntimeTransition) -> None:
        self._session.add(transition)
