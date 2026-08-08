"""Add immutable Lemon Squeezy reconciliation decisions.

Revision ID: 20260805_0027
Revises: 20260805_0026
Create Date: 2026-08-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "20260805_0027"
down_revision: str | None = "20260805_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "admin_market_lemon_squeezy_reconciliation_decisions"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("inbox_id", sa.Uuid(), nullable=False),
        sa.Column("event_identity_hash", sa.String(length=64), nullable=False),
        sa.Column("customer_ref", sa.String(length=128), nullable=False),
        sa.Column("order_ref", sa.String(length=128), nullable=False),
        sa.Column("offer_ref", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=24), nullable=False),
        sa.Column("reason_code", sa.String(length=128), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "action IN ('ignore', 'reconcile', 'requires_review')",
            name=op.f("ck_admin_market_ls_reconciliation_action_allowed"),
        ),
        sa.CheckConstraint(
            "length(event_identity_hash) = 64",
            name=op.f("ck_admin_market_ls_reconciliation_identity_hash_length"),
        ),
        sa.CheckConstraint(
            "length(reason_code) BETWEEN 1 AND 128",
            name=op.f("ck_admin_market_ls_reconciliation_reason_length"),
        ),
        sa.ForeignKeyConstraint(
            ["inbox_id"],
            ["admin_market_lemon_squeezy_webhook_inbox.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("inbox_id", name="uq_admin_market_ls_reconciliation_inbox"),
        sa.UniqueConstraint(
            "event_identity_hash",
            name="uq_admin_market_ls_reconciliation_event_identity",
        ),
    )
    op.create_index(
        "ix_admin_market_ls_reconciliation_action_time",
        TABLE,
        ["action", "decided_at"],
    )
    op.create_index(
        "ix_admin_market_ls_reconciliation_order_time",
        TABLE,
        ["order_ref", "decided_at"],
    )


def downgrade() -> None:
    if not context.is_offline_mode():
        connection = op.get_bind()
        if connection.execute(sa.text(f"SELECT 1 FROM {TABLE} LIMIT 1")).first():
            raise RuntimeError(
                "Downgrade blocked: Lemon Squeezy reconciliation decisions exist"
            )
    op.drop_index("ix_admin_market_ls_reconciliation_order_time", table_name=TABLE)
    op.drop_index("ix_admin_market_ls_reconciliation_action_time", table_name=TABLE)
    op.drop_table(TABLE)
