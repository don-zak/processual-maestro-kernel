"""Add immutable subscription runtime transition ledger.

Revision ID: 20260805_0029
Revises: 20260805_0028
Create Date: 2026-08-05
"""
from __future__ import annotations
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import context, op

revision: str = "20260805_0029"
down_revision: str | None = "20260805_0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "admin_market_subscription_runtime_transitions"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("runtime_id", sa.Uuid(), nullable=False),
        sa.Column("subscription_id", sa.Uuid(), nullable=False),
        sa.Column("reconciliation_decision_id", sa.Uuid(), nullable=False),
        sa.Column("customer_ref", sa.String(128), nullable=False),
        sa.Column("event_name", sa.String(64), nullable=False),
        sa.Column("from_stage", sa.String(24), nullable=False),
        sa.Column("to_stage", sa.String(24), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("from_stage IN ('active','grace','suspended','terminated')", name=op.f("ck_admin_market_subscription_transition_from_stage")),
        sa.CheckConstraint("to_stage IN ('active','grace','suspended','terminated')", name=op.f("ck_admin_market_subscription_transition_to_stage")),
        sa.ForeignKeyConstraint(["runtime_id"], ["admin_market_subscription_runtime.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["subscription_id"], ["admin_market_subscriptions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reconciliation_decision_id"], ["admin_market_lemon_squeezy_reconciliation_decisions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reconciliation_decision_id", name="uq_admin_market_subscription_transition_decision"),
    )
    op.create_index("ix_admin_market_subscription_transition_subscription_time", TABLE, ["subscription_id", "effective_at"])
    op.create_index("ix_admin_market_subscription_transition_customer_time", TABLE, ["customer_ref", "effective_at"])


def downgrade() -> None:
    if not context.is_offline_mode():
        connection = op.get_bind()
        if connection.execute(sa.text(f"SELECT 1 FROM {TABLE} LIMIT 1")).first():
            raise RuntimeError("Downgrade blocked: subscription runtime transitions exist")
    op.drop_index("ix_admin_market_subscription_transition_customer_time", table_name=TABLE)
    op.drop_index("ix_admin_market_subscription_transition_subscription_time", table_name=TABLE)
    op.drop_table(TABLE)
