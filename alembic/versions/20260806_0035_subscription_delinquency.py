"""Add subscription delinquency lifecycle persistence.

Revision ID: 20260806_0035
Revises: 20260806_0034
Create Date: 2026-08-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260806_0035"
down_revision: str | None = "20260806_0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "admin_market_subscription_delinquency"


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subscription_id", sa.Uuid(), nullable=False),
        sa.Column("customer_ref", sa.String(length=128), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("missed_billing_cycles", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_failed_cycle_key", sa.String(length=7)),
        sa.Column("first_failed_at", sa.DateTime(timezone=True)),
        sa.Column("last_failed_at", sa.DateTime(timezone=True)),
        sa.Column("grace_until", sa.DateTime(timezone=True)),
        sa.Column("grace_usage_percent", sa.Integer(), nullable=False, server_default="25"),
        sa.Column("frozen_at", sa.DateTime(timezone=True)),
        sa.Column("deletion_eligible_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "state IN ('grace_degraded','delinquent_read_only','account_frozen','pending_deletion','resolved')",
            name=op.f("ck_admin_market_subscription_delinquency_state"),
        ),
        sa.CheckConstraint(
            "missed_billing_cycles >= 0",
            name=op.f("ck_admin_market_subscription_delinquency_missed_cycles"),
        ),
        sa.CheckConstraint(
            "grace_usage_percent BETWEEN 0 AND 100",
            name=op.f("ck_admin_market_subscription_delinquency_grace_usage_percent"),
        ),
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["admin_market_subscriptions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "subscription_id",
            name="uq_admin_market_subscription_delinquency_subscription",
        ),
    )
    op.create_index(
        "ix_admin_market_subscription_delinquency_state",
        _TABLE,
        ["state", "deletion_eligible_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_admin_market_subscription_delinquency_state",
        table_name=_TABLE,
    )
    op.drop_table(_TABLE)
