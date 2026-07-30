from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from processual_api.db.base import Base


class CommercialSubscriptionCheckoutOrderRow(Base):
    __tablename__ = "commercial_subscription_checkout_orders"
    __table_args__ = (
        CheckConstraint(
            "included_units > 0",
            name="included_units_positive",
        ),
        CheckConstraint(
            "authoritative_price_usd > 0",
            name="authoritative_price_positive",
        ),
        CheckConstraint(
            "settlement_amount > 0",
            name="settlement_amount_positive",
        ),
        CheckConstraint(
            "version >= 0",
            name="version_nonnegative",
        ),
        CheckConstraint(
            "selected_channel IN ('local_tunisia', 'lemon_squeezy')",
            name="selected_channel_allowed",
        ),
        CheckConstraint(
            """
            state IN (
                'draft',
                'awaiting_payment',
                'payment_pending',
                'payment_verified',
                'payment_rejected',
                'activation_review',
                'activation_approved',
                'activation_rejected',
                'activated',
                'cancelled'
            )
            """,
            name="state_allowed",
        ),
        CheckConstraint(
            """
            (
                selected_channel = 'lemon_squeezy'
                AND settlement_currency = 'USD'
                AND settlement_amount = authoritative_price_usd
            )
            OR
            (
                selected_channel = 'local_tunisia'
                AND billing_country = 'TN'
                AND tunisian_address_eligible
                AND settlement_currency = 'TND'
            )
            """,
            name="channel_settlement_consistent",
        ),
        UniqueConstraint(
            "idempotency_key",
            name="uq_subscription_checkout_order_idempotency",
        ),
        Index(
            "ix_subscription_checkout_orders_tenant_state",
            "tenant_id",
            "state",
        ),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    customer_reference: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    plan_code: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    included_units: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    billing_cycle_reference: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    cycle_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    cycle_ends_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    authoritative_price_usd: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
    )
    selected_channel: Mapped[str] = mapped_column(
        String(32),
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
    quote_reference: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    quote_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    billing_country: Mapped[str | None] = mapped_column(
        String(2),
        nullable=True,
    )
    tunisian_address_eligible: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    customer_choice_preserved: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    state: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class CommercialSubscriptionPaymentEvidenceRow(Base):
    __tablename__ = "commercial_subscription_payment_evidence"
    __table_args__ = (
        CheckConstraint(
            """
            outcome IN (
                'pending',
                'verified',
                'rejected',
                'requires_review'
            )
            """,
            name="outcome_allowed",
        ),
        UniqueConstraint(
            "provider_reference",
            name="uq_subscription_payment_provider_reference",
        ),
        UniqueConstraint(
            "idempotency_key",
            name="uq_subscription_payment_idempotency",
        ),
        Index(
            "ix_subscription_payment_order_observed",
            "order_id",
            "observed_at",
        ),
    )

    evidence_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "commercial_subscription_checkout_orders.order_id",
            name="fk_subscription_payment_order",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    provider_reference: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    channel: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    outcome: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    verified_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 3),
        nullable=True,
    )
    verified_currency: Mapped[str | None] = mapped_column(
        String(3),
        nullable=True,
    )
    immutable_evidence_reference: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class CommercialSubscriptionActivationDecisionRow(Base):
    __tablename__ = "commercial_subscription_activation_decisions"
    __table_args__ = (
        CheckConstraint(
            """
            outcome IN (
                'approved',
                'denied',
                'requires_review'
            )
            """,
            name="outcome_allowed",
        ),
        CheckConstraint(
            "authority_reference = 'platform_admin'",
            name="platform_admin_exact",
        ),
        UniqueConstraint(
            "idempotency_key",
            name="uq_subscription_activation_decision_idempotency",
        ),
        Index(
            "ix_subscription_activation_order_occurred",
            "order_id",
            "occurred_at",
        ),
    )

    decision_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "commercial_subscription_checkout_orders.order_id",
            name="fk_subscription_activation_order",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    outcome: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
    )
    actor_reference: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    authority_reference: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )
    approval_reference: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


COMMERCIAL_SUBSCRIPTION_CHECKOUT_MODELS = (
    CommercialSubscriptionCheckoutOrderRow,
    CommercialSubscriptionPaymentEvidenceRow,
    CommercialSubscriptionActivationDecisionRow,
)


__all__ = [
    "COMMERCIAL_SUBSCRIPTION_CHECKOUT_MODELS",
    *[model.__name__ for model in COMMERCIAL_SUBSCRIPTION_CHECKOUT_MODELS],
]
