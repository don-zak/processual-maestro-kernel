"""Add atomic subscription and entitlement activation identity.

Revision ID: 20260805_0023
Revises: 20260805_0022
Create Date: 2026-08-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260805_0023"
down_revision: str | None = "20260805_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "admin_market_subscriptions",
        sa.Column("order_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_admin_market_subscription_order",
        "admin_market_subscriptions",
        "admin_market_orders",
        ["order_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_admin_market_subscriptions_order_id",
        "admin_market_subscriptions",
        ["order_id"],
    )
    op.create_index(
        "uq_admin_market_subscriptions_active_customer",
        "admin_market_subscriptions",
        ["customer_ref"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.add_column(
        "admin_market_entitlement_activations",
        sa.Column("order_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "admin_market_entitlement_activations",
        sa.Column(
            "status",
            sa.String(length=24),
            server_default="activated",
            nullable=False,
        ),
    )
    op.add_column(
        "admin_market_entitlement_activations",
        sa.Column(
            "activation_idempotency_key_hash",
            sa.String(length=64),
            nullable=True,
        ),
    )
    op.add_column(
        "admin_market_entitlement_activations",
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.alter_column(
        "admin_market_entitlement_activations",
        "status",
        server_default=None,
    )
    op.create_check_constraint(
        op.f("ck_admin_market_entitlement_activations_status_allowed"),
        "admin_market_entitlement_activations",
        "status IN ('activated', 'failed', 'requires_review')",
    )
    op.create_foreign_key(
        "fk_admin_market_entitlement_order",
        "admin_market_entitlement_activations",
        "admin_market_orders",
        ["order_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_admin_market_entitlement_activations_subscription_id",
        "admin_market_entitlement_activations",
        ["subscription_id"],
    )
    op.create_unique_constraint(
        "uq_admin_market_entitlement_activations_order_id",
        "admin_market_entitlement_activations",
        ["order_id"],
    )
    op.create_unique_constraint(
        "uq_admin_market_entitlement_activations_idem_hash",
        "admin_market_entitlement_activations",
        ["activation_idempotency_key_hash"],
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM admin_market_entitlement_activations
                WHERE order_id IS NOT NULL
                   OR activation_idempotency_key_hash IS NOT NULL
                   OR activated_at IS NOT NULL
            )
               OR EXISTS (
                    SELECT 1 FROM admin_market_subscriptions
                    WHERE order_id IS NOT NULL
               )
               OR EXISTS (
                    SELECT 1 FROM admin_market_orders
                    WHERE status = 'activated'
               )
            THEN
                RAISE EXCEPTION
                    'Downgrade blocked: automatic subscription activation exists';
            END IF;
        END $$
        """
    )
    op.drop_constraint(
        "uq_admin_market_entitlement_activations_idem_hash",
        "admin_market_entitlement_activations",
        type_="unique",
    )
    op.drop_constraint(
        "uq_admin_market_entitlement_activations_order_id",
        "admin_market_entitlement_activations",
        type_="unique",
    )
    op.drop_constraint(
        "uq_admin_market_entitlement_activations_subscription_id",
        "admin_market_entitlement_activations",
        type_="unique",
    )
    op.drop_constraint(
        "fk_admin_market_entitlement_order",
        "admin_market_entitlement_activations",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("ck_admin_market_entitlement_activations_status_allowed"),
        "admin_market_entitlement_activations",
        type_="check",
    )
    op.drop_column("admin_market_entitlement_activations", "activated_at")
    op.drop_column(
        "admin_market_entitlement_activations",
        "activation_idempotency_key_hash",
    )
    op.drop_column("admin_market_entitlement_activations", "status")
    op.drop_column("admin_market_entitlement_activations", "order_id")

    op.drop_index(
        "uq_admin_market_subscriptions_active_customer",
        table_name="admin_market_subscriptions",
    )
    op.drop_constraint(
        "uq_admin_market_subscriptions_order_id",
        "admin_market_subscriptions",
        type_="unique",
    )
    op.drop_constraint(
        "fk_admin_market_subscription_order",
        "admin_market_subscriptions",
        type_="foreignkey",
    )
    op.drop_column("admin_market_subscriptions", "order_id")
