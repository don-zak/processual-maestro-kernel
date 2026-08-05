"""Add transactional commercial notification outbox.

Revision ID: 20260805_0025
Revises: 20260805_0024
Create Date: 2026-08-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260805_0025"
down_revision: str | None = "20260805_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "admin_market_notification_outbox",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_ref", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=48), nullable=False),
        sa.Column("aggregate_type", sa.String(length=32), nullable=False),
        sa.Column("aggregate_ref", sa.String(length=128), nullable=False),
        sa.Column("recipient_customer_ref", sa.String(length=128), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("deduplication_key_hash", sa.String(length=64), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("claim_id", sa.Uuid(), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dead_lettered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('order_created', 'contract_completed', 'payment_instructions_ready', "
            "'payment_reported', 'payment_verified', 'payment_requires_review', "
            "'subscription_activated', 'activation_failed', 'order_cancelled')",
            name=op.f("ck_admin_market_notification_outbox_event_type_allowed"),
        ),
        sa.CheckConstraint(
            "attempt_count >= 0",
            name=op.f("ck_admin_market_notification_outbox_attempt_count_nonnegative"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_ref", name="uq_admin_market_notification_event_ref"),
        sa.UniqueConstraint("deduplication_key_hash", name="uq_admin_market_notification_dedup_hash"),
    )
    op.create_index(
        "ix_admin_market_notification_outbox_dispatch",
        "admin_market_notification_outbox",
        ["delivered_at", "dead_lettered_at", "available_at", "claimed_at"],
    )


def downgrade() -> None:
    connection = op.get_bind()
    if connection.execute(
        sa.text("SELECT 1 FROM admin_market_notification_outbox LIMIT 1")
    ).first():
        raise RuntimeError(
            "Downgrade blocked: commercial notification outbox rows exist"
        )
    op.drop_index(
        "ix_admin_market_notification_outbox_dispatch",
        table_name="admin_market_notification_outbox",
    )
    op.drop_table("admin_market_notification_outbox")
