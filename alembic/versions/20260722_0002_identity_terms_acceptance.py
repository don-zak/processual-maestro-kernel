"""Add immutable registration terms acceptance records.

Revision ID: 20260722_0002
Revises: 20260721_0001
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260722_0002"
down_revision: str | None = "20260721_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "identity_terms_acceptances",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("terms_version", sa.String(length=64), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["identity_users.id"],
            name="fk_identity_terms_acceptances_user_id_identity_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_identity_terms_acceptances"),
        sa.UniqueConstraint(
            "user_id",
            "terms_version",
            name="uq_identity_terms_acceptance_user_version",
        ),
    )


def downgrade() -> None:
    op.drop_table("identity_terms_acceptances")
