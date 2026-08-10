"""Add authoritative ownership snapshot to top-up orders.

Revision ID: 20260807_0040
Revises: 20260807_0039
Create Date: 2026-08-07
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import context, op

revision: str = "20260807_0040"
down_revision: str | None = "20260807_0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ORDER_TABLE = "commercial_top_up_orders"
CATALOG_VERSION = "2026-08-plan-fulfillment-v1"


def upgrade() -> None:
    with op.batch_alter_table(ORDER_TABLE) as batch:
        batch.alter_column("account_id", existing_type=sa.Uuid(), nullable=True)
        batch.add_column(sa.Column("customer_ref", sa.String(128)))
        batch.add_column(sa.Column("quota_cycle_id", sa.Uuid()))
        batch.add_column(sa.Column("plan_catalog_version", sa.String(64)))

    update_statement = sa.text(
        f"""
        UPDATE {ORDER_TABLE}
        SET customer_ref = (
                SELECT s.customer_ref
                FROM admin_market_subscriptions s
                WHERE s.id = {ORDER_TABLE}.subscription_id
            ),
            quota_cycle_id = (
                SELECT q.id
                FROM admin_market_subscription_quota_cycles q
                WHERE q.subscription_id = {ORDER_TABLE}.subscription_id
                  AND q.period_start <= {ORDER_TABLE}.created_at
                  AND {ORDER_TABLE}.created_at < q.period_end
                ORDER BY q.period_start DESC
                LIMIT 1
            ),
            plan_catalog_version = '{CATALOG_VERSION}'
        """
    )

    if context.is_offline_mode():
        op.execute(update_statement)
    else:
        connection = op.get_bind()
        connection.execute(update_statement)
        unresolved = connection.execute(
            sa.text(
                f"""
                SELECT 1 FROM {ORDER_TABLE}
                WHERE customer_ref IS NULL
                   OR quota_cycle_id IS NULL
                   OR plan_catalog_version IS NULL
                LIMIT 1
                """
            )
        ).first()
        if unresolved:
            raise RuntimeError(
                "Top-up order authority migration found an order without a resolvable subscription cycle"
            )

    with op.batch_alter_table(ORDER_TABLE) as batch:
        batch.alter_column(
            "customer_ref",
            existing_type=sa.String(128),
            nullable=False,
        )
        batch.alter_column(
            "quota_cycle_id",
            existing_type=sa.Uuid(),
            nullable=False,
        )
        batch.alter_column(
            "plan_catalog_version",
            existing_type=sa.String(64),
            nullable=False,
        )
        batch.create_foreign_key(
            "fk_commercial_top_up_orders_subscription",
            "admin_market_subscriptions",
            ["subscription_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_foreign_key(
            "fk_commercial_top_up_orders_quota_cycle",
            "admin_market_subscription_quota_cycles",
            ["quota_cycle_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_index(
            "ix_commercial_top_up_orders_customer_state",
            ["customer_ref", "state"],
        )


def downgrade() -> None:
    with op.batch_alter_table(ORDER_TABLE) as batch:
        batch.drop_index("ix_commercial_top_up_orders_customer_state")
        batch.drop_constraint(
            "fk_commercial_top_up_orders_quota_cycle",
            type_="foreignkey",
        )
        batch.drop_constraint(
            "fk_commercial_top_up_orders_subscription",
            type_="foreignkey",
        )
        batch.drop_column("plan_catalog_version")
        batch.drop_column("quota_cycle_id")
        batch.drop_column("customer_ref")
        batch.alter_column("account_id", existing_type=sa.Uuid(), nullable=False)
