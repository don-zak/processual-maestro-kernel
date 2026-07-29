"""add commercial top-up persistence tables

Revision ID: 20260729_0013
Revises: 20260727_0011
Create Date: 2026-07-29
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260729_0013"
down_revision: str | None = "20260727_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "commercial_top_up_orders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("subscription_id", sa.Uuid(), nullable=False),
        sa.Column("plan_code", sa.String(length=128), nullable=False),
        sa.Column("requested_units", sa.Integer(), nullable=False),
        sa.Column("bundle_count", sa.Integer(), nullable=False),
        sa.Column(
            "total_price_usd",
            sa.Numeric(precision=18, scale=2),
            nullable=False,
        ),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("state", sa.String(length=40), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "requested_units > 0",
            name=op.f("ck_commercial_top_up_orders_requested_units_positive"),
        ),
        sa.CheckConstraint(
            "bundle_count > 0",
            name=op.f("ck_commercial_top_up_orders_bundle_count_positive"),
        ),
        sa.CheckConstraint(
            "total_price_usd > 0",
            name=op.f("ck_commercial_top_up_orders_total_price_positive"),
        ),
        sa.CheckConstraint(
            "channel IN ('local_tunisia', 'lemon_squeezy')",
            name=op.f("ck_commercial_top_up_orders_channel_allowed"),
        ),
        sa.CheckConstraint(
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
            name=op.f("ck_commercial_top_up_orders_state_allowed"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_commercial_top_up_orders")),
        sa.UniqueConstraint(
            "idempotency_key",
            name="uq_commercial_top_up_orders_idempotency_key",
        ),
    )
    op.create_index(
        "ix_commercial_top_up_orders_account_state",
        "commercial_top_up_orders",
        ["account_id", "state"],
        unique=False,
    )

    op.create_table(
        "commercial_top_up_payment_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("provider_reference", sa.String(length=255), nullable=False),
        sa.Column("outcome", sa.String(length=24), nullable=False),
        sa.Column(
            "verified_amount_usd",
            sa.Numeric(precision=18, scale=2),
            nullable=True,
        ),
        sa.Column("verified_currency", sa.String(length=3), nullable=True),
        sa.Column(
            "immutable_evidence_reference",
            sa.String(length=500),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "outcome IN ('verified', 'rejected', 'pending')",
            name=op.f("ck_commercial_top_up_payment_evidence_outcome_allowed"),
        ),
        sa.CheckConstraint(
            "verified_amount_usd IS NULL OR verified_amount_usd > 0",
            name=op.f("ck_commercial_top_up_payment_evidence_verified_amount_positive"),
        ),
        sa.CheckConstraint(
            "verified_currency IS NULL OR length(verified_currency) = 3",
            name=op.f("ck_commercial_top_up_payment_evidence_verified_currency_length"),
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["commercial_top_up_orders.id"],
            name=op.f("fk_commercial_top_up_payment_evidence_order_id_commercial_top_up_orders"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_commercial_top_up_payment_evidence"),
        ),
        sa.UniqueConstraint(
            "provider_reference",
            name="uq_commercial_top_up_payment_provider_reference",
        ),
    )
    op.create_index(
        "ix_commercial_top_up_payment_order",
        "commercial_top_up_payment_evidence",
        ["order_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "commercial_top_up_grants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("outcome", sa.String(length=24), nullable=False),
        sa.Column("units", sa.Integer(), nullable=False),
        sa.Column(
            "grant_idempotency_key",
            sa.String(length=500),
            nullable=False,
        ),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "units > 0",
            name=op.f("ck_commercial_top_up_grants_units_positive"),
        ),
        sa.CheckConstraint(
            "outcome IN ('granted', 'duplicate', 'blocked')",
            name=op.f("ck_commercial_top_up_grants_outcome_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["commercial_top_up_orders.id"],
            name=op.f("fk_commercial_top_up_grants_order_id_commercial_top_up_orders"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_commercial_top_up_grants"),
        ),
        sa.UniqueConstraint(
            "grant_idempotency_key",
            name="uq_commercial_top_up_grants_idempotency_key",
        ),
        sa.UniqueConstraint(
            "order_id",
            name="uq_commercial_top_up_grants_order_id",
        ),
    )

    op.create_table(
        "commercial_top_up_audit_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_ref", sa.String(length=255), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=48), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "actor_reference",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "evidence_reference",
            sa.String(length=500),
            nullable=False,
        ),
        sa.Column(
            "payload_digest",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
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
            name=op.f("ck_commercial_top_up_audit_records_action_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["commercial_top_up_orders.id"],
            name=op.f("fk_commercial_top_up_audit_records_order_id_commercial_top_up_orders"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_commercial_top_up_audit_records"),
        ),
        sa.UniqueConstraint(
            "event_ref",
            name="uq_commercial_top_up_audit_event_ref",
        ),
    )
    op.create_index(
        "ix_commercial_top_up_audit_order_time",
        "commercial_top_up_audit_records",
        ["order_id", "occurred_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_commercial_top_up_audit_order_time",
        table_name="commercial_top_up_audit_records",
    )
    op.drop_table("commercial_top_up_audit_records")
    op.drop_table("commercial_top_up_grants")
    op.drop_index(
        "ix_commercial_top_up_payment_order",
        table_name="commercial_top_up_payment_evidence",
    )
    op.drop_table("commercial_top_up_payment_evidence")
    op.drop_index(
        "ix_commercial_top_up_orders_account_state",
        table_name="commercial_top_up_orders",
    )
    op.drop_table("commercial_top_up_orders")
