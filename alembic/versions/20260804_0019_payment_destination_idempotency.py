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

TABLE = "admin_market_payment_destinations"
CONSTRAINT = "uq_admin_market_payment_destinations_create_idem_hash"


def upgrade() -> None:
    with op.batch_alter_table(TABLE) as batch_op:
        batch_op.add_column(
            sa.Column(
                "creation_idempotency_key_hash",
                sa.String(length=64),
                nullable=True,
            )
        )
        batch_op.create_unique_constraint(
            CONSTRAINT,
            ["creation_idempotency_key_hash"],
        )


def downgrade() -> None:
    with op.batch_alter_table(TABLE) as batch_op:
        batch_op.drop_constraint(CONSTRAINT, type_="unique")
        batch_op.drop_column("creation_idempotency_key_hash")
