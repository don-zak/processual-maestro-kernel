"""Add subscription runtime, quota accounts, and immutable usage ledger.

Revision ID: 20260805_0028
Revises: 20260805_0027
Create Date: 2026-08-05
"""
from __future__ import annotations
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import context, op

revision: str = "20260805_0028"
down_revision: str | None = "20260805_0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RUNTIME = "admin_market_subscription_runtime"
QUOTAS = "admin_market_subscription_quota_accounts"
USAGE = "admin_market_subscription_usage_ledger"


def upgrade() -> None:
    op.create_table(
        RUNTIME,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subscription_id", sa.Uuid(), nullable=False),
        sa.Column("customer_ref", sa.String(128), nullable=False),
        sa.Column("entitlement_profile_ref", sa.String(128), nullable=False),
        sa.Column("quota_profile_ref", sa.String(128), nullable=False),
        sa.Column("access_stage", sa.String(24), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("grace_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("terminated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("access_stage IN ('active','grace','suspended','terminated')", name=op.f("ck_admin_market_subscription_runtime_stage")),
        sa.CheckConstraint("version >= 0", name=op.f("ck_admin_market_subscription_runtime_version")),
        sa.CheckConstraint("(access_stage != 'grace') OR grace_until IS NOT NULL", name=op.f("ck_admin_market_subscription_runtime_grace_time")),
        sa.CheckConstraint("(access_stage != 'suspended') OR suspended_at IS NOT NULL", name=op.f("ck_admin_market_subscription_runtime_suspended_time")),
        sa.CheckConstraint("(access_stage != 'terminated') OR terminated_at IS NOT NULL", name=op.f("ck_admin_market_subscription_runtime_terminated_time")),
        sa.ForeignKeyConstraint(["subscription_id"], ["admin_market_subscriptions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("subscription_id", name="uq_admin_market_subscription_runtime_subscription"),
    )
    op.create_index("ix_admin_market_subscription_runtime_customer_stage", RUNTIME, ["customer_ref", "access_stage"])

    op.create_table(
        QUOTAS,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subscription_id", sa.Uuid(), nullable=False),
        sa.Column("customer_ref", sa.String(128), nullable=False),
        sa.Column("quota_profile_ref", sa.String(128), nullable=False),
        sa.Column("metric_code", sa.String(128), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("limit_units", sa.BigInteger(), nullable=False),
        sa.Column("used_units", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("period_end > period_start", name=op.f("ck_admin_market_subscription_quota_period")),
        sa.CheckConstraint("limit_units >= 0 AND used_units >= 0 AND used_units <= limit_units", name=op.f("ck_admin_market_subscription_quota_units")),
        sa.CheckConstraint("version >= 0", name=op.f("ck_admin_market_subscription_quota_version")),
        sa.ForeignKeyConstraint(["subscription_id"], ["admin_market_subscriptions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("subscription_id", "metric_code", "period_start", name="uq_admin_market_subscription_quota_period"),
    )
    op.create_index("ix_admin_market_subscription_quota_customer_metric", QUOTAS, ["customer_ref", "metric_code", "period_end"])

    op.create_table(
        USAGE,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("quota_account_id", sa.Uuid(), nullable=False),
        sa.Column("subscription_id", sa.Uuid(), nullable=False),
        sa.Column("customer_ref", sa.String(128), nullable=False),
        sa.Column("metric_code", sa.String(128), nullable=False),
        sa.Column("units", sa.BigInteger(), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(64), nullable=False),
        sa.Column("dimensions_digest", sa.String(64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("units > 0", name=op.f("ck_admin_market_subscription_usage_units")),
        sa.CheckConstraint("length(idempotency_key_hash) = 64 AND length(dimensions_digest) = 64", name=op.f("ck_admin_market_subscription_usage_digests")),
        sa.ForeignKeyConstraint(["quota_account_id"], [f"{QUOTAS}.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["subscription_id"], ["admin_market_subscriptions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key_hash", name="uq_admin_market_subscription_usage_idempotency"),
    )
    op.create_index("ix_admin_market_subscription_usage_subscription_time", USAGE, ["subscription_id", "occurred_at"])
    op.create_index("ix_admin_market_subscription_usage_customer_metric", USAGE, ["customer_ref", "metric_code", "occurred_at"])


def downgrade() -> None:
    if not context.is_offline_mode():
        connection = op.get_bind()
        for table in (USAGE, QUOTAS, RUNTIME):
            if connection.execute(sa.text(f"SELECT 1 FROM {table} LIMIT 1")).first():
                raise RuntimeError("Downgrade blocked: subscription runtime, quota, or usage rows exist")
    op.drop_index("ix_admin_market_subscription_usage_customer_metric", table_name=USAGE)
    op.drop_index("ix_admin_market_subscription_usage_subscription_time", table_name=USAGE)
    op.drop_table(USAGE)
    op.drop_index("ix_admin_market_subscription_quota_customer_metric", table_name=QUOTAS)
    op.drop_table(QUOTAS)
    op.drop_index("ix_admin_market_subscription_runtime_customer_stage", table_name=RUNTIME)
    op.drop_table(RUNTIME)
