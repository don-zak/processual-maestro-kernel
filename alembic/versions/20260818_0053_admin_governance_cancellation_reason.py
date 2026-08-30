"""Persist administrator invitation cancellation provenance.

Revision ID: 20260818_0053
Revises: 20260818_0052
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa

revision = "20260818_0053"
down_revision = "20260818_0052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "admin_governance_invitations",
        sa.Column("cancellation_reason", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    if not context.is_offline_mode():
        bind = op.get_bind()
        row = bind.execute(
            sa.text(
                "SELECT id FROM admin_governance_invitations "
                "WHERE cancellation_reason IS NOT NULL LIMIT 1"
            )
        ).first()
        if row is not None:
            raise RuntimeError(
                "Downgrade blocked: administrator invitation cancellation provenance exists"
            )

    op.drop_column(
        "admin_governance_invitations",
        "cancellation_reason",
    )
