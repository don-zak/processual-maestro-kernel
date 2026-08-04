"""Add trusted Tunisia payment choice and direct order foundation.

Revision ID: 20260804_0020
Revises: 20260804_0019
Create Date: 2026-08-04
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260804_0020"
down_revision: str | None = "20260804_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_AUDIT_ACTIONS = """
action IN (
    'authority_checked',
    'offer_decided',
    'channel_eligibility_decided',
    'channel_selected',
    'payment_verification_decided',
    'subscription_activation_decided',
    'payment_destination_created',
    'payment_destination_validated',
    'payment_destination_activated',
    'payment_destination_deactivated',
    'payment_destination_default_set',
    'order_created'
)
"""

_PREVIOUS_AUDIT_ACTIONS = """
action IN (
    'authority_checked',
    'offer_decided',
    'channel_eligibility_decided',
    'channel_selected',
    'payment_verification_decided',
    'subscription_activation_decided',
    'payment_destination_created',
    'payment_destination_validated',
    'payment_destination_activated',
    'payment_destination_deactivated',
    'payment_destination_default_set'
)
"""

_ORDER_STATUS = """
status IN (
    'draft',
    'awaiting_contract',
    'awaiting_payment',
    'payment_under_review',
    'ready_for_activation',
    'activated',
    'cancelled',
    'expired',
    'requires_review'
)
"""

_PREVIOUS_ORDER_STATUS = """
status IN (
    'draft',
    'submitted',
    'awaiting_payment_verification',
    'approved',
    'rejected',
    'cancelled',
    'fulfilled'
)
"""


def upgrade() -> None:
    op.add_column(
        "admin_market_offers",
        sa.Column(
            "sales_channel",
            sa.String(length=32),
            server_default="lemon_squeezy",
            nullable=False,
        ),
    )
    op.add_column(
        "admin_market_offers",
        sa.Column(
            "billing_period",
            sa.String(length=16),
            server_default="monthly",
            nullable=False,
        ),
    )
    op.alter_column(
        "admin_market_offers",
        "amount",
        existing_type=sa.Numeric(18, 2),
        type_=sa.Numeric(18, 3),
        existing_nullable=False,
    )
    op.execute(
        """
        UPDATE admin_market_offers
        SET sales_channel = CASE
            WHEN currency = 'TND' THEN 'maestro_direct'
            ELSE 'lemon_squeezy'
        END
        """
    )
    op.create_check_constraint(
        op.f("ck_admin_market_offers_sales_channel_allowed"),
        "admin_market_offers",
        "sales_channel IN ('maestro_direct', 'lemon_squeezy')",
    )
    op.create_check_constraint(
        op.f("ck_admin_market_offers_billing_period_allowed"),
        "admin_market_offers",
        "billing_period IN ('monthly', 'annual')",
    )
    op.create_check_constraint(
        op.f("ck_admin_market_offers_direct_channel_requires_tnd"),
        "admin_market_offers",
        "sales_channel != 'maestro_direct' OR currency = 'TND'",
    )
    op.alter_column(
        "admin_market_offers",
        "sales_channel",
        server_default=None,
    )
    op.alter_column(
        "admin_market_offers",
        "billing_period",
        server_default=None,
    )

    op.add_column(
        "admin_market_channel_eligibilities",
        sa.Column(
            "address_status",
            sa.String(length=16),
            server_default="unverified",
            nullable=False,
        ),
    )
    op.add_column(
        "admin_market_channel_eligibilities",
        sa.Column("address_source", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "admin_market_channel_eligibilities",
        sa.Column(
            "address_verified_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.execute(
        """
        UPDATE admin_market_channel_eligibilities
        SET
            address_status = 'confirmed',
            address_source = 'trusted_eligibility_backfill_v1',
            address_verified_at = updated_at
        WHERE country_code = 'TN'
          AND maestro_direct_status = 'eligible'
          AND NOT admin_review_required
        """
    )
    op.create_check_constraint(
        op.f("ck_admin_market_channel_eligibilities_address_status_allowed"),
        "admin_market_channel_eligibilities",
        "address_status IN ('unverified', 'confirmed', 'revoked')",
    )
    op.create_check_constraint(
        op.f(
            "ck_admin_market_channel_eligibilities_"
            "confirmed_address_requires_evidence"
        ),
        "admin_market_channel_eligibilities",
        "address_status != 'confirmed' OR "
        "(country_code IS NOT NULL AND address_source IS NOT NULL "
        "AND address_verified_at IS NOT NULL)",
    )
    op.alter_column(
        "admin_market_channel_eligibilities",
        "address_status",
        server_default=None,
    )

    op.drop_constraint(
        op.f("ck_admin_market_orders_status_allowed"),
        "admin_market_orders",
        type_="check",
    )
    op.add_column(
        "admin_market_orders",
        sa.Column("plan_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "admin_market_orders",
        sa.Column(
            "billing_period",
            sa.String(length=16),
            server_default="monthly",
            nullable=False,
        ),
    )
    op.add_column(
        "admin_market_orders",
        sa.Column(
            "country_code",
            sa.String(length=2),
            server_default="TN",
            nullable=False,
        ),
    )
    op.add_column(
        "admin_market_orders",
        sa.Column(
            "currency",
            sa.String(length=3),
            server_default="TND",
            nullable=False,
        ),
    )
    for name in ("subtotal_amount", "tax_amount", "total_amount"):
        op.add_column(
            "admin_market_orders",
            sa.Column(
                name,
                sa.Numeric(18, 3),
                server_default="0.000",
                nullable=False,
            ),
        )
    op.add_column(
        "admin_market_orders",
        sa.Column(
            "contract_status",
            sa.String(length=24),
            server_default="pending",
            nullable=False,
        ),
    )
    op.add_column(
        "admin_market_orders",
        sa.Column(
            "payment_requirement",
            sa.String(length=24),
            server_default="required",
            nullable=False,
        ),
    )
    op.add_column(
        "admin_market_orders",
        sa.Column(
            "payment_status",
            sa.String(length=32),
            server_default="pending",
            nullable=False,
        ),
    )
    op.add_column(
        "admin_market_orders",
        sa.Column("payment_reference", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "admin_market_orders",
        sa.Column(
            "payment_destination_snapshot",
            sa.JSON(),
            server_default=sa.text("'{}'::json"),
            nullable=False,
        ),
    )
    op.add_column(
        "admin_market_orders",
        sa.Column(
            "offer_snapshot",
            sa.JSON(),
            server_default=sa.text("'{}'::json"),
            nullable=False,
        ),
    )
    op.add_column(
        "admin_market_orders",
        sa.Column(
            "creation_idempotency_key_hash",
            sa.String(length=64),
            nullable=True,
        ),
    )
    op.add_column(
        "admin_market_orders",
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "admin_market_orders",
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        """
        UPDATE admin_market_orders AS orders
        SET
            plan_id = offers.plan_id,
            currency = offers.currency,
            subtotal_amount = offers.amount,
            total_amount = offers.amount,
            payment_reference = 'TN-LEGACY-' || substr(md5(orders.order_ref), 1, 12),
            offer_snapshot = json_build_object(
                'offer_ref', offers.offer_code,
                'plan_ref', plans.plan_code,
                'display_name', offers.display_name,
                'billing_period', offers.billing_period,
                'currency', offers.currency,
                'amount', offers.amount::text,
                'sales_channel', offers.sales_channel,
                'snapshot_at', orders.created_at
            )
        FROM admin_market_offers AS offers
        JOIN admin_market_plans AS plans ON plans.id = offers.plan_id
        WHERE offers.id = orders.offer_id
        """
    )
    op.execute(
        """
        UPDATE admin_market_orders
        SET status = CASE status
            WHEN 'submitted' THEN 'awaiting_contract'
            WHEN 'awaiting_payment_verification' THEN 'awaiting_payment'
            WHEN 'approved' THEN 'ready_for_activation'
            WHEN 'rejected' THEN 'requires_review'
            WHEN 'fulfilled' THEN 'activated'
            ELSE status
        END
        """
    )
    op.alter_column("admin_market_orders", "plan_id", nullable=False)
    op.create_foreign_key(
        op.f("fk_admin_market_orders_plan_id_admin_market_plans"),
        "admin_market_orders",
        "admin_market_plans",
        ["plan_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        op.f("uq_admin_market_orders_creation_idem_hash"),
        "admin_market_orders",
        ["creation_idempotency_key_hash"],
    )
    op.create_unique_constraint(
        op.f("uq_admin_market_orders_payment_reference"),
        "admin_market_orders",
        ["payment_reference"],
    )
    op.create_check_constraint(
        op.f("ck_admin_market_orders_status_allowed"),
        "admin_market_orders",
        _ORDER_STATUS,
    )
    op.create_check_constraint(
        op.f("ck_admin_market_orders_billing_period_allowed"),
        "admin_market_orders",
        "billing_period IN ('monthly', 'annual')",
    )
    op.create_check_constraint(
        op.f("ck_admin_market_orders_direct_channel_country_tunisia"),
        "admin_market_orders",
        "selected_channel != 'maestro_direct' OR country_code = 'TN'",
    )
    op.create_check_constraint(
        op.f("ck_admin_market_orders_direct_channel_currency_tnd"),
        "admin_market_orders",
        "selected_channel != 'maestro_direct' OR currency = 'TND'",
    )
    op.create_check_constraint(
        op.f("ck_admin_market_orders_amounts_nonnegative"),
        "admin_market_orders",
        "subtotal_amount >= 0 AND tax_amount >= 0 AND total_amount >= 0",
    )
    op.create_check_constraint(
        op.f("ck_admin_market_orders_total_amount_consistent"),
        "admin_market_orders",
        "total_amount = subtotal_amount + tax_amount",
    )
    op.create_check_constraint(
        op.f("ck_admin_market_orders_contract_status_allowed"),
        "admin_market_orders",
        "contract_status IN ('not_required', 'pending', 'completed', 'rejected', 'expired')",
    )
    op.create_check_constraint(
        op.f("ck_admin_market_orders_payment_requirement_allowed"),
        "admin_market_orders",
        "payment_requirement IN ('required', 'not_required')",
    )
    op.create_check_constraint(
        op.f("ck_admin_market_orders_payment_status_allowed"),
        "admin_market_orders",
        "payment_status IN ('pending', 'customer_reported', "
        "'notification_received', 'matched', 'verified', "
        "'requires_review', 'rejected', 'not_required')",
    )
    for name in (
        "billing_period",
        "country_code",
        "currency",
        "subtotal_amount",
        "tax_amount",
        "total_amount",
        "contract_status",
        "payment_requirement",
        "payment_status",
        "payment_destination_snapshot",
        "offer_snapshot",
    ):
        op.alter_column("admin_market_orders", name, server_default=None)

    op.drop_constraint(
        op.f("ck_admin_market_audit_records_platform_authority_exact"),
        "admin_market_audit_records",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_admin_market_audit_records_action_allowed"),
        "admin_market_audit_records",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_admin_market_audit_records_actor_authority_allowed"),
        "admin_market_audit_records",
        "platform_authority IN ('platform_admin', 'identity_customer', 'system')",
    )
    op.create_check_constraint(
        op.f("ck_admin_market_audit_records_action_allowed"),
        "admin_market_audit_records",
        _AUDIT_ACTIONS,
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM admin_market_audit_records
                WHERE platform_authority != 'platform_admin'
                   OR action = 'order_created'
            ) THEN
                RAISE EXCEPTION
                    'Downgrade blocked: customer direct-order audit exists';
            END IF;
        END $$
        """
    )
    op.drop_constraint(
        op.f("ck_admin_market_audit_records_action_allowed"),
        "admin_market_audit_records",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_admin_market_audit_records_actor_authority_allowed"),
        "admin_market_audit_records",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_admin_market_audit_records_platform_authority_exact"),
        "admin_market_audit_records",
        "platform_authority = 'platform_admin'",
    )
    op.create_check_constraint(
        op.f("ck_admin_market_audit_records_action_allowed"),
        "admin_market_audit_records",
        _PREVIOUS_AUDIT_ACTIONS,
    )

    for constraint in (
        "ck_admin_market_orders_payment_status_allowed",
        "ck_admin_market_orders_payment_requirement_allowed",
        "ck_admin_market_orders_contract_status_allowed",
        "ck_admin_market_orders_total_amount_consistent",
        "ck_admin_market_orders_amounts_nonnegative",
        "ck_admin_market_orders_direct_channel_currency_tnd",
        "ck_admin_market_orders_direct_channel_country_tunisia",
        "ck_admin_market_orders_billing_period_allowed",
        "ck_admin_market_orders_status_allowed",
    ):
        op.drop_constraint(
            op.f(constraint),
            "admin_market_orders",
            type_="check",
        )
    op.execute(
        """
        UPDATE admin_market_orders
        SET status = CASE status
            WHEN 'awaiting_contract' THEN 'submitted'
            WHEN 'awaiting_payment' THEN 'awaiting_payment_verification'
            WHEN 'payment_under_review' THEN 'awaiting_payment_verification'
            WHEN 'ready_for_activation' THEN 'approved'
            WHEN 'activated' THEN 'fulfilled'
            WHEN 'requires_review' THEN 'rejected'
            WHEN 'expired' THEN 'cancelled'
            ELSE status
        END
        """
    )
    op.create_check_constraint(
        op.f("ck_admin_market_orders_status_allowed"),
        "admin_market_orders",
        _PREVIOUS_ORDER_STATUS,
    )
    op.drop_constraint(
        op.f("uq_admin_market_orders_payment_reference"),
        "admin_market_orders",
        type_="unique",
    )
    op.drop_constraint(
        op.f("uq_admin_market_orders_creation_idem_hash"),
        "admin_market_orders",
        type_="unique",
    )
    op.drop_constraint(
        op.f("fk_admin_market_orders_plan_id_admin_market_plans"),
        "admin_market_orders",
        type_="foreignkey",
    )
    for name in (
        "cancelled_at",
        "completed_at",
        "creation_idempotency_key_hash",
        "offer_snapshot",
        "payment_destination_snapshot",
        "payment_reference",
        "payment_status",
        "payment_requirement",
        "contract_status",
        "total_amount",
        "tax_amount",
        "subtotal_amount",
        "currency",
        "country_code",
        "billing_period",
        "plan_id",
    ):
        op.drop_column("admin_market_orders", name)

    op.drop_constraint(
        op.f(
            "ck_admin_market_channel_eligibilities_"
            "confirmed_address_requires_evidence"
        ),
        "admin_market_channel_eligibilities",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_admin_market_channel_eligibilities_address_status_allowed"),
        "admin_market_channel_eligibilities",
        type_="check",
    )
    op.drop_column(
        "admin_market_channel_eligibilities",
        "address_verified_at",
    )
    op.drop_column("admin_market_channel_eligibilities", "address_source")
    op.drop_column("admin_market_channel_eligibilities", "address_status")

    op.drop_constraint(
        op.f("ck_admin_market_offers_direct_channel_requires_tnd"),
        "admin_market_offers",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_admin_market_offers_billing_period_allowed"),
        "admin_market_offers",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_admin_market_offers_sales_channel_allowed"),
        "admin_market_offers",
        type_="check",
    )
    op.alter_column(
        "admin_market_offers",
        "amount",
        existing_type=sa.Numeric(18, 3),
        type_=sa.Numeric(18, 2),
        existing_nullable=False,
    )
    op.drop_column("admin_market_offers", "billing_period")
    op.drop_column("admin_market_offers", "sales_channel")
