"""Persist administrator invitation delivery outbox.

Revision ID: 20260818_0052
Revises: 20260818_0051
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa

revision = "20260818_0052"
down_revision = "20260818_0051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_governance_invitation_delivery_outbox",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("invitation_id", sa.Uuid(), nullable=False),
        sa.Column("recipient_email_normalized", sa.String(length=320), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("payload_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("payload_key_version", sa.String(length=80), nullable=False),
        sa.Column("idempotency_key", sa.String(length=180), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'delivered', 'failed', 'dead')",
            name="status_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["invitation_id"],
            ["admin_governance_invitations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index(
        "ix_admin_governance_delivery_status_next",
        "admin_governance_invitation_delivery_outbox",
        ["status", "next_attempt_at"],
        unique=False,
    )


def downgrade() -> None:
    if not context.is_offline_mode():
        bind = op.get_bind()
        row = bind.execute(
            sa.text("SELECT id FROM admin_governance_invitation_delivery_outbox LIMIT 1")
        ).first()
        if row is not None:
            raise RuntimeError(
                "Downgrade blocked: administrator governance delivery outbox records exist"
            )

    op.drop_index(
        "ix_admin_governance_delivery_status_next",
        table_name="admin_governance_invitation_delivery_outbox",
    )
    op.drop_table("admin_governance_invitation_delivery_outbox")
