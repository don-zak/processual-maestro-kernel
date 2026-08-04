from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
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


def _updated_at_column() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class AdminMarketPlan(Base):
    __tablename__ = "admin_market_plans"
    __table_args__ = (
        UniqueConstraint(
            "plan_code",
            name="uq_admin_market_plans_plan_code",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_column()
    plan_code: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    display_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    entitlement_profile_ref: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    quota_profile_ref: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    metadata_json: Mapped[dict[str, str]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = _created_at_column()
    updated_at: Mapped[datetime] = _updated_at_column()


class AdminMarketOffer(Base):
    __tablename__ = "admin_market_offers"
    __table_args__ = (
        CheckConstraint(
            """
            status IN (
                'draft',
                'under_review',
                'approved',
                'published',
                'suspended',
                'retired'
            )
            """,
            name="status_allowed",
        ),
        CheckConstraint(
            "amount >= 0",
            name="amount_nonnegative",
        ),
        CheckConstraint(
            "length(currency) = 3",
            name="currency_length",
        ),
        CheckConstraint(
            """
            expires_at IS NULL
            OR effective_at IS NULL
            OR expires_at > effective_at
            """,
            name="effective_window_valid",
        ),
        UniqueConstraint(
            "offer_code",
            name="uq_admin_market_offers_offer_code",
        ),
        Index(
            "ix_admin_market_offers_plan_status",
            "plan_id",
            "status",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_column()
    offer_code: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "admin_market_plans.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    display_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="draft",
    )
    effective_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    customer_specific: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    created_at: Mapped[datetime] = _created_at_column()
    updated_at: Mapped[datetime] = _updated_at_column()


class AdminMarketSubscription(Base):
    __tablename__ = "admin_market_subscriptions"
    __table_args__ = (
        CheckConstraint(
            """
            status IN (
                'pending',
                'active',
                'suspended',
                'cancelled',
                'expired'
            )
            """,
            name="status_allowed",
        ),
        CheckConstraint(
            """
            ends_at IS NULL
            OR starts_at IS NULL
            OR ends_at > starts_at
            """,
            name="active_window_valid",
        ),
        UniqueConstraint(
            "subscription_ref",
            name="uq_admin_market_subscriptions_subscription_ref",
        ),
        Index(
            "ix_admin_market_subscriptions_customer_status",
            "customer_ref",
            "status",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_column()
    subscription_ref: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    customer_ref: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    offer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "admin_market_offers.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "admin_market_plans.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="pending",
    )
    starts_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    created_at: Mapped[datetime] = _created_at_column()
    updated_at: Mapped[datetime] = _updated_at_column()


class AdminMarketTrial(Base):
    __tablename__ = "admin_market_trials"
    __table_args__ = (
        CheckConstraint(
            """
            status IN (
                'pending',
                'approved',
                'active',
                'suspended',
                'converted',
                'expired',
                'rejected'
            )
            """,
            name="status_allowed",
        ),
        CheckConstraint(
            """
            ends_at IS NULL
            OR starts_at IS NULL
            OR ends_at > starts_at
            """,
            name="active_window_valid",
        ),
        UniqueConstraint(
            "trial_ref",
            name="uq_admin_market_trials_trial_ref",
        ),
        Index(
            "ix_admin_market_trials_customer_status",
            "customer_ref",
            "status",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_column()
    trial_ref: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    customer_ref: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "admin_market_plans.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="pending",
    )
    starts_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    created_at: Mapped[datetime] = _created_at_column()
    updated_at: Mapped[datetime] = _updated_at_column()


class AdminMarketOrder(Base):
    __tablename__ = "admin_market_orders"
    __table_args__ = (
        CheckConstraint(
            """
            selected_channel IN (
                'maestro_direct',
                'lemon_squeezy'
            )
            """,
            name="selected_channel_allowed",
        ),
        CheckConstraint(
            """
            status IN (
                'draft',
                'submitted',
                'awaiting_payment_verification',
                'approved',
                'rejected',
                'cancelled',
                'fulfilled'
            )
            """,
            name="status_allowed",
        ),
        UniqueConstraint(
            "order_ref",
            name="uq_admin_market_orders_order_ref",
        ),
        Index(
            "ix_admin_market_orders_customer_status",
            "customer_ref",
            "status",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_column()
    order_ref: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    customer_ref: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    offer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "admin_market_offers.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    selected_channel: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="draft",
    )
    created_at: Mapped[datetime] = _created_at_column()
    updated_at: Mapped[datetime] = _updated_at_column()


class AdminMarketPaymentVerification(Base):
    __tablename__ = "admin_market_payment_verifications"
    __table_args__ = (
        CheckConstraint(
            """
            status IN (
                'pending',
                'verified',
                'rejected',
                'requires_review'
            )
            """,
            name="status_allowed",
        ),
        UniqueConstraint(
            "verification_ref",
            name=("uq_admin_market_payment_verifications_verification_ref"),
        ),
        Index(
            "ix_admin_market_payment_verifications_order_status",
            "order_id",
            "status",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_column()
    verification_ref: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "admin_market_orders.id",
            name="fk_admin_market_payment_verification_order",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="pending",
    )
    safe_reference: Mapped[str | None] = mapped_column(
        String(255),
    )
    created_at: Mapped[datetime] = _created_at_column()
    updated_at: Mapped[datetime] = _updated_at_column()


class AdminMarketInvoice(Base):
    __tablename__ = "admin_market_invoices"
    __table_args__ = (
        CheckConstraint(
            "amount >= 0",
            name="amount_nonnegative",
        ),
        CheckConstraint(
            "length(currency) = 3",
            name="currency_length",
        ),
        UniqueConstraint(
            "invoice_ref",
            name="uq_admin_market_invoices_invoice_ref",
        ),
        Index(
            "ix_admin_market_invoices_order",
            "order_id",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_column()
    invoice_ref: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "admin_market_orders.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
    )
    created_at: Mapped[datetime] = _created_at_column()


class AdminMarketEntitlementActivation(Base):
    __tablename__ = "admin_market_entitlement_activations"
    __table_args__ = (
        UniqueConstraint(
            "activation_ref",
            name=("uq_admin_market_entitlement_activations_activation_ref"),
        ),
        Index(
            "ix_admin_market_entitlement_subscription",
            "subscription_id",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_column()
    activation_ref: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    customer_ref: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "admin_market_subscriptions.id",
            name="fk_admin_market_entitlement_subscription",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    entitlement_profile_ref: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    automatic_activation_allowed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    created_at: Mapped[datetime] = _created_at_column()


class AdminMarketChannelEligibility(Base):
    __tablename__ = "admin_market_channel_eligibilities"
    __table_args__ = (
        CheckConstraint(
            """
            maestro_direct_status IN (
                'eligible',
                'ineligible',
                'requires_review'
            )
            """,
            name="maestro_direct_status_allowed",
        ),
        CheckConstraint(
            """
            lemon_squeezy_status IN (
                'eligible',
                'ineligible',
                'requires_review'
            )
            """,
            name="lemon_squeezy_status_allowed",
        ),
        CheckConstraint(
            "country_code IS NULL OR length(country_code) = 2",
            name="country_code_length",
        ),
        CheckConstraint(
            """
            NOT admin_review_required
            OR NOT automatic_activation_allowed
            """,
            name="review_blocks_automatic_activation",
        ),
        CheckConstraint(
            """
            NOT customer_choice_allowed
            OR (
                maestro_direct_status = 'eligible'
                AND lemon_squeezy_status = 'eligible'
            )
            """,
            name="customer_choice_requires_both_channels",
        ),
        CheckConstraint(
            """
            (
                maestro_direct_status != 'ineligible'
                AND lemon_squeezy_status != 'ineligible'
            )
            OR restriction_reason IS NOT NULL
            """,
            name="ineligible_requires_reason",
        ),
        UniqueConstraint(
            "customer_ref",
            name=("uq_admin_market_channel_eligibilities_customer_ref"),
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_column()
    customer_ref: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    country_code: Mapped[str | None] = mapped_column(
        String(2),
    )
    maestro_direct_status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
    )
    lemon_squeezy_status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
    )
    customer_choice_allowed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    admin_review_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    restriction_reason: Mapped[str | None] = mapped_column(
        String(500),
    )
    automatic_activation_allowed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    created_at: Mapped[datetime] = _created_at_column()
    updated_at: Mapped[datetime] = _updated_at_column()


class AdminMarketChannelSelection(Base):
    __tablename__ = "admin_market_channel_selections"
    __table_args__ = (
        CheckConstraint(
            """
            selected_channel IN (
                'maestro_direct',
                'lemon_squeezy'
            )
            """,
            name="selected_channel_allowed",
        ),
        CheckConstraint(
            """
            customer_consented
            OR administrator_override_reason IS NOT NULL
            """,
            name="consent_or_override_required",
        ),
        Index(
            "ix_admin_market_channel_selections_customer",
            "customer_ref",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_column()
    customer_ref: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    selected_channel: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    eligible_channels_json: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
    )
    customer_consented: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    administrator_override_reason: Mapped[str | None] = mapped_column(
        String(500),
    )
    created_at: Mapped[datetime] = _created_at_column()


class AdminMarketCommercialDecision(Base):
    __tablename__ = "admin_market_commercial_decisions"
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
        UniqueConstraint(
            "decision_ref",
            name=("uq_admin_market_commercial_decisions_decision_ref"),
        ),
        Index(
            "ix_admin_market_decisions_resource",
            "resource_type",
            "resource_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_column()
    decision_ref: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    resource_type: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    resource_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    outcome: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
    )
    reason_code: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    created_at: Mapped[datetime] = _created_at_column()


class AdminMarketAuditRecord(Base):
    __tablename__ = "admin_market_audit_records"
    __table_args__ = (
        CheckConstraint(
            "platform_authority = 'platform_admin'",
            name="platform_authority_exact",
        ),
        CheckConstraint(
            """
            action IN (
                'authority_checked',
                'offer_decided',
                'channel_eligibility_decided',
                'channel_selected',
                'payment_verification_decided',
                'subscription_activation_decided',
                'payment_destination_created',
                'payment_destination_validated',
                'payment_destination_activated',
                'payment_destination_deactivated',
                'payment_destination_default_set'
            )
            """,
            name="action_allowed",
        ),
        CheckConstraint(
            """
            resource_type IN (
                'offer',
                'plan',
                'order',
                'payment_verification',
                'subscription',
                'trial',
                'sales_channel_eligibility',
                'payment_destination'
            )
            """,
            name="resource_type_allowed",
        ),
        CheckConstraint(
            """
            outcome IN (
                'allowed',
                'denied',
                'requires_review'
            )
            """,
            name="outcome_allowed",
        ),
        CheckConstraint(
            """
            previous_state_digest IS NULL
            OR length(previous_state_digest) = 64
            """,
            name="previous_digest_length",
        ),
        CheckConstraint(
            """
            new_state_digest IS NULL
            OR length(new_state_digest) = 64
            """,
            name="new_digest_length",
        ),
        UniqueConstraint(
            "event_ref",
            name="uq_admin_market_audit_records_event_ref",
        ),
        Index(
            "ix_admin_market_audit_resource_time",
            "resource_type",
            "resource_id",
            "occurred_at",
        ),
        Index(
            "ix_admin_market_audit_correlation",
            "correlation_id",
            "occurred_at",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_column()
    event_ref: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    actor_user_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    actor_session_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    platform_authority: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    resource_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    resource_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    outcome: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
    )
    reason_code: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    correlation_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    previous_state_digest: Mapped[str | None] = mapped_column(
        String(64),
    )
    new_state_digest: Mapped[str | None] = mapped_column(
        String(64),
    )
    metadata_json: Mapped[dict[str, str]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = _created_at_column()


class AdminMarketPaymentDestination(Base):
    __tablename__ = "admin_market_payment_destinations"
    __table_args__ = (
        CheckConstraint(
            """
            destination_type IN (
                'bank_account',
                'postal_account'
            )
            """,
            name="destination_type_allowed",
        ),
        CheckConstraint(
            "country_code = 'TN'",
            name="country_tunisia_only",
        ),
        CheckConstraint(
            "currency = 'TND'",
            name="currency_tnd_only",
        ),
        CheckConstraint(
            "sales_channel = 'maestro_direct'",
            name="channel_direct",
        ),
        CheckConstraint(
            """
            status IN (
                'draft',
                'validated',
                'active',
                'inactive'
            )
            """,
            name="status_allowed",
        ),
        CheckConstraint(
            """
            validation_method IS NULL
            OR validation_method IN (
                'structural',
                'provider'
            )
            """,
            name="validation_method_allowed",
        ),
        CheckConstraint(
            "length(identifier_ciphertext) > 12",
            name="ciphertext_not_truncated",
        ),
        CheckConstraint(
            "length(trim(masked_identifier)) >= 8",
            name="masked_identifier_present",
        ),
        CheckConstraint(
            """
            expires_at IS NULL
            OR effective_at IS NULL
            OR expires_at > effective_at
            """,
            name="effective_window_valid",
        ),
        CheckConstraint(
            """
            NOT is_active
            OR status = 'active'
            """,
            name="active_status",
        ),
        CheckConstraint(
            """
            NOT is_default
            OR (
                is_active
                AND status = 'active'
            )
            """,
            name="default_requires_active",
        ),
        CheckConstraint(
            """
            status = 'draft'
            OR (
                validation_method IS NOT NULL
                AND validation_reason_code IS NOT NULL
                AND validated_at IS NOT NULL
            )
            """,
            name="validated_state",
        ),
        UniqueConstraint(
            "destination_ref",
            name="uq_admin_market_payment_destinations_destination_ref",
        ),
        UniqueConstraint(
            "creation_idempotency_key_hash",
            name="uq_admin_market_payment_destinations_create_idem_hash",
        ),
        Index(
            "ix_admin_market_payment_destinations_status",
            "status",
            "is_active",
        ),
        Index(
            "uq_admin_market_payment_destinations_active_default",
            "sales_channel",
            unique=True,
            postgresql_where=text("is_active AND is_default"),
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_column()
    destination_ref: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    display_name: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )
    destination_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    institution_name: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
    )
    account_holder_name: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
    )
    identifier_ciphertext: Mapped[bytes] = mapped_column(
        LargeBinary,
        nullable=False,
    )
    identifier_key_version: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    masked_identifier: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    creation_idempotency_key_hash: Mapped[str | None] = mapped_column(
        String(64),
    )
    country_code: Mapped[str] = mapped_column(
        String(2),
        nullable=False,
        default="TN",
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="TND",
    )
    sales_channel: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="maestro_direct",
    )
    status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="draft",
    )
    validation_method: Mapped[str | None] = mapped_column(
        String(24),
    )
    validation_reason_code: Mapped[str | None] = mapped_column(
        String(128),
    )
    validated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    effective_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    instructions: Mapped[str | None] = mapped_column(
        String(1000),
    )
    created_at: Mapped[datetime] = _created_at_column()
    updated_at: Mapped[datetime] = _updated_at_column()


ADMIN_MARKET_MODELS = (
    AdminMarketPlan,
    AdminMarketOffer,
    AdminMarketSubscription,
    AdminMarketTrial,
    AdminMarketOrder,
    AdminMarketPaymentVerification,
    AdminMarketPaymentDestination,
    AdminMarketInvoice,
    AdminMarketEntitlementActivation,
    AdminMarketChannelEligibility,
    AdminMarketChannelSelection,
    AdminMarketCommercialDecision,
    AdminMarketAuditRecord,
)


__all__ = [
    "ADMIN_MARKET_MODELS",
    *[model.__name__ for model in ADMIN_MARKET_MODELS],
]
