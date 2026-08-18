"""Persist administrator permission grants and governance audit events.

Revision ID: 20260818_0051
Revises: 20260818_0050
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa

revision = "20260818_0051"
down_revision = "20260818_0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_governance_permission_grants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("permission", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("source_invitation_id", sa.Uuid(), nullable=False),
        sa.Column("granted_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("grant_reason", sa.String(length=500), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("revocation_reason", sa.String(length=500), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('active', 'revoked')", name="status_allowed"),
        sa.ForeignKeyConstraint(["granted_by_user_id"], ["identity_users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["revoked_by_user_id"], ["identity_users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_invitation_id"], ["admin_governance_invitations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["identity_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "permission", name="uq_admin_governance_permission_user_permission"),
    )
    op.create_index(
        "ix_admin_governance_permission_user_status",
        "admin_governance_permission_grants",
        ["user_id", "status"],
        unique=False,
    )

    op.create_table(
        "admin_governance_audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("subject_user_id", sa.Uuid(), nullable=False),
        sa.Column("invitation_id", sa.Uuid(), nullable=True),
        sa.Column("permission", sa.String(length=120), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["identity_users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["invitation_id"], ["admin_governance_invitations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["subject_user_id"], ["identity_users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_admin_governance_audit_subject_occurred",
        "admin_governance_audit_events",
        ["subject_user_id", "occurred_at"],
        unique=False,
    )
    op.create_index(
        "ix_admin_governance_audit_event_occurred",
        "admin_governance_audit_events",
        ["event_type", "occurred_at"],
        unique=False,
    )


def downgrade() -> None:
    if not context.is_offline_mode():
        bind = op.get_bind()
        grant = bind.execute(
            sa.text("SELECT id FROM admin_governance_permission_grants LIMIT 1")
        ).first()
        event = bind.execute(
            sa.text("SELECT id FROM admin_governance_audit_events LIMIT 1")
        ).first()
        if grant is not None or event is not None:
            raise RuntimeError(
                "Downgrade blocked: administrator governance permission or audit records exist"
            )

    op.drop_index(
        "ix_admin_governance_audit_event_occurred",
        table_name="admin_governance_audit_events",
    )
    op.drop_index(
        "ix_admin_governance_audit_subject_occurred",
        table_name="admin_governance_audit_events",
    )
    op.drop_table("admin_governance_audit_events")
    op.drop_index(
        "ix_admin_governance_permission_user_status",
        table_name="admin_governance_permission_grants",
    )
    op.drop_table("admin_governance_permission_grants")
