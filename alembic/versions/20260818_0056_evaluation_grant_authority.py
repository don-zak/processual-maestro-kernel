"""Add durable subscription-independent evaluation grant authority.

Revision ID: 20260818_0056
Revises: 20260818_0055
Create Date: 2026-08-18
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "20260818_0056"
down_revision: str | None = "20260818_0055"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GRANTS = "evaluation_grant_authority"
KEYS = "evaluation_api_key_authority"
USAGE = "evaluation_usage_ledger"


def upgrade() -> None:
    op.create_table(
        GRANTS,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("grant_ref", sa.String(64), nullable=False),
        sa.Column("owner_user_ref", sa.String(128), nullable=False),
        sa.Column("client_ref", sa.String(160), nullable=False),
        sa.Column("user_ref", sa.String(160), nullable=False),
        sa.Column("issued_to", sa.String(240), nullable=False),
        sa.Column("purpose", sa.String(500), nullable=False),
        sa.Column("allowed_task_ids_json", sa.Text(), nullable=False),
        sa.Column("task_scope_ids_json", sa.Text(), nullable=False),
        sa.Column("allowed_scopes_json", sa.Text(), nullable=False),
        sa.Column("max_requests", sa.BigInteger(), nullable=False),
        sa.Column("used_requests", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("rejected_requests", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("approved_by_actor_ref", sa.String(240), nullable=False),
        sa.Column("approved_by_role", sa.String(80), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("max_requests > 0", name=op.f("ck_evaluation_grant_authority_max_requests")),
        sa.CheckConstraint("used_requests >= 0", name=op.f("ck_evaluation_grant_authority_used_requests")),
        sa.CheckConstraint("used_requests <= max_requests", name=op.f("ck_evaluation_grant_authority_quota_bound")),
        sa.CheckConstraint("rejected_requests >= 0", name=op.f("ck_evaluation_grant_authority_rejected_requests")),
        sa.CheckConstraint("status IN ('active','revoked','expired','disabled')", name=op.f("ck_evaluation_grant_authority_status")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("grant_ref", name="uq_evaluation_grant_authority_ref"),
    )
    op.create_index(
        "ix_evaluation_grant_authority_owner_status",
        GRANTS,
        ["owner_user_ref", "status", "expires_at"],
    )
    op.create_index(
        "ix_evaluation_grant_authority_client_status",
        GRANTS,
        ["client_ref", "status", "expires_at"],
    )

    op.create_table(
        KEYS,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key_ref", sa.String(64), nullable=False),
        sa.Column("grant_id", sa.Uuid(), nullable=False),
        sa.Column("key_hash", sa.String(512), nullable=False),
        sa.Column("key_prefix", sa.String(32), nullable=False),
        sa.Column("client_ref", sa.String(160), nullable=False),
        sa.Column("user_ref", sa.String(160), nullable=False),
        sa.Column("scopes_json", sa.Text(), nullable=False),
        sa.Column("allowed_task_ids_json", sa.Text(), nullable=False),
        sa.Column("task_scope_ids_json", sa.Text(), nullable=False),
        sa.Column("label", sa.String(160), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="enabled"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("usage_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('enabled','revoked','expired','disabled')", name=op.f("ck_evaluation_api_key_authority_status")),
        sa.CheckConstraint("usage_count >= 0", name=op.f("ck_evaluation_api_key_authority_usage_count")),
        sa.ForeignKeyConstraint(["grant_id"], [f"{GRANTS}.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_ref", name="uq_evaluation_api_key_authority_ref"),
        sa.UniqueConstraint("key_hash", name="uq_evaluation_api_key_authority_hash"),
    )
    op.create_index(
        "ix_evaluation_api_key_authority_grant_status",
        KEYS,
        ["grant_id", "status", "expires_at"],
    )
    op.create_index(
        "ix_evaluation_api_key_authority_prefix",
        KEYS,
        ["key_prefix"],
    )

    op.create_table(
        USAGE,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("grant_id", sa.Uuid(), nullable=False),
        sa.Column("key_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("units", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("task_id", sa.String(160), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("units > 0", name=op.f("ck_evaluation_usage_ledger_units")),
        sa.ForeignKeyConstraint(["grant_id"], [f"{GRANTS}.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["key_id"], [f"{KEYS}.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("grant_id", "idempotency_key", name="uq_evaluation_usage_ledger_idempotency"),
    )
    op.create_index(
        "ix_evaluation_usage_ledger_grant_created",
        USAGE,
        ["grant_id", "created_at"],
    )


def downgrade() -> None:
    if not context.is_offline_mode():
        connection = op.get_bind()
        for table in (USAGE, KEYS, GRANTS):
            if connection.execute(sa.text(f"SELECT 1 FROM {table} LIMIT 1")).first():
                raise RuntimeError(
                    f"Downgrade blocked: durable evaluation authority rows exist in {table}"
                )
    op.drop_index("ix_evaluation_usage_ledger_grant_created", table_name=USAGE)
    op.drop_table(USAGE)
    op.drop_index("ix_evaluation_api_key_authority_prefix", table_name=KEYS)
    op.drop_index("ix_evaluation_api_key_authority_grant_status", table_name=KEYS)
    op.drop_table(KEYS)
    op.drop_index("ix_evaluation_grant_authority_client_status", table_name=GRANTS)
    op.drop_index("ix_evaluation_grant_authority_owner_status", table_name=GRANTS)
    op.drop_table(GRANTS)
