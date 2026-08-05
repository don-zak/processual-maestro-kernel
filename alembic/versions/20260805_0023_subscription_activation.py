"""Add atomic subscription and entitlement activation identity.

Revision ID: 20260805_0023
Revises: 20260805_0022
Create Date: 2026-08-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import context, op

revision: str = "20260805_0023"
down_revision: str | None = "20260805_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SUBSCRIPTION_TABLE = "admin_market_subscriptions"
ACTIVATION_TABLE = "admin_market_entitlement_activations"


def _assert_safe_to_downgrade() -> None:
    if context.is_offline_mode():
        return
    connection = op.get_bind()
    checks = (
        sa.text(
            "SELECT 1 FROM admin_market_entitlement_activations "
            "WHERE order_id IS NOT NULL "
            "OR activation_idempotency_key_hash IS NOT NULL "
            "OR activated_at IS NOT NULL LIMIT 1"
        ),
        sa.text(
            "SELECT 1 FROM admin_market_subscriptions "
            "WHERE order_id IS NOT NULL LIMIT 1"
        ),
        sa.text(
            "SELECT 1 FROM admin_market_orders "
            "WHERE status = 'activated' LIMIT 1"
        ),
    )
    if any(connection.execute(query).first() for query in checks):
        raise RuntimeError(
            "Downgrade blocked: automatic subscription activation exists"
        )


def upgrade() -> None:
    with op.batch_alter_table(SUBSCRIPTION_TABLE) as batch_op:
        batch_op.add_column(sa.Column("order_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_admin_market_subscription_order",
            "admin_market_orders",
            ["order_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_unique_constraint(
            "uq_admin_market_subscriptions_order_id",
            ["order_id"],
        )

    active_predicate = sa.text("status = 'active'")
    op.create_index(
        "uq_admin_market_subscriptions_active_customer",
        SUBSCRIPTION_TABLE,
        ["customer_ref"],
        unique=True,
        postgresql_where=active_predicate,
        sqlite_where=active_predicate,
    )

    with op.batch_alter_table(ACTIVATION_TABLE) as batch_op:
        batch_op.add_column(sa.Column("order_id", sa.Uuid(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "status",
                sa.String(length=24),
                server_default="activated",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "activation_idempotency_key_hash",
                sa.String(length=64),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.alter_column(
            "status",
            existing_type=sa.String(length=24),
            server_default=None,
            existing_nullable=False,
        )
        batch_op.create_check_constraint(
            op.f("ck_admin_market_entitlement_activations_status_allowed"),
            "status IN ('activated', 'failed', 'requires_review')",
        )
        batch_op.create_foreign_key(
            "fk_admin_market_entitlement_order",
            "admin_market_orders",
            ["order_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_unique_constraint(
            "uq_admin_market_entitlement_activations_subscription_id",
            ["subscription_id"],
        )
        batch_op.create_unique_constraint(
            "uq_admin_market_entitlement_activations_order_id",
            ["order_id"],
        )
        batch_op.create_unique_constraint(
            "uq_admin_market_entitlement_activations_idem_hash",
            ["activation_idempotency_key_hash"],
        )


def downgrade() -> None:
    _assert_safe_to_downgrade()

    with op.batch_alter_table(ACTIVATION_TABLE) as batch_op:
        batch_op.drop_constraint(
            "uq_admin_market_entitlement_activations_idem_hash",
            type_="unique",
        )
        batch_op.drop_constraint(
            "uq_admin_market_entitlement_activations_order_id",
            type_="unique",
        )
        batch_op.drop_constraint(
            "uq_admin_market_entitlement_activations_subscription_id",
            type_="unique",
        )
        batch_op.drop_constraint(
            "fk_admin_market_entitlement_order",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            op.f("ck_admin_market_entitlement_activations_status_allowed"),
            type_="check",
        )
        batch_op.drop_column("activated_at")
        batch_op.drop_column("activation_idempotency_key_hash")
        batch_op.drop_column("status")
        batch_op.drop_column("order_id")

    op.drop_index(
        "uq_admin_market_subscriptions_active_customer",
        table_name=SUBSCRIPTION_TABLE,
    )
    with op.batch_alter_table(SUBSCRIPTION_TABLE) as batch_op:
        batch_op.drop_constraint(
            "uq_admin_market_subscriptions_order_id",
            type_="unique",
        )
        batch_op.drop_constraint(
            "fk_admin_market_subscription_order",
            type_="foreignkey",
        )
        batch_op.drop_column("order_id")
