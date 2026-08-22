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


_TABLE = "admin_market_lemon_checkout_bindings"
_PK = "pk_am_lcb"
_ORDER_FK = "fk_am_lcb_order"
_ORDER_UQ = "uq_am_lcb_order"
_PROVIDER_CHECKOUT_UQ = "uq_am_lcb_provider_checkout"
_STATUS_CK = "ck_am_lcb_status"
_READY_PROVIDER_CK = "ck_am_lcb_ready_provider"


def upgrade() -> None:
    op.create_table(
        _TABLE,
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
        sa.PrimaryKeyConstraint("id", name=op.f(_PK)),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["admin_market_orders.id"],
            name=op.f(_ORDER_FK),
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "order_id",
            name=op.f(_ORDER_UQ),
        ),
        sa.UniqueConstraint(
            "provider_checkout_id",
            name=op.f(_PROVIDER_CHECKOUT_UQ),
        ),
        sa.CheckConstraint(
            "checkout_creation_status IN ('not_started','creating','ready','uncertain')",
            name=op.f(_STATUS_CK),
        ),
        sa.CheckConstraint(
            "(checkout_creation_status = 'ready' AND provider_checkout_id IS NOT NULL) "
            "OR checkout_creation_status != 'ready'",
            name=op.f(_READY_PROVIDER_CK),
        ),
    )

    with op.batch_alter_table(_TABLE) as batch:
        batch.alter_column(
            "checkout_creation_status",
            existing_type=sa.String(24),
            nullable=False,
            server_default=None,
        )


def downgrade() -> None:
    op.drop_table(_TABLE)
