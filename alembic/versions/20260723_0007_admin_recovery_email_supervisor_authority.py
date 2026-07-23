"""Add administrator recovery email and supervisor authority.

Revision ID: 20260723_0007
Revises: 20260722_0006
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260723_0007"
down_revision = "20260722_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("authority_allowed", "identity_platform_authorities", type_="check")
    op.create_check_constraint(
        "authority_allowed",
        "identity_platform_authorities",
        "authority IN ('platform_admin', 'platform_supervisor')",
    )
    op.create_table(
        "identity_user_email_addresses",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email_normalized", sa.String(length=320), nullable=False),
        sa.Column("purpose", sa.String(length=24), server_default="recovery", nullable=False),
        sa.Column("status", sa.String(length=24), server_default="pending", nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("purpose IN ('recovery')", name="purpose_allowed"),
        sa.CheckConstraint("status IN ('pending', 'verified', 'revoked')", name="status_allowed"),
        sa.ForeignKeyConstraint(["user_id"], ["identity_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email_normalized", name="uq_identity_user_email_address_email"),
        sa.UniqueConstraint("user_id", "purpose", name="uq_identity_user_email_address_user_purpose"),
    )
    op.create_index(
        "ix_identity_user_email_addresses_user_status",
        "identity_user_email_addresses",
        ["user_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_identity_user_email_addresses_user_status", table_name="identity_user_email_addresses")
    op.drop_table("identity_user_email_addresses")
    op.drop_constraint("authority_allowed", "identity_platform_authorities", type_="check")
    op.create_check_constraint(
        "authority_allowed",
        "identity_platform_authorities",
        "authority IN ('platform_admin')",
    )
