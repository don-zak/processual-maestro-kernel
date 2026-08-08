"""add registration plan intent persistence

Revision ID: 20260803_0015
Revises: 20260729_0014
Create Date: 2026-08-03
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260803_0015"
down_revision: str | None = "20260729_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "auth_registration_plan_intents"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("selected_plan_id", sa.String(length=80), nullable=False),
        sa.Column(
            "state",
            sa.String(length=32),
            nullable=False,
            server_default="pending_verification",
        ),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
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
            "state IN ('pending_verification', 'verified', 'superseded', 'cancelled')",
            name="ck_auth_registration_plan_intents_state_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["identity_users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            name="uq_auth_registration_plan_intent_user",
        ),
    )
    op.create_index(
        "ix_auth_registration_plan_intents_state",
        TABLE,
        ["state", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_auth_registration_plan_intents_state", table_name=TABLE)
    op.drop_table(TABLE)
