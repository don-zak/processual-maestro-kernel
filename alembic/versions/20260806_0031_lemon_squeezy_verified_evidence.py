"""Persist immutable verified Lemon Squeezy evidence.

Revision ID: 20260806_0031
Revises: 20260806_0030
Create Date: 2026-08-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260806_0031"
down_revision: str | None = "20260806_0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "admin_market_lemon_squeezy_webhook_inbox"


def upgrade() -> None:
    with op.batch_alter_table(_TABLE) as batch_op:
        batch_op.add_column(sa.Column("evidence_schema_version", sa.Integer()))
        batch_op.add_column(sa.Column("provider_customer_id", sa.String(128)))
        batch_op.add_column(sa.Column("provider_order_id", sa.String(128)))
        batch_op.add_column(sa.Column("provider_subscription_id", sa.String(128)))
        batch_op.add_column(sa.Column("variant_id", sa.String(128)))
        batch_op.add_column(sa.Column("currency", sa.String(3)))
        batch_op.add_column(sa.Column("total_amount", sa.String(64)))
        batch_op.add_column(sa.Column("provider_status", sa.String(64)))
        batch_op.add_column(sa.Column("provider_effective_at", sa.DateTime(timezone=True)))
        batch_op.create_check_constraint(
            op.f("ck_admin_market_ls_webhook_inbox_evidence_schema_version_positive"),
            "evidence_schema_version IS NULL OR evidence_schema_version >= 1",
        )
        batch_op.create_check_constraint(
            op.f("ck_admin_market_ls_webhook_inbox_evidence_currency_length"),
            "currency IS NULL OR length(currency) = 3",
        )
        batch_op.create_check_constraint(
            op.f("ck_admin_market_ls_webhook_inbox_evidence_core_complete"),
            "(evidence_schema_version IS NULL AND provider_customer_id IS NULL "
            "AND provider_status IS NULL AND provider_effective_at IS NULL) "
            "OR (evidence_schema_version IS NOT NULL AND provider_customer_id IS NOT NULL "
            "AND provider_status IS NOT NULL AND provider_effective_at IS NOT NULL)",
        )
        batch_op.create_index(
            "ix_admin_market_ls_webhook_provider_customer",
            ["provider_customer_id", "provider_effective_at"],
        )
        batch_op.create_index(
            "ix_admin_market_ls_webhook_provider_subscription",
            ["provider_subscription_id", "provider_effective_at"],
        )


def downgrade() -> None:
    with op.batch_alter_table(_TABLE) as batch_op:
        batch_op.drop_index("ix_admin_market_ls_webhook_provider_subscription")
        batch_op.drop_index("ix_admin_market_ls_webhook_provider_customer")
        batch_op.drop_constraint(
            op.f("ck_admin_market_ls_webhook_inbox_evidence_core_complete"),
            type_="check",
        )
        batch_op.drop_constraint(
            op.f("ck_admin_market_ls_webhook_inbox_evidence_currency_length"),
            type_="check",
        )
        batch_op.drop_constraint(
            op.f("ck_admin_market_ls_webhook_inbox_evidence_schema_version_positive"),
            type_="check",
        )
        for column_name in (
            "provider_effective_at",
            "provider_status",
            "total_amount",
            "currency",
            "variant_id",
            "provider_subscription_id",
            "provider_order_id",
            "provider_customer_id",
            "evidence_schema_version",
        ):
            batch_op.drop_column(column_name)
