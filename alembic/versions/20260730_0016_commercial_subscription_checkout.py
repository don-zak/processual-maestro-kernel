"""add commercial subscription checkout authority persistence

Revision ID: 20260730_0016
Revises: 20260730_0015
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260730_0016"
down_revision: str | None = "20260730_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "commercial_subscription_checkout_orders",
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("subscription_id", sa.Uuid(), nullable=False),
        sa.Column(
            "customer_reference",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "plan_code",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column("included_units", sa.Integer(), nullable=False),
        sa.Column(
            "billing_cycle_reference",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "cycle_started_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "cycle_ends_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "authoritative_price_usd",
            sa.Numeric(precision=18, scale=2),
            nullable=False,
        ),
        sa.Column(
            "selected_channel",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "settlement_currency",
            sa.String(length=3),
            nullable=False,
        ),
        sa.Column(
            "settlement_amount",
            sa.Numeric(precision=18, scale=3),
            nullable=False,
        ),
        sa.Column(
            "quote_reference",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "quote_expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "billing_country",
            sa.String(length=2),
            nullable=True,
        ),
        sa.Column(
            "tunisian_address_eligible",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column(
            "customer_choice_preserved",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column("state", sa.String(length=40), nullable=False),
        sa.Column(
            "idempotency_key",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "order_id",
            name="pk_commercial_subscription_checkout_orders",
        ),
        sa.UniqueConstraint(
            "idempotency_key",
            name="uq_subscription_checkout_order_idempotency",
        ),
        sa.CheckConstraint(
            "included_units > 0",
            name=op.f("ck_commercial_subscription_checkout_orders_included_units_positive"),
        ),
        sa.CheckConstraint(
            "authoritative_price_usd > 0",
            name=op.f("ck_commercial_subscription_checkout_orders_authoritative_price_positive"),
        ),
        sa.CheckConstraint(
            "settlement_amount > 0",
            name=op.f("ck_commercial_subscription_checkout_orders_settlement_amount_positive"),
        ),
        sa.CheckConstraint(
            "version >= 0",
            name=op.f("ck_commercial_subscription_checkout_orders_version_nonnegative"),
        ),
        sa.CheckConstraint(
            "selected_channel IN ('local_tunisia', 'lemon_squeezy')",
            name=op.f("ck_commercial_subscription_checkout_orders_selected_channel_allowed"),
        ),
        sa.CheckConstraint(
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
            name=op.f("ck_commercial_subscription_checkout_orders_state_allowed"),
        ),
        sa.CheckConstraint(
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
            name=op.f("ck_commercial_subscription_checkout_orders_channel_settlement_consistent"),
        ),
    )
    op.create_index(
        "ix_subscription_checkout_orders_tenant_state",
        "commercial_subscription_checkout_orders",
        ["tenant_id", "state"],
        unique=False,
    )

    op.create_table(
        "commercial_subscription_payment_evidence",
        sa.Column("evidence_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column(
            "provider_reference",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "channel",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "outcome",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "verified_amount",
            sa.Numeric(precision=18, scale=3),
            nullable=True,
        ),
        sa.Column(
            "verified_currency",
            sa.String(length=3),
            nullable=True,
        ),
        sa.Column(
            "immutable_evidence_reference",
            sa.String(length=500),
            nullable=False,
        ),
        sa.Column(
            "observed_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "idempotency_key",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "evidence_id",
            name="pk_commercial_subscription_payment_evidence",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["commercial_subscription_checkout_orders.order_id"],
            name="fk_subscription_payment_order",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "provider_reference",
            name="uq_subscription_payment_provider_reference",
        ),
        sa.UniqueConstraint(
            "idempotency_key",
            name="uq_subscription_payment_idempotency",
        ),
        sa.CheckConstraint(
            """
            outcome IN (
                'pending',
                'verified',
                'rejected',
                'requires_review'
            )
            """,
            name=op.f("ck_commercial_subscription_payment_evidence_outcome_allowed"),
        ),
    )
    op.create_index(
        "ix_subscription_payment_order_observed",
        "commercial_subscription_payment_evidence",
        ["order_id", "observed_at"],
        unique=False,
    )

    op.create_table(
        "commercial_subscription_activation_decisions",
        sa.Column("decision_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column(
            "outcome",
            sa.String(length=24),
            nullable=False,
        ),
        sa.Column(
            "actor_reference",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "authority_reference",
            sa.String(length=40),
            nullable=False,
        ),
        sa.Column(
            "approval_reference",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "reason",
            sa.String(length=500),
            nullable=False,
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "idempotency_key",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "decision_id",
            name="pk_commercial_subscription_activation_decisions",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["commercial_subscription_checkout_orders.order_id"],
            name="fk_subscription_activation_order",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "idempotency_key",
            name="uq_subscription_activation_decision_idempotency",
        ),
        sa.CheckConstraint(
            """
            outcome IN (
                'approved',
                'denied',
                'requires_review'
            )
            """,
            name=op.f("ck_commercial_subscription_activation_decisions_outcome_allowed"),
        ),
        sa.CheckConstraint(
            "authority_reference = 'platform_admin'",
            name=op.f("ck_commercial_subscription_activation_decisions_platform_admin_exact"),
        ),
    )
    op.create_index(
        "ix_subscription_activation_order_occurred",
        "commercial_subscription_activation_decisions",
        ["order_id", "occurred_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_subscription_activation_order_occurred",
        table_name="commercial_subscription_activation_decisions",
    )
    op.drop_table("commercial_subscription_activation_decisions")
    op.drop_index(
        "ix_subscription_payment_order_observed",
        table_name="commercial_subscription_payment_evidence",
    )
    op.drop_table("commercial_subscription_payment_evidence")
    op.drop_index(
        "ix_subscription_checkout_orders_tenant_state",
        table_name="commercial_subscription_checkout_orders",
    )
    op.drop_table("commercial_subscription_checkout_orders")
