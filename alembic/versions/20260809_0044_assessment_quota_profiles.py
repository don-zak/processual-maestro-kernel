"""Add durable assessment-derived quota profiles.

Revision ID: 20260809_0044
Revises: 20260807_0043
Create Date: 2026-08-09
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "20260809_0044"
down_revision: str | None = "20260807_0043"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "admin_market_assessment_quota_profiles"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("profile_ref", sa.String(length=128), nullable=False),
        sa.Column("assessment_binding_hash", sa.String(length=64), nullable=False),
        sa.Column("assessment_id", sa.String(length=128), nullable=False),
        sa.Column("customer_ref", sa.String(length=128), nullable=False),
        sa.Column("public_plan_id", sa.String(length=128), nullable=False),
        sa.Column("entitlement_source_plan_code", sa.String(length=128), nullable=False),
        sa.Column("approved_by", sa.String(length=128), nullable=False),
        sa.Column("approval_reference", sa.String(length=128), nullable=False),
        sa.Column("entitlement_codes_json", sa.JSON(), nullable=False),
        sa.Column("metric_code", sa.String(length=128), nullable=False),
        sa.Column("limit_units", sa.BigInteger(), nullable=False),
        sa.Column("cycle_kind", sa.String(length=32), nullable=False),
        sa.Column("compatibility_period_days", sa.Integer(), nullable=False),
        sa.Column("definition_version", sa.String(length=128), nullable=False),
        sa.Column("payload_digest", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("limit_units > 0", name="limit_units_positive"),
        sa.CheckConstraint(
            "cycle_kind = 'calendar_month'",
            name="cycle_kind_calendar_month",
        ),
        sa.CheckConstraint(
            "compatibility_period_days = 30",
            name="compatibility_period_days_monthly",
        ),
        sa.CheckConstraint(
            "length(assessment_binding_hash) = 64 AND length(payload_digest) = 64",
            name="digests_length",
        ),
        sa.PrimaryKeyConstraint("profile_ref"),
        sa.UniqueConstraint(
            "assessment_binding_hash",
            name="uq_admin_market_assessment_quota_binding_hash",
        ),
    )


def downgrade() -> None:
    if not context.is_offline_mode():
        connection = op.get_bind()
        if connection.execute(sa.text(f"SELECT 1 FROM {TABLE} LIMIT 1")).first():
            raise RuntimeError(
                "Downgrade blocked: assessment quota profile rows exist"
            )
    op.drop_table(TABLE)
