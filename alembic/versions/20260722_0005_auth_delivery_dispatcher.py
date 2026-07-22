"""Add lease ownership and dead-letter state to the auth delivery outbox.

Revision ID: 20260722_0005
Revises: 20260722_0004
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260722_0005"
down_revision: str | None = "20260722_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_auth_delivery_outbox_pending", table_name="auth_delivery_outbox")
    op.add_column(
        "auth_delivery_outbox",
        sa.Column("claim_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "auth_delivery_outbox",
        sa.Column("dead_lettered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_auth_delivery_outbox_dispatch",
        "auth_delivery_outbox",
        ["delivered_at", "dead_lettered_at", "available_at", "claimed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_auth_delivery_outbox_dispatch",
        table_name="auth_delivery_outbox",
    )
    op.drop_column("auth_delivery_outbox", "dead_lettered_at")
    op.drop_column("auth_delivery_outbox", "claim_id")
    op.create_index(
        "ix_auth_delivery_outbox_pending",
        "auth_delivery_outbox",
        ["delivered_at", "available_at"],
        unique=False,
    )
