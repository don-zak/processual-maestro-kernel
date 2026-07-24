"""Add account recovery persistence foundation.

Revision ID: 20260723_0009
Revises: 20260723_0008
"""

import sqlalchemy as sa

from alembic import op

revision = "20260723_0009"
down_revision = "20260723_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_account_recovery_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("recovery_email_id", sa.Uuid(), nullable=True),
        sa.Column(
            "purpose",
            sa.String(length=40),
            nullable=False,
        ),
        sa.Column(
            "state",
            sa.String(length=24),
            nullable=False,
        ),
        sa.Column(
            "verification_token_hash",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "completion_token_hash",
            sa.String(length=128),
            nullable=True,
        ),
        sa.Column(
            "attempt_count",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "verified_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
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
            "purpose IN ('platform_account_recovery')",
            name=("ck_auth_account_recovery_requests_purpose_allowed"),
        ),
        sa.CheckConstraint(
            ("state IN ('pending', 'verified', 'completed', 'expired', 'revoked')"),
            name=("ck_auth_account_recovery_requests_state_allowed"),
        ),
        sa.CheckConstraint(
            "attempt_count >= 0",
            name=("ck_auth_account_recovery_requests_attempt_count_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["identity_users.id"],
            name=("fk_auth_account_recovery_requests_user_id_identity_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["recovery_email_id"],
            ["identity_user_email_addresses.id"],
            name=("fk_auth_account_recovery_recovery_email"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_auth_account_recovery_requests",
        ),
        sa.UniqueConstraint(
            "verification_token_hash",
            name=("uq_auth_account_recovery_requests_verification_token_hash"),
        ),
        sa.UniqueConstraint(
            "completion_token_hash",
            name=("uq_auth_account_recovery_requests_completion_token_hash"),
        ),
    )

    op.create_index(
        "ix_auth_account_recovery_user_state",
        "auth_account_recovery_requests",
        ["user_id", "state", "expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_auth_account_recovery_expiry",
        "auth_account_recovery_requests",
        ["state", "expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_auth_account_recovery_expiry",
        table_name="auth_account_recovery_requests",
    )
    op.drop_index(
        "ix_auth_account_recovery_user_state",
        table_name="auth_account_recovery_requests",
    )
    op.drop_table("auth_account_recovery_requests")
