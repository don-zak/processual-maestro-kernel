"""Add the current degraded grace anchor.

Revision ID: 20260806_0036
Revises: 20260806_0035
Create Date: 2026-08-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260806_0036"
down_revision: str | None = "20260806_0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "admin_market_subscription_delinquency"


def upgrade() -> None:
    with op.batch_alter_table(_TABLE) as batch_op:
        batch_op.add_column(
            sa.Column("grace_started_at", sa.DateTime(timezone=True), nullable=True)
        )

    op.execute(
        sa.text(
            f"UPDATE {_TABLE} SET grace_started_at = last_failed_at "
            "WHERE state = 'grace_degraded' AND grace_started_at IS NULL"
        )
    )


def downgrade() -> None:
    with op.batch_alter_table(_TABLE) as batch_op:
        batch_op.drop_column("grace_started_at")
