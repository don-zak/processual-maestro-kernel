"""Persist Lemon Squeezy top-up checkout creation binding.

Revision ID: 20260807_0042
Revises: 20260807_0041
Create Date: 2026-08-07
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260807_0042"
down_revision: str | None = "20260807_0041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("commercial_top_up_orders") as batch:
        batch.add_column(sa.Column("provider_checkout_id", sa.String(128), nullable=True))
        batch.add_column(
            sa.Column(
                "checkout_creation_status",
                sa.String(24),
                nullable=False,
                server_default="not_started",
            )
        )
        batch.create_unique_constraint(
            "uq_commercial_top_up_orders_provider_checkout_id",
            ["provider_checkout_id"],
        )
        batch.create_check_constraint(
            "checkout_creation_status_allowed",
            "checkout_creation_status IN ('not_started','creating','ready','uncertain')",
        )
        batch.create_check_constraint(
            "ready_checkout_has_provider_id",
            "(checkout_creation_status = 'ready' AND provider_checkout_id IS NOT NULL) "
            "OR checkout_creation_status != 'ready'",
        )

    with op.batch_alter_table("commercial_top_up_orders") as batch:
        batch.alter_column(
            "checkout_creation_status",
            existing_type=sa.String(24),
            nullable=False,
            server_default=None,
        )


def downgrade() -> None:
    with op.batch_alter_table("commercial_top_up_orders") as batch:
        batch.drop_constraint("ready_checkout_has_provider_id", type_="check")
        batch.drop_constraint("checkout_creation_status_allowed", type_="check")
        batch.drop_constraint(
            "uq_commercial_top_up_orders_provider_checkout_id",
            type_="unique",
        )
        batch.drop_column("checkout_creation_status")
        batch.drop_column("provider_checkout_id")
