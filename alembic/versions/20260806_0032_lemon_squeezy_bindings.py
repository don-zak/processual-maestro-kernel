"""Add authoritative Lemon Squeezy bindings.

Revision ID: 20260806_0032
Revises: 20260806_0031
Create Date: 2026-08-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260806_0032"
down_revision: str | None = "20260806_0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CUSTOMERS = "admin_market_lemon_squeezy_customer_bindings"
_BINDINGS = "admin_market_lemon_squeezy_bindings"


def upgrade() -> None:
    op.create_table(
        _CUSTOMERS,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("customer_ref", sa.String(length=128), nullable=False),
        sa.Column("provider_customer_id", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "customer_ref",
            name="uq_admin_market_ls_customer_binding_customer",
        ),
        sa.UniqueConstraint(
            "provider_customer_id",
            name="uq_admin_market_ls_customer_binding_provider_customer",
        ),
    )
    op.create_table(
        _BINDINGS,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("customer_ref", sa.String(length=128), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("offer_id", sa.Uuid(), nullable=False),
        sa.Column("subscription_id", sa.Uuid()),
        sa.Column("provider_customer_id", sa.String(length=128), nullable=False),
        sa.Column("provider_order_id", sa.String(length=128), nullable=False),
        sa.Column("provider_subscription_id", sa.String(length=128)),
        sa.Column("variant_id", sa.String(length=128), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("total_amount", sa.String(length=64), nullable=False),
        sa.Column("last_provider_effective_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "length(currency) = 3",
            name=op.f("ck_admin_market_ls_bindings_currency_length"),
        ),
        sa.ForeignKeyConstraint(
            ["customer_ref"],
            [f"{_CUSTOMERS}.customer_ref"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["offer_id"],
            ["admin_market_offers.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["admin_market_orders.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["admin_market_subscriptions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id", name="uq_admin_market_ls_binding_order"),
        sa.UniqueConstraint(
            "provider_order_id",
            name="uq_admin_market_ls_binding_provider_order",
        ),
        sa.UniqueConstraint(
            "provider_subscription_id",
            name="uq_admin_market_ls_binding_provider_subscription",
        ),
    )
    op.create_index(
        "ix_admin_market_ls_binding_customer",
        _BINDINGS,
        ["customer_ref", "last_provider_effective_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_admin_market_ls_binding_customer", table_name=_BINDINGS)
    op.drop_table(_BINDINGS)
    op.drop_table(_CUSTOMERS)
