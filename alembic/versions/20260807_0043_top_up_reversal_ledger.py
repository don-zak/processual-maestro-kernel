"""Add immutable subscription top-up reversal ledger and refund evidence.

Revision ID: 20260807_0043
Revises: 20260807_0042
Create Date: 2026-08-07
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260807_0043"
down_revision: str | None = "20260807_0042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("admin_market_lemon_squeezy_webhook_inbox") as batch:
        batch.add_column(sa.Column("refunded_amount", sa.String(length=64), nullable=True))

    op.create_table(
        "admin_market_subscription_top_up_reversals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("grant_id", sa.Uuid(), nullable=False),
        sa.Column("subscription_id", sa.Uuid(), nullable=False),
        sa.Column("quota_cycle_id", sa.Uuid(), nullable=False),
        sa.Column("customer_ref", sa.String(length=128), nullable=False),
        sa.Column("provider_event_ref", sa.String(length=255), nullable=False),
        sa.Column("units", sa.BigInteger(), nullable=False),
        sa.Column("outcome", sa.String(length=24), nullable=False),
        sa.Column("reason_code", sa.String(length=128), nullable=False),
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("units > 0", name="units_positive"),
        sa.CheckConstraint("outcome IN ('reversed','manual_review')", name="outcome_allowed"),
        sa.ForeignKeyConstraint(["grant_id"], ["admin_market_subscription_top_up_grants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["order_id"], ["commercial_top_up_orders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["quota_cycle_id"], ["admin_market_subscription_quota_cycles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["subscription_id"], ["admin_market_subscriptions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("grant_id", name="uq_admin_market_top_up_reversal_grant"),
        sa.UniqueConstraint("provider_event_ref", name="uq_admin_market_top_up_reversal_provider_event"),
    )
    op.create_index(
        "ix_admin_market_top_up_reversal_subscription_cycle",
        "admin_market_subscription_top_up_reversals",
        ["subscription_id", "quota_cycle_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_admin_market_top_up_reversal_subscription_cycle",
        table_name="admin_market_subscription_top_up_reversals",
    )
    op.drop_table("admin_market_subscription_top_up_reversals")
    with op.batch_alter_table("admin_market_lemon_squeezy_webhook_inbox") as batch:
        batch.drop_column("refunded_amount")
