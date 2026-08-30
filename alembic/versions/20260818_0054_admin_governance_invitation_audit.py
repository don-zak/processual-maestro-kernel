"""Allow invitation lifecycle audit events without an identity subject.

Revision ID: 20260818_0054
Revises: 20260818_0053
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa

revision = "20260818_0054"
down_revision = "20260818_0053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("admin_governance_audit_events") as batch_op:
        batch_op.alter_column(
            "subject_user_id",
            existing_type=sa.Uuid(),
            nullable=True,
        )


def downgrade() -> None:
    if not context.is_offline_mode():
        bind = op.get_bind()
        row = bind.execute(
            sa.text(
                "SELECT id FROM admin_governance_audit_events "
                "WHERE subject_user_id IS NULL LIMIT 1"
            )
        ).first()
        if row is not None:
            raise RuntimeError(
                "Downgrade blocked: invitation governance audit records exist"
            )

    with op.batch_alter_table("admin_governance_audit_events") as batch_op:
        batch_op.alter_column(
            "subject_user_id",
            existing_type=sa.Uuid(),
            nullable=False,
        )
