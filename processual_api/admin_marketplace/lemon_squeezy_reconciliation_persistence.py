from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, Uuid, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from processual_api.db.base import Base


class AdminMarketLemonSqueezyReconciliationDecision(Base):
    __tablename__ = "admin_market_lemon_squeezy_reconciliation_decisions"
    __table_args__ = (
        CheckConstraint(
            "action IN ('ignore', 'reconcile', 'requires_review')",
            name="action_allowed",
        ),
        CheckConstraint("length(event_identity_hash) = 64", name="identity_hash_length"),
        CheckConstraint("length(reason_code) BETWEEN 1 AND 128", name="reason_length"),
        UniqueConstraint("inbox_id", name="uq_admin_market_ls_reconciliation_inbox"),
        UniqueConstraint(
            "event_identity_hash",
            name="uq_admin_market_ls_reconciliation_event_identity",
        ),
        Index(
            "ix_admin_market_ls_reconciliation_action_time",
            "action",
            "decided_at",
        ),
        Index(
            "ix_admin_market_ls_reconciliation_order_time",
            "order_ref",
            "decided_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    inbox_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("admin_market_lemon_squeezy_webhook_inbox.id", ondelete="RESTRICT"),
        nullable=False,
    )
    event_identity_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    customer_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    order_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    offer_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(24), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(128), nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


@dataclass(frozen=True, slots=True)
class LemonSqueezyReconciliationDecisionRecord:
    id: uuid.UUID
    inbox_id: uuid.UUID
    event_identity_hash: str
    customer_ref: str
    order_ref: str
    offer_ref: str
    action: str
    reason_code: str
    decided_at: datetime


class LemonSqueezyReconciliationDecisionRepository(Protocol):
    async def get_by_inbox_id(
        self,
        inbox_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketLemonSqueezyReconciliationDecision | None: ...

    def add(
        self,
        decision: LemonSqueezyReconciliationDecisionRecord,
    ) -> None: ...


class SqlAlchemyLemonSqueezyReconciliationDecisionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_inbox_id(
        self,
        inbox_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketLemonSqueezyReconciliationDecision | None:
        statement = select(AdminMarketLemonSqueezyReconciliationDecision).where(
            AdminMarketLemonSqueezyReconciliationDecision.inbox_id == inbox_id
        )
        if for_update:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    async def get_by_event_identity_hash(
        self,
        event_identity_hash: str,
        *,
        for_update: bool = False,
    ) -> AdminMarketLemonSqueezyReconciliationDecision | None:
        statement = select(AdminMarketLemonSqueezyReconciliationDecision).where(
            AdminMarketLemonSqueezyReconciliationDecision.event_identity_hash
            == event_identity_hash
        )
        if for_update:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    def add(
        self,
        decision: LemonSqueezyReconciliationDecisionRecord
        | AdminMarketLemonSqueezyReconciliationDecision,
    ) -> None:
        if isinstance(decision, AdminMarketLemonSqueezyReconciliationDecision):
            row = decision
        else:
            row = AdminMarketLemonSqueezyReconciliationDecision(
                id=decision.id,
                inbox_id=decision.inbox_id,
                event_identity_hash=decision.event_identity_hash,
                customer_ref=decision.customer_ref,
                order_ref=decision.order_ref,
                offer_ref=decision.offer_ref,
                action=decision.action,
                reason_code=decision.reason_code,
                decided_at=decision.decided_at,
            )
        self._session.add(row)
