"""Add rollover quota cycle usage ledger.

Revision ID: 20260806_0034
Revises: 20260806_0033
Create Date: 2026-08-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260806_0034"
down_revision: str | None = "20260806_0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "admin_market_subscription_quota_cycle_usage"


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("quota_cycle_id", sa.Uuid(), nullable=False),
        sa.Column("subscription_id", sa.Uuid(), nullable=False),
        sa.Column("customer_ref", sa.String(length=128), nullable=False),
        sa.Column("metric_code", sa.String(length=128), nullable=False),
        sa.Column("units", sa.BigInteger(), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(length=64), nullable=False),
        sa.Column("dimensions_digest", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("units > 0", name=op.f("ck_admin_market_subscription_quota_cycle_usage_units_positive")),
        sa.CheckConstraint(
            "length(idempotency_key_hash) = 64",
            name=op.f("ck_admin_market_subscription_quota_cycle_usage_idempotency_hash_length"),
        ),
        sa.CheckConstraint(
            "length(dimensions_digest) = 64",
            name=op.f("ck_admin_market_subscription_quota_cycle_usage_dimensions_digest_length"),
        ),
        sa.ForeignKeyConstraint(
            ["quota_cycle_id"],
            ["admin_market_subscription_quota_cycles.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["admin_market_subscriptions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "idempotency_key_hash",
            name="uq_admin_market_quota_cycle_usage_idempotency",
        ),
    )
    op.create_index(
        "ix_admin_market_quota_cycle_usage_cycle_time",
        _TABLE,
        ["quota_cycle_id", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_admin_market_quota_cycle_usage_cycle_time",
        table_name=_TABLE,
    )
    op.drop_table(_TABLE)
