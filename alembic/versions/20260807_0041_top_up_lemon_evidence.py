"""Add Lemon Squeezy top-up evidence and variant binding.

Revision ID: 20260807_0041
Revises: 20260807_0040
Create Date: 2026-08-07
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260807_0041"
down_revision: str | None = "20260807_0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("admin_market_lemon_squeezy_webhook_inbox") as batch:
        batch.add_column(sa.Column("subtotal_amount", sa.String(64), nullable=True))

    with op.batch_alter_table("commercial_top_up_orders") as batch:
        batch.add_column(sa.Column("provider_variant_id", sa.String(128), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("commercial_top_up_orders") as batch:
        batch.drop_column("provider_variant_id")

    with op.batch_alter_table("admin_market_lemon_squeezy_webhook_inbox") as batch:
        batch.drop_column("subtotal_amount")
