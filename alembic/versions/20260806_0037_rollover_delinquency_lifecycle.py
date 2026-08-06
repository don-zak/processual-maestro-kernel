"""Add rollover delinquency lifecycle fields.

Revision ID: 20260806_0037
Revises: 20260806_0036
Create Date: 2026-08-06
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import context, op

revision: str = "20260806_0037"
down_revision: str | None = "20260806_0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "admin_market_subscription_quota_cycles"


def upgrade() -> None:
    with op.batch_alter_table(TABLE) as batch:
        batch.add_column(
            sa.Column(
                "rollover_status",
                sa.String(32),
                nullable=False,
                server_default="available",
            )
        )
        batch.add_column(sa.Column("rollover_expires_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("rollover_locked_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("rollover_restored_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("rollover_expired_at", sa.DateTime(timezone=True)))
        batch.create_check_constraint(
            "ck_admin_market_subscription_quota_cycles_rollover_status",
            "rollover_status IN "
            "('available','locked_for_delinquency','restored','expired')",
        )
        batch.create_index(
            "ix_admin_market_quota_cycle_rollover_expiry",
            ["rollover_status", "rollover_expires_at"],
        )


def downgrade() -> None:
    if not context.is_offline_mode():
        connection = op.get_bind()
        active = connection.execute(
            sa.text(
                f"SELECT 1 FROM {TABLE} "
                "WHERE rollover_status != 'available' LIMIT 1"
            )
        ).first()
        if active:
            raise RuntimeError(
                "Downgrade blocked: rollover delinquency lifecycle rows exist"
            )
    with op.batch_alter_table(TABLE) as batch:
        batch.drop_index("ix_admin_market_quota_cycle_rollover_expiry")
        batch.drop_constraint(
            "ck_admin_market_subscription_quota_cycles_rollover_status",
            type_="check",
        )
        batch.drop_column("rollover_expired_at")
        batch.drop_column("rollover_restored_at")
        batch.drop_column("rollover_locked_at")
        batch.drop_column("rollover_expires_at")
        batch.drop_column("rollover_status")
