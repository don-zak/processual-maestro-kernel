from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
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

from processual_api.admin_marketplace.lemon_squeezy_inbox import (
    LemonSqueezyWebhookInboxEntry,
)
from processual_api.db.base import Base


class AdminMarketLemonSqueezyWebhookInbox(Base):
    __tablename__ = "admin_market_lemon_squeezy_webhook_inbox"
    __table_args__ = (
        CheckConstraint(
            "processing_status IN ('received', 'processing', 'processed', 'rejected')",
            name="status_allowed",
        ),
        CheckConstraint("attempt_count >= 0", name="attempt_nonnegative"),
        CheckConstraint(
            "length(event_identity_hash) = 64 AND length(payload_digest) = 64",
            name="digest_lengths",
        ),
        CheckConstraint(
            "(processing_status = 'processed' AND processed_at IS NOT NULL AND rejected_at IS NULL) "
            "OR (processing_status = 'rejected' AND rejected_at IS NOT NULL AND processed_at IS NULL) "
            "OR (processing_status IN ('received', 'processing') AND processed_at IS NULL AND rejected_at IS NULL)",
            name="terminal_timestamps",
        ),
        UniqueConstraint(
            "event_identity_hash",
            name="uq_admin_market_ls_webhook_event_identity",
        ),
        UniqueConstraint(
            "payload_digest",
            name="uq_admin_market_ls_webhook_payload_digest",
        ),
        UniqueConstraint(
            "store_id",
            "event_name",
            "resource_type",
            "external_resource_id",
            "customer_ref",
            "order_ref",
            "offer_ref",
            name="uq_admin_market_ls_webhook_resource_binding",
        ),
        Index(
            "ix_admin_market_ls_webhook_dispatch",
            "processing_status",
            "received_at",
            "claimed_at",
        ),
        Index(
            "ix_admin_market_ls_webhook_order_time",
            "order_ref",
            "received_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    event_identity_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    event_name: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False)
    external_resource_id: Mapped[str] = mapped_column(String(128), nullable=False)
    store_id: Mapped[str] = mapped_column(String(128), nullable=False)
    customer_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    order_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    offer_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    test_mode: Mapped[bool] = mapped_column(Boolean, nullable=False)
    processing_status: Mapped[str] = mapped_column(String(24), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error_code: Mapped[str | None] = mapped_column(String(128))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SqlAlchemyLemonSqueezyWebhookInboxRepository:
    """Persistence-only access to verified Lemon Squeezy webhook inbox rows."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_event_identity_hash(
        self,
        event_identity_hash: str,
        *,
        for_update: bool = False,
    ) -> AdminMarketLemonSqueezyWebhookInbox | None:
        statement = select(AdminMarketLemonSqueezyWebhookInbox).where(
            AdminMarketLemonSqueezyWebhookInbox.event_identity_hash
            == event_identity_hash
        )
        if for_update:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    async def get_by_payload_digest(
        self,
        payload_digest: str,
        *,
        for_update: bool = False,
    ) -> AdminMarketLemonSqueezyWebhookInbox | None:
        statement = select(AdminMarketLemonSqueezyWebhookInbox).where(
            AdminMarketLemonSqueezyWebhookInbox.payload_digest == payload_digest
        )
        if for_update:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    async def get_by_id(
        self,
        inbox_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketLemonSqueezyWebhookInbox | None:
        statement = select(AdminMarketLemonSqueezyWebhookInbox).where(
            AdminMarketLemonSqueezyWebhookInbox.id == inbox_id
        )
        if for_update:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    def add(
        self,
        entry: LemonSqueezyWebhookInboxEntry | AdminMarketLemonSqueezyWebhookInbox,
    ) -> None:
        if isinstance(entry, AdminMarketLemonSqueezyWebhookInbox):
            row = entry
        else:
            row = AdminMarketLemonSqueezyWebhookInbox(
                id=entry.id,
                event_identity_hash=entry.event_identity_hash,
                payload_digest=entry.payload_digest,
                event_name=entry.event_name,
                resource_type=entry.resource_type,
                external_resource_id=entry.external_resource_id,
                store_id=entry.store_id,
                customer_ref=entry.customer_ref,
                order_ref=entry.order_ref,
                offer_ref=entry.offer_ref,
                test_mode=entry.test_mode,
                processing_status=entry.processing_status,
                attempt_count=entry.attempt_count,
                last_error_code=entry.last_error_code,
                received_at=entry.received_at,
                claimed_at=entry.claimed_at,
                processed_at=entry.processed_at,
                rejected_at=entry.rejected_at,
            )
        self._session.add(row)
