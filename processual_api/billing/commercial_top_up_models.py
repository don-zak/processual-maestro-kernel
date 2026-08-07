from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    event,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from processual_api.db.base import Base


def _uuid_column() -> Mapped[uuid.UUID]:
    return mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )


def _created_at_column() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class CommercialTopUpOrder(Base):
    __tablename__ = "commercial_top_up_orders"
    __table_args__ = (
        CheckConstraint("requested_units > 0", name="requested_units_positive"),
        CheckConstraint("bundle_count > 0", name="bundle_count_positive"),
        CheckConstraint("total_price_usd > 0", name="total_price_positive"),
        CheckConstraint(
            "channel IN ('local_tunisia', 'lemon_squeezy')",
            name="channel_allowed",
        ),
        CheckConstraint(
            "settlement_currency IN ('USD', 'TND')",
            name="settlement_currency_allowed",
        ),
        CheckConstraint(
            "settlement_amount > 0",
            name="settlement_amount_positive",
        ),
        CheckConstraint(
            """
            (
                channel = 'lemon_squeezy'
                AND settlement_currency = 'USD'
                AND settlement_amount = total_price_usd
                AND exchange_rate_usd_tnd IS NULL
                AND exchange_rate_source IS NULL
                AND exchange_rate_reference IS NULL
                AND exchange_rate_observed_at IS NULL
                AND exchange_rate_expires_at IS NULL
            )
            OR
            (
                channel = 'local_tunisia'
                AND settlement_currency = 'TND'
                AND exchange_rate_usd_tnd IS NOT NULL
                AND exchange_rate_usd_tnd > 0
                AND exchange_rate_source IS NOT NULL
                AND length(trim(exchange_rate_source)) > 0
                AND exchange_rate_reference IS NOT NULL
                AND length(trim(exchange_rate_reference)) > 0
                AND exchange_rate_observed_at IS NOT NULL
                AND exchange_rate_expires_at IS NOT NULL
                AND exchange_rate_expires_at
                    > exchange_rate_observed_at
            )
            """,
            name="channel_settlement_consistent",
        ),
        CheckConstraint(
            """
            state IN (
                'draft',
                'awaiting_confirmation',
                'awaiting_payment',
                'payment_pending',
                'payment_verified',
                'payment_rejected',
                'grant_pending',
                'granted',
                'failed',
                'cancelled'
            )
            """,
            name="state_allowed",
        ),
        UniqueConstraint(
            "idempotency_key",
            name="uq_commercial_top_up_orders_idempotency_key",
        ),
        Index(
            "ix_commercial_top_up_orders_account_state",
            "account_id",
            "state",
        ),
        Index(
            "ix_commercial_top_up_orders_customer_state",
            "customer_ref",
            "state",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_column()
    account_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    customer_ref: Mapped[str] = mapped_column(String(128), nullable=False)
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
    plan_code: Mapped[str] = mapped_column(String(128), nullable=False)
    plan_catalog_version: Mapped[str] = mapped_column(String(64), nullable=False)
    requested_units: Mapped[int] = mapped_column(nullable=False)
    bundle_count: Mapped[int] = mapped_column(nullable=False)
    total_price_usd: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
    )
    settlement_currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
    )
    settlement_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 3),
        nullable=False,
    )
    exchange_rate_usd_tnd: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 6),
    )
    exchange_rate_source: Mapped[str | None] = mapped_column(
        String(255),
    )
    exchange_rate_reference: Mapped[str | None] = mapped_column(
        String(255),
    )
    exchange_rate_observed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    exchange_rate_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_variant_id: Mapped[str | None] = mapped_column(String(128))
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    state: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="draft",
    )
    created_at: Mapped[datetime] = _created_at_column()


class CommercialTopUpPaymentEvidence(Base):
    __tablename__ = "commercial_top_up_payment_evidence"
    __table_args__ = (
        CheckConstraint(
            "outcome IN ('verified', 'rejected', 'pending')",
            name="outcome_allowed",
        ),
        CheckConstraint(
            "verified_amount IS NULL OR verified_amount > 0",
            name="verified_amount_positive",
        ),
        CheckConstraint(
            "verified_currency IS NULL OR length(verified_currency) = 3",
            name="verified_currency_length",
        ),
        UniqueConstraint(
            "provider_reference",
            name="uq_commercial_top_up_payment_provider_reference",
        ),
        Index(
            "ix_commercial_top_up_payment_order",
            "order_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_column()
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("commercial_top_up_orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider_reference: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    outcome: Mapped[str] = mapped_column(String(24), nullable=False)
    verified_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 3),
    )
    verified_currency: Mapped[str | None] = mapped_column(String(3))
    immutable_evidence_reference: Mapped[str | None] = mapped_column(
        String(500),
    )
    created_at: Mapped[datetime] = _created_at_column()


class CommercialTopUpGrant(Base):
    __tablename__ = "commercial_top_up_grants"
    __table_args__ = (
        CheckConstraint("units > 0", name="units_positive"),
        CheckConstraint(
            "outcome IN ('granted', 'duplicate', 'blocked')",
            name="outcome_allowed",
        ),
        UniqueConstraint(
            "grant_idempotency_key",
            name="uq_commercial_top_up_grants_idempotency_key",
        ),
        UniqueConstraint(
            "order_id",
            name="uq_commercial_top_up_grants_order_id",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_column()
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("commercial_top_up_orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    outcome: Mapped[str] = mapped_column(String(24), nullable=False)
    units: Mapped[int] = mapped_column(nullable=False)
    grant_idempotency_key: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = _created_at_column()


class CommercialTopUpAuditRecord(Base):
    __tablename__ = "commercial_top_up_audit_records"
    __table_args__ = (
        CheckConstraint(
            """
            action IN (
                'order_created',
                'order_confirmed',
                'payment_recorded',
                'payment_verified',
                'payment_rejected',
                'grant_requested',
                'grant_applied',
                'grant_duplicate',
                'grant_blocked',
                'reconciliation_flagged'
            )
            """,
            name="action_allowed",
        ),
        UniqueConstraint(
            "event_ref",
            name="uq_commercial_top_up_audit_event_ref",
        ),
        Index(
            "ix_commercial_top_up_audit_order_time",
            "order_id",
            "occurred_at",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_column()
    event_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("commercial_top_up_orders.id", ondelete="RESTRICT"),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(String(48), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    actor_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    evidence_reference: Mapped[str] = mapped_column(String(500), nullable=False)
    payload_digest: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = _created_at_column()


@event.listens_for(CommercialTopUpAuditRecord, "before_update")
def _reject_audit_update(*_: object) -> None:
    raise ValueError("commercial top-up audit records are append-only")


@event.listens_for(CommercialTopUpAuditRecord, "before_delete")
def _reject_audit_delete(*_: object) -> None:
    raise ValueError("commercial top-up audit records are append-only")


COMMERCIAL_TOP_UP_MODELS = (
    CommercialTopUpOrder,
    CommercialTopUpPaymentEvidence,
    CommercialTopUpGrant,
    CommercialTopUpAuditRecord,
)


__all__ = [
    "COMMERCIAL_TOP_UP_MODELS",
    *[model.__name__ for model in COMMERCIAL_TOP_UP_MODELS],
]
