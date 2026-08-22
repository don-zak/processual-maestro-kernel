"""Persist fail-closed Lemon Squeezy checkout creation binding.

Revision ID: 20260822_0059
Revises: 20260822_0058
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260822_0059"
down_revision: str | None = "20260822_0058"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "admin_market_lemon_checkout_bindings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("provider_variant_id", sa.String(128), nullable=False),
        sa.Column("provider_checkout_id", sa.String(128), nullable=True),
        sa.Column(
            "checkout_creation_status",
            sa.String(24),
            nullable=False,
            server_default="not_started",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_admin_market_lemon_checkout_bindings"),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["admin_market_orders.id"],
            name="fk_admin_market_lemon_checkout_bindings_order_id_admin_market_orders",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "order_id",
            name="uq_admin_market_lemon_checkout_bindings_order_id",
        ),
        sa.UniqueConstraint(
            "provider_checkout_id",
            name="uq_admin_market_lemon_checkout_bindings_provider_checkout_id",
        ),
        sa.CheckConstraint(
            "checkout_creation_status IN ('not_started','creating','ready','uncertain')",
            name="ck_admin_market_lemon_checkout_bindings_checkout_creation_status_allowed",
        ),
        sa.CheckConstraint(
            "(checkout_creation_status = 'ready' AND provider_checkout_id IS NOT NULL) "
            "OR checkout_creation_status != 'ready'",
            name="ck_admin_market_lemon_checkout_bindings_ready_checkout_has_provider_id",
        ),
    )

    with op.batch_alter_table("admin_market_lemon_checkout_bindings") as batch:
        batch.alter_column(
            "checkout_creation_status",
            existing_type=sa.String(24),
            nullable=False,
            server_default=None,
        )


def downgrade() -> None:
    op.drop_table("admin_market_lemon_checkout_bindings")
