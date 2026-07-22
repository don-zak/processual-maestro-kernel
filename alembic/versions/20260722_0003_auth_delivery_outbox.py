"""Add encrypted transactional authentication delivery outbox.

Revision ID: 20260722_0003
Revises: 20260722_0002
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260722_0003"
down_revision: str | None = "20260722_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "auth_delivery_outbox",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("action_token_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("payload_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("payload_key_version", sa.String(length=40), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "event_type IN ('verify_email')",
            name="ck_auth_delivery_outbox_event_type_allowed",
        ),
        sa.CheckConstraint(
            "attempt_count >= 0",
            name="ck_auth_delivery_outbox_attempt_count_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["action_token_id"],
            ["auth_action_tokens.id"],
            name="fk_auth_delivery_outbox_action_token_id_auth_action_tokens",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["identity_users.id"],
            name="fk_auth_delivery_outbox_user_id_identity_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_auth_delivery_outbox"),
        sa.UniqueConstraint(
            "action_token_id",
            name="uq_auth_delivery_outbox_action_token_id",
        ),
    )
    op.create_index(
        "ix_auth_delivery_outbox_pending",
        "auth_delivery_outbox",
        ["delivered_at", "available_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_auth_delivery_outbox_pending",
        table_name="auth_delivery_outbox",
    )
    op.drop_table("auth_delivery_outbox")
