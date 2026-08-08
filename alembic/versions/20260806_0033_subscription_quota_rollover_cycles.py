"""Add auditable subscription quota rollover cycles.

Revision ID: 20260806_0033
Revises: 20260806_0032
Create Date: 2026-08-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260806_0033"
down_revision: str | None = "20260806_0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "admin_market_subscription_quota_cycles"


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subscription_id", sa.Uuid(), nullable=False),
        sa.Column("source_cycle_id", sa.Uuid()),
        sa.Column("customer_ref", sa.String(length=128), nullable=False),
        sa.Column("quota_profile_ref", sa.String(length=128), nullable=False),
        sa.Column("metric_code", sa.String(length=128), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("base_limit_units", sa.BigInteger(), nullable=False),
        sa.Column(
            "rollover_units",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "used_units",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "version",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
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
            "period_end > period_start",
            name=op.f(
                "ck_admin_market_subscription_quota_cycles_period_valid"
            ),
        ),
        sa.CheckConstraint(
            "base_limit_units >= 0",
            name=op.f(
                "ck_admin_market_subscription_quota_cycles_base_nonnegative"
            ),
        ),
        sa.CheckConstraint(
            "rollover_units >= 0",
            name=op.f(
                "ck_admin_market_subscription_quota_cycles_rollover_nonnegative"
            ),
        ),
        sa.CheckConstraint(
            "used_units >= 0 "
            "AND used_units <= base_limit_units + rollover_units",
            name=op.f(
                "ck_admin_market_subscription_quota_cycles_usage_within_available"
            ),
        ),
        sa.CheckConstraint(
            "version >= 0",
            name=op.f(
                "ck_admin_market_subscription_quota_cycles_version_nonnegative"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["admin_market_subscriptions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_cycle_id"],
            [f"{_TABLE}.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "subscription_id",
            "metric_code",
            "period_start",
            name="uq_admin_market_quota_cycle_period",
        ),
        sa.UniqueConstraint(
            "source_cycle_id",
            name="uq_admin_market_quota_cycle_source",
        ),
    )
    op.create_index(
        "ix_admin_market_quota_cycle_customer_metric",
        _TABLE,
        ["customer_ref", "metric_code", "period_end"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_admin_market_quota_cycle_customer_metric",
        table_name=_TABLE,
    )
    op.drop_table(_TABLE)
