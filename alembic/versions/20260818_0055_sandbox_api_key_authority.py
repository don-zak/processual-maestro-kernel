"""Add durable sandbox API-key authority.

Revision ID: 20260818_0055
Revises: 20260818_0054
Create Date: 2026-08-18
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "20260818_0055"
down_revision: str | None = "20260818_0054"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "sandbox_api_key_authority"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key_hash", sa.String(512), nullable=False),
        sa.Column("key_prefix", sa.String(32), nullable=False),
        sa.Column("client_ref", sa.String(128), nullable=False),
        sa.Column("owner_user_ref", sa.String(128), nullable=False),
        sa.Column("subscription_id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.String(128), nullable=False),
        sa.Column("operational_profile_id", sa.String(128), nullable=False),
        sa.Column("scopes_json", sa.Text(), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("purpose", sa.String(240), nullable=False),
        sa.Column("issued_to", sa.String(128), nullable=False),
        sa.Column("issued_by_actor_ref", sa.String(128), nullable=False),
        sa.Column("environment", sa.String(16), nullable=False, server_default="sandbox"),
        sa.Column("status", sa.String(16), nullable=False, server_default="enabled"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("usage_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("environment = 'sandbox'", name=op.f("ck_sandbox_api_key_authority_environment")),
        sa.CheckConstraint("status IN ('enabled','revoked','expired','disabled')", name=op.f("ck_sandbox_api_key_authority_status")),
        sa.CheckConstraint("usage_count >= 0", name=op.f("ck_sandbox_api_key_authority_usage_count")),
        sa.ForeignKeyConstraint(["subscription_id"], ["admin_market_subscriptions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_hash", name="uq_sandbox_api_key_authority_hash"),
    )
    op.create_index(
        "ix_sandbox_api_key_authority_client_status",
        TABLE,
        ["client_ref", "status", "expires_at"],
    )
    op.create_index(
        "ix_sandbox_api_key_authority_subscription",
        TABLE,
        ["subscription_id", "status"],
    )


def downgrade() -> None:
    if not context.is_offline_mode():
        connection = op.get_bind()
        if connection.execute(sa.text(f"SELECT 1 FROM {TABLE} LIMIT 1")).first():
            raise RuntimeError("Downgrade blocked: sandbox API-key authority rows exist")
    op.drop_index("ix_sandbox_api_key_authority_subscription", table_name=TABLE)
    op.drop_index("ix_sandbox_api_key_authority_client_status", table_name=TABLE)
    op.drop_table(TABLE)
