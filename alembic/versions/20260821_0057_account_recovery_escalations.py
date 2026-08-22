"""Add durable account recovery escalation queue.

Revision ID: 20260821_0057
Revises: 20260818_0056
Create Date: 2026-08-21
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "20260821_0057"
down_revision: str | None = "20260818_0056"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "auth_account_recovery_escalations"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("claimed_login", sa.String(320), nullable=False),
        sa.Column("contact_email", sa.String(320), nullable=False),
        sa.Column("organization_ref", sa.String(160), nullable=True),
        sa.Column("reason", sa.String(40), nullable=False),
        sa.Column("state", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("reviewed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("resolution", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "reason IN ('lost_recovery_email','lost_authenticator','recovery_codes_unavailable','account_locked','other')",
            name=op.f("ck_auth_account_recovery_escalations_reason"),
        ),
        sa.CheckConstraint(
            "state IN ('pending','resolved','rejected')",
            name=op.f("ck_auth_account_recovery_escalations_state"),
        ),
        sa.CheckConstraint(
            "resolution IS NULL OR resolution IN ('recovery_channel_reviewed','identity_evidence_insufficient','duplicate','resolved_externally')",
            name=op.f("ck_auth_account_recovery_escalations_resolution"),
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by_user_id"],
            ["identity_users.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_auth_account_recovery_escalations_state_created",
        TABLE,
        ["state", "created_at"],
    )
    op.create_index(
        "ix_auth_account_recovery_escalations_claimed_login",
        TABLE,
        ["claimed_login"],
    )


def downgrade() -> None:
    if not context.is_offline_mode():
        connection = op.get_bind()
        if connection.execute(sa.text(f"SELECT 1 FROM {TABLE} LIMIT 1")).first():
            raise RuntimeError(
                "Downgrade blocked: durable account recovery escalation rows exist"
            )
    op.drop_index(
        "ix_auth_account_recovery_escalations_claimed_login",
        table_name=TABLE,
    )
    op.drop_index(
        "ix_auth_account_recovery_escalations_state_created",
        table_name=TABLE,
    )
    op.drop_table(TABLE)
