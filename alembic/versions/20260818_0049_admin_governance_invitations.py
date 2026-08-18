"""Persist email-bound administrator governance invitations.

Revision ID: 20260818_0049
Revises: 20260817_0048
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260818_0049"
down_revision = "20260817_0048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_governance_invitations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email_normalized", sa.String(length=320), nullable=False),
        sa.Column("supervision_level", sa.String(length=40), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("invited_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("invite_reason", sa.String(length=500), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "supervision_level IN ('operations_supervisor', 'review_supervisor')",
            name=op.f("ck_admin_governance_invitations_supervision_level_allowed"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'expired', 'cancelled')",
            name=op.f("ck_admin_governance_invitations_status_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["invited_by_user_id"],
            ["identity_users.id"],
            name=op.f("fk_admin_governance_invitations_invited_by_user_id_identity_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["accepted_by_user_id"],
            ["identity_users.id"],
            name=op.f("fk_admin_governance_invitations_accepted_by_user_id_identity_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["cancelled_by_user_id"],
            ["identity_users.id"],
            name=op.f("fk_admin_governance_invitations_cancelled_by_user_id_identity_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_admin_governance_invitations")),
        sa.UniqueConstraint(
            "token_hash",
            name=op.f("uq_admin_governance_invitations_token_hash"),
        ),
    )
    op.create_index(
        "ix_admin_governance_invitations_email_status",
        "admin_governance_invitations",
        ["email_normalized", "status", "expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_admin_governance_invitations_inviter_created",
        "admin_governance_invitations",
        ["invited_by_user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_admin_governance_invitations_inviter_created",
        table_name="admin_governance_invitations",
    )
    op.drop_index(
        "ix_admin_governance_invitations_email_status",
        table_name="admin_governance_invitations",
    )
    op.drop_table("admin_governance_invitations")
