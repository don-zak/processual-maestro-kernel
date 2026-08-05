"""Add fail-closed Lemon Squeezy webhook inbox.

Revision ID: 20260805_0026
Revises: 20260805_0025
Create Date: 2026-08-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import context, op

revision: str = "20260805_0026"
down_revision: str | None = "20260805_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "admin_market_lemon_squeezy_webhook_inbox"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_identity_hash", sa.String(length=64), nullable=False),
        sa.Column("payload_digest", sa.String(length=64), nullable=False),
        sa.Column("event_name", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=32), nullable=False),
        sa.Column("external_resource_id", sa.String(length=128), nullable=False),
        sa.Column("store_id", sa.String(length=128), nullable=False),
        sa.Column("customer_ref", sa.String(length=128), nullable=False),
        sa.Column("order_ref", sa.String(length=128), nullable=False),
        sa.Column("offer_ref", sa.String(length=128), nullable=False),
        sa.Column("test_mode", sa.Boolean(), nullable=False),
        sa.Column("processing_status", sa.String(length=24), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("last_error_code", sa.String(length=128), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "processing_status IN ('received', 'processing', 'processed', 'rejected')",
            name=op.f("ck_admin_market_ls_webhook_inbox_status_allowed"),
        ),
        sa.CheckConstraint(
            "attempt_count >= 0",
            name=op.f("ck_admin_market_ls_webhook_inbox_attempt_nonnegative"),
        ),
        sa.CheckConstraint(
            "length(event_identity_hash) = 64 AND length(payload_digest) = 64",
            name=op.f("ck_admin_market_ls_webhook_inbox_digest_lengths"),
        ),
        sa.CheckConstraint(
            "(processing_status = 'processed' AND processed_at IS NOT NULL AND rejected_at IS NULL) "
            "OR (processing_status = 'rejected' AND rejected_at IS NOT NULL AND processed_at IS NULL) "
            "OR (processing_status IN ('received', 'processing') AND processed_at IS NULL AND rejected_at IS NULL)",
            name=op.f("ck_admin_market_ls_webhook_inbox_terminal_timestamps"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "event_identity_hash",
            name="uq_admin_market_ls_webhook_event_identity",
        ),
        sa.UniqueConstraint(
            "payload_digest",
            name="uq_admin_market_ls_webhook_payload_digest",
        ),
        sa.UniqueConstraint(
            "store_id",
            "event_name",
            "resource_type",
            "external_resource_id",
            "customer_ref",
            "order_ref",
            "offer_ref",
            name="uq_admin_market_ls_webhook_resource_binding",
        ),
    )
    op.create_index(
        "ix_admin_market_ls_webhook_dispatch",
        TABLE,
        ["processing_status", "received_at", "claimed_at"],
    )
    op.create_index(
        "ix_admin_market_ls_webhook_order_time",
        TABLE,
        ["order_ref", "received_at"],
    )


def downgrade() -> None:
    if not context.is_offline_mode():
        connection = op.get_bind()
        if connection.execute(sa.text(f"SELECT 1 FROM {TABLE} LIMIT 1")).first():
            raise RuntimeError(
                "Downgrade blocked: Lemon Squeezy webhook inbox rows exist"
            )
    op.drop_index("ix_admin_market_ls_webhook_order_time", table_name=TABLE)
    op.drop_index("ix_admin_market_ls_webhook_dispatch", table_name=TABLE)
    op.drop_table(TABLE)
