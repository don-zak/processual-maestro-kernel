"""Add shared PostgreSQL authority for External Evaluation grants and keys.

Revision ID: 20260901_0049
Revises: 20260901_0048
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260901_0049"
down_revision = "20260901_0048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evaluation_authority_state",
        sa.Column("owner_id", sa.String(length=200), nullable=False),
        sa.Column("authority", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("production_allowed", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("raw_secret_visible", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.PrimaryKeyConstraint("owner_id", name=op.f("pk_evaluation_authority_state")),
    )
    op.create_table(
        "evaluation_authority_key",
        sa.Column("key_id", sa.String(length=160), nullable=False),
        sa.Column("owner_id", sa.String(length=200), nullable=False),
        sa.Column("grant_id", sa.String(length=160), nullable=False),
        sa.Column("lookup_sha256", sa.String(length=64), nullable=True),
        sa.Column("prefix", sa.String(length=64), nullable=False),
        sa.Column("hashed", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("usage_count", sa.Integer(), nullable=False),
        sa.Column("quota_rejected_count", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("production_allowed", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("raw_secret_visible", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["evaluation_authority_state.owner_id"],
            name=op.f("fk_evaluation_authority_key_owner_id_evaluation_authority_state"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("key_id", name=op.f("pk_evaluation_authority_key")),
        sa.UniqueConstraint("lookup_sha256", name=op.f("uq_evaluation_authority_key_lookup_sha256")),
    )
    op.create_index(op.f("ix_evaluation_authority_key_owner_id"), "evaluation_authority_key", ["owner_id"], unique=False)
    op.create_index(op.f("ix_evaluation_authority_key_grant_id"), "evaluation_authority_key", ["grant_id"], unique=False)
    op.create_index(op.f("ix_evaluation_authority_key_prefix"), "evaluation_authority_key", ["prefix"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_evaluation_authority_key_prefix"), table_name="evaluation_authority_key")
    op.drop_index(op.f("ix_evaluation_authority_key_grant_id"), table_name="evaluation_authority_key")
    op.drop_index(op.f("ix_evaluation_authority_key_owner_id"), table_name="evaluation_authority_key")
    op.drop_table("evaluation_authority_key")
    op.drop_table("evaluation_authority_state")
