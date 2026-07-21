"""Create identity, session, token, and TOTP authority tables.

Revision ID: 20260721_0001
Revises: None
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260721_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _id_column() -> sa.Column:
    return sa.Column("id", sa.Uuid(), nullable=False)


def _created_at_column() -> sa.Column:
    return sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.text("CURRENT_TIMESTAMP"),
        nullable=False,
    )


def _updated_at_column() -> sa.Column:
    return sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        server_default=sa.text("CURRENT_TIMESTAMP"),
        nullable=False,
    )


def upgrade() -> None:
    op.create_table(
        "identity_users",
        _id_column(),
        sa.Column("email_normalized", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_login_count", sa.Integer(), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        _created_at_column(),
        _updated_at_column(),
        sa.CheckConstraint(
            "status IN ('pending_verification', 'active', 'locked', 'disabled', 'deleted')",
            name="ck_identity_users_status_allowed",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_identity_users"),
        sa.UniqueConstraint("email_normalized", name="uq_identity_users_email_normalized"),
    )

    op.create_table(
        "identity_organizations",
        _id_column(),
        sa.Column("slug_normalized", sa.String(length=100), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        _created_at_column(),
        _updated_at_column(),
        sa.CheckConstraint(
            "status IN ('pending_review', 'active', 'suspended', 'closed')",
            name="ck_identity_organizations_status_allowed",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_identity_organizations"),
        sa.UniqueConstraint(
            "slug_normalized",
            name="uq_identity_organizations_slug_normalized",
        ),
    )

    op.create_table(
        "identity_memberships",
        _id_column(),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("invited_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True),
        _created_at_column(),
        _updated_at_column(),
        sa.CheckConstraint(
            "role IN ('organization_owner', 'organization_admin', 'operator', 'auditor', 'viewer')",
            name="ck_identity_memberships_role_allowed",
        ),
        sa.CheckConstraint(
            "status IN ('invited', 'active', 'suspended', 'revoked')",
            name="ck_identity_memberships_status_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["invited_by_user_id"],
            ["identity_users.id"],
            name="fk_identity_memberships_invited_by_user_id_identity_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["identity_organizations.id"],
            name="fk_identity_memberships_organization_id_identity_organizations",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["identity_users.id"],
            name="fk_identity_memberships_user_id_identity_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_identity_memberships"),
        sa.UniqueConstraint(
            "user_id",
            "organization_id",
            name="uq_identity_membership_user_org",
        ),
    )
    op.create_index(
        "ix_identity_memberships_organization_role",
        "identity_memberships",
        ["organization_id", "role"],
        unique=False,
    )

    op.create_table(
        "auth_sessions",
        _id_column(),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("refresh_family_id", sa.Uuid(), nullable=False),
        sa.Column("authenticated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("mfa_satisfied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.String(length=80), nullable=True),
        _created_at_column(),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["identity_organizations.id"],
            name="fk_auth_sessions_organization_id_identity_organizations",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["identity_users.id"],
            name="fk_auth_sessions_user_id_identity_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_auth_sessions"),
        sa.UniqueConstraint("refresh_family_id", name="uq_auth_sessions_refresh_family_id"),
    )
    op.create_index(
        "ix_auth_sessions_user_active",
        "auth_sessions",
        ["user_id", "revoked_at", "expires_at"],
        unique=False,
    )

    op.create_table(
        "auth_refresh_tokens",
        _id_column(),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("parent_token_id", sa.Uuid(), nullable=True),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reuse_detected_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["parent_token_id"],
            ["auth_refresh_tokens.id"],
            name="fk_auth_refresh_tokens_parent_token_id_auth_refresh_tokens",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["auth_sessions.id"],
            name="fk_auth_refresh_tokens_session_id_auth_sessions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_auth_refresh_tokens"),
        sa.UniqueConstraint("token_hash", name="uq_auth_refresh_tokens_token_hash"),
    )
    op.create_index(
        "ix_auth_refresh_tokens_session_expiry",
        "auth_refresh_tokens",
        ["session_id", "expires_at"],
        unique=False,
    )

    op.create_table(
        "auth_action_tokens",
        _id_column(),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        _created_at_column(),
        sa.CheckConstraint(
            "purpose IN ('verify_email', 'reset_password', 'change_email', 'accept_invitation')",
            name="ck_auth_action_tokens_purpose_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["identity_users.id"],
            name="fk_auth_action_tokens_user_id_identity_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_auth_action_tokens"),
        sa.UniqueConstraint("token_hash", name="uq_auth_action_tokens_token_hash"),
    )
    op.create_index(
        "ix_auth_action_tokens_user_purpose",
        "auth_action_tokens",
        ["user_id", "purpose", "expires_at"],
        unique=False,
    )

    op.create_table(
        "auth_mfa_factors",
        _id_column(),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("factor_type", sa.String(length=24), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("secret_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("secret_key_version", sa.String(length=40), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_step", sa.BigInteger(), nullable=True),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        _created_at_column(),
        _updated_at_column(),
        sa.CheckConstraint("factor_type IN ('totp')", name="ck_auth_mfa_factors_factor_type_allowed"),
        sa.CheckConstraint(
            "status IN ('pending', 'active', 'disabled')",
            name="ck_auth_mfa_factors_status_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["identity_users.id"],
            name="fk_auth_mfa_factors_user_id_identity_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_auth_mfa_factors"),
        sa.UniqueConstraint(
            "user_id",
            "factor_type",
            "label",
            name="uq_auth_mfa_factor_user_type_label",
        ),
    )
    op.create_index(
        "ix_auth_mfa_factors_user_status",
        "auth_mfa_factors",
        ["user_id", "status"],
        unique=False,
    )

    op.create_table(
        "auth_mfa_recovery_codes",
        _id_column(),
        sa.Column("factor_id", sa.Uuid(), nullable=False),
        sa.Column("code_hash", sa.String(length=128), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        _created_at_column(),
        sa.ForeignKeyConstraint(
            ["factor_id"],
            ["auth_mfa_factors.id"],
            name="fk_auth_mfa_recovery_codes_factor_id_auth_mfa_factors",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_auth_mfa_recovery_codes"),
        sa.UniqueConstraint("code_hash", name="uq_auth_mfa_recovery_codes_code_hash"),
    )

    op.create_table(
        "auth_mfa_challenges",
        _id_column(),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("challenge_hash", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        _created_at_column(),
        sa.CheckConstraint(
            "status IN ('pending', 'verified', 'expired', 'locked')",
            name="ck_auth_mfa_challenges_status_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["identity_users.id"],
            name="fk_auth_mfa_challenges_user_id_identity_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_auth_mfa_challenges"),
        sa.UniqueConstraint("challenge_hash", name="uq_auth_mfa_challenges_challenge_hash"),
    )
    op.create_index(
        "ix_auth_mfa_challenges_user_expiry",
        "auth_mfa_challenges",
        ["user_id", "expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_auth_mfa_challenges_user_expiry", table_name="auth_mfa_challenges")
    op.drop_table("auth_mfa_challenges")
    op.drop_table("auth_mfa_recovery_codes")
    op.drop_index("ix_auth_mfa_factors_user_status", table_name="auth_mfa_factors")
    op.drop_table("auth_mfa_factors")
    op.drop_index("ix_auth_action_tokens_user_purpose", table_name="auth_action_tokens")
    op.drop_table("auth_action_tokens")
    op.drop_index("ix_auth_refresh_tokens_session_expiry", table_name="auth_refresh_tokens")
    op.drop_table("auth_refresh_tokens")
    op.drop_index("ix_auth_sessions_user_active", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_index(
        "ix_identity_memberships_organization_role",
        table_name="identity_memberships",
    )
    op.drop_table("identity_memberships")
    op.drop_table("identity_organizations")
    op.drop_table("identity_users")
