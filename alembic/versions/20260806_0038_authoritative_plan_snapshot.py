"""Add authoritative plan snapshots to subscription quota cycles.

Revision ID: 20260806_0038
Revises: 20260806_0037
Create Date: 2026-08-06
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import context, op

revision: str = "20260806_0038"
down_revision: str | None = "20260806_0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "admin_market_subscription_quota_cycles"
VERSION = "2026-08-plan-fulfillment-v1"


def upgrade() -> None:
    with op.batch_alter_table(TABLE) as batch:
        batch.add_column(sa.Column("plan_code", sa.String(128)))
        batch.add_column(sa.Column("plan_catalog_version", sa.String(64)))
        batch.add_column(sa.Column("entitlement_codes", sa.JSON()))

    connection = op.get_bind()
    connection.execute(
        sa.text(
            f"""
            UPDATE {TABLE}
            SET plan_code = (
                SELECT p.plan_code
                FROM admin_market_subscriptions s
                JOIN admin_market_plans p ON p.id = s.plan_id
                WHERE s.id = {TABLE}.subscription_id
            ),
            plan_catalog_version = :version,
            entitlement_codes = '[]'
            """
        ),
        {"version": VERSION},
    )

    if not context.is_offline_mode():
        missing = connection.execute(
            sa.text(
                f"SELECT 1 FROM {TABLE} "
                "WHERE plan_code IS NULL OR plan_catalog_version IS NULL LIMIT 1"
            )
        ).first()
        if missing:
            raise RuntimeError(
                "Authoritative plan snapshot migration found orphaned quota cycles"
            )

    with op.batch_alter_table(TABLE) as batch:
        batch.alter_column("plan_code", existing_type=sa.String(128), nullable=False)
        batch.alter_column(
            "plan_catalog_version",
            existing_type=sa.String(64),
            nullable=False,
        )
        batch.alter_column("entitlement_codes", existing_type=sa.JSON(), nullable=False)


def downgrade() -> None:
    if not context.is_offline_mode():
        connection = op.get_bind()
        populated = connection.execute(
            sa.text(
                f"SELECT 1 FROM {TABLE} "
                "WHERE plan_catalog_version IS NOT NULL LIMIT 1"
            )
        ).first()
        if populated:
            raise RuntimeError(
                "Downgrade blocked: authoritative plan snapshots exist"
            )
    with op.batch_alter_table(TABLE) as batch:
        batch.drop_column("entitlement_codes")
        batch.drop_column("plan_catalog_version")
        batch.drop_column("plan_code")
