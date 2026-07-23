"""Add independent platform authority persistence.

Revision ID: 20260722_0006
Revises: 20260722_0005
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260722_0006"
down_revision: str | None = "20260722_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "identity_platform_authorities",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "authority",
            sa.String(length=40),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=24),
            nullable=False,
        ),
        sa.Column(
            "granted_by_user_id",
            sa.Uuid(),
            nullable=True,
        ),
        sa.Column(
            "grant_reason",
            sa.String(length=500),
            nullable=False,
        ),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "revoked_by_user_id",
            sa.Uuid(),
            nullable=True,
        ),
        sa.Column(
            "revoke_reason",
            sa.String(length=500),
            nullable=True,
        ),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "authority IN ('platform_admin')",
            name="authority_allowed",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'revoked')",
            name="status_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["granted_by_user_id"],
            ["identity_users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["revoked_by_user_id"],
            ["identity_users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["identity_users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "authority",
            name="uq_identity_platform_authority_user_authority",
        ),
    )
    op.create_index(
        "ix_identity_platform_authorities_authority_status",
        "identity_platform_authorities",
        ["authority", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_identity_platform_authorities_authority_status",
        table_name="identity_platform_authorities",
    )
    op.drop_table("identity_platform_authorities")
