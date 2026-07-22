"""Add explicit invalidation state for authentication action tokens.

Revision ID: 20260722_0004
Revises: 20260722_0003
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260722_0004"
down_revision: str | None = "20260722_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "auth_action_tokens",
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("auth_action_tokens", "invalidated_at")
