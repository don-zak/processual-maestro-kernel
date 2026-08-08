"""add billing period to registration plan intent

Revision ID: 20260804_0016
Revises: 20260803_0015
Create Date: 2026-08-04
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260804_0016"
down_revision: str | None = "20260803_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "auth_registration_plan_intents"
CONSTRAINT = "ck_auth_registration_plan_intents_billing_period_allowed"


def upgrade() -> None:
    with op.batch_alter_table(TABLE) as batch_op:
        batch_op.add_column(
            sa.Column("billing_period", sa.String(length=16), nullable=True)
        )
        batch_op.create_check_constraint(
            CONSTRAINT,
            "billing_period IS NULL OR billing_period IN ('monthly', 'annual')",
        )


def downgrade() -> None:
    with op.batch_alter_table(TABLE) as batch_op:
        batch_op.drop_constraint(CONSTRAINT, type_="check")
        batch_op.drop_column("billing_period")
