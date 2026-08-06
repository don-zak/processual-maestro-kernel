"""Allow successive Lemon Squeezy events for the same resource binding.

Revision ID: 20260806_0030
Revises: 20260805_0029
Create Date: 2026-08-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import context, op

revision: str = "20260806_0030"
down_revision: str | None = "20260805_0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "admin_market_lemon_squeezy_webhook_inbox"
CONSTRAINT = "uq_admin_market_ls_webhook_resource_binding"
BINDING_COLUMNS = (
    "store_id",
    "event_name",
    "resource_type",
    "external_resource_id",
    "customer_ref",
    "order_ref",
    "offer_ref",
)


def upgrade() -> None:
    with op.batch_alter_table(TABLE) as batch_op:
        batch_op.drop_constraint(CONSTRAINT, type_="unique")


def downgrade() -> None:
    if not context.is_offline_mode():
        columns = ", ".join(BINDING_COLUMNS)
        duplicate = op.get_bind().execute(
            sa.text(
                f"SELECT 1 FROM {TABLE} "
                f"GROUP BY {columns} HAVING COUNT(*) > 1 LIMIT 1"
            )
        ).first()
        if duplicate is not None:
            raise RuntimeError(
                "Downgrade blocked: successive Lemon Squeezy resource events exist"
            )

    with op.batch_alter_table(TABLE) as batch_op:
        batch_op.create_unique_constraint(CONSTRAINT, list(BINDING_COLUMNS))
