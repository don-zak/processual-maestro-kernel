from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from processual_api.db.base import Base


class AdminMarketLemonCheckoutBinding(Base):
    __tablename__ = "admin_market_lemon_checkout_bindings"
    __table_args__ = (
        CheckConstraint(
            "checkout_creation_status IN ('not_started','creating','ready','uncertain')",
            name="checkout_creation_status_allowed",
        ),
        CheckConstraint(
            "(checkout_creation_status = 'ready' AND provider_checkout_id IS NOT NULL) "
            "OR checkout_creation_status != 'ready'",
            name="ready_checkout_has_provider_id",
        ),
        UniqueConstraint(
            "order_id",
            name="uq_admin_market_lemon_checkout_bindings_order_id",
        ),
        UniqueConstraint(
            "provider_checkout_id",
            name="uq_admin_market_lemon_checkout_bindings_provider_checkout_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("admin_market_orders.id", ondelete="RESTRICT"),
        nullable=False,
    )
    provider_variant_id: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_checkout_id: Mapped[str | None] = mapped_column(String(128))
    checkout_creation_status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="not_started",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


__all__ = ["AdminMarketLemonCheckoutBinding"]
