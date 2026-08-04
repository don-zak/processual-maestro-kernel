"""Add payment-destination creation idempotency.

Revision ID: 20260804_0019
Revises: 20260804_0018
Create Date: 2026-08-04
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260804_0019"
down_revision: str | None = "20260804_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "admin_market_payment_destinations",
        sa.Column(
            "creation_idempotency_key_hash",
            sa.String(length=64),
            nullable=True,
        ),
    )
    op.create_unique_constraint(
        op.f("uq_admin_market_payment_destinations_create_idem_hash"),
        "admin_market_payment_destinations",
        ["creation_idempotency_key_hash"],
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("uq_admin_market_payment_destinations_create_idem_hash"),
        "admin_market_payment_destinations",
        type_="unique",
    )
    op.drop_column(
        "admin_market_payment_destinations",
        "creation_idempotency_key_hash",
    )
