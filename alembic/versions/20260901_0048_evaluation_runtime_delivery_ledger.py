"""Add shared PostgreSQL delivery ledger for External Evaluation runtime.

Revision ID: 20260901_0048
Revises: 20260830_0047
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260901_0048"
down_revision: str | None = "20260830_0047"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "evaluation_runtime_delivery"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("record_id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("owner_id_sha256", sa.String(length=64), nullable=False),
        sa.Column("grant_id", sa.String(length=160), nullable=False),
        sa.Column("api_key_id", sa.String(length=160), nullable=False),
        sa.Column("idempotency_key_sha256", sa.String(length=64), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("task_id", sa.String(length=160), nullable=False),
        sa.Column("binding_id", sa.String(length=160), nullable=False),
        sa.Column("state", sa.String(length=40), nullable=False),
        sa.Column("state_history", sa.JSON(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=True),
        sa.Column("replay_response", sa.JSON(), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("execution_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evidence_persisted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.String(length=200), nullable=True),
        sa.Column("network_outcome", sa.String(length=40), nullable=True),
        sa.Column(
            "raw_task_input_persisted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "raw_secret_visible",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.UniqueConstraint(
            "owner_id_sha256",
            "grant_id",
            "api_key_id",
            "idempotency_key_sha256",
            name="uq_evaluation_runtime_delivery_authority_key",
        ),
        sa.CheckConstraint(
            "state IN ('executing', 'evidence_persisted', 'failed')",
            name=op.f("ck_evaluation_runtime_delivery_state"),
        ),
    )
    op.create_index(
        "ix_evaluation_runtime_delivery_owner_state",
        TABLE,
        ["owner_id_sha256", "state"],
    )


def downgrade() -> None:
    op.drop_index("ix_evaluation_runtime_delivery_owner_state", table_name=TABLE)
    op.drop_table(TABLE)
