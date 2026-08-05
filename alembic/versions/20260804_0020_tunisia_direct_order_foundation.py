"""Add trusted Tunisia payment choice and direct order foundation.

Revision ID: 20260804_0020
Revises: 20260804_0019
Create Date: 2026-08-04
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260804_0020"
down_revision: str | None = "20260804_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_AUDIT_ACTIONS = """action IN (
'authority_checked','offer_decided','channel_eligibility_decided',
'channel_selected','payment_verification_decided',
'subscription_activation_decided','payment_destination_created',
'payment_destination_validated','payment_destination_activated',
'payment_destination_deactivated','payment_destination_default_set',
'order_created')"""
_PREVIOUS_AUDIT_ACTIONS = """action IN (
'authority_checked','offer_decided','channel_eligibility_decided',
'channel_selected','payment_verification_decided',
'subscription_activation_decided','payment_destination_created',
'payment_destination_validated','payment_destination_activated',
'payment_destination_deactivated','payment_destination_default_set')"""
_ORDER_STATUS = """status IN (
'draft','awaiting_contract','awaiting_payment','payment_under_review',
'ready_for_activation','activated','cancelled','expired','requires_review')"""
_PREVIOUS_ORDER_STATUS = """status IN (
'draft','submitted','awaiting_payment_verification','approved','rejected',
'cancelled','fulfilled')"""


def _backfill_orders() -> None:
    bind = op.get_bind()
    orders = sa.table(
        "admin_market_orders",
        sa.column("id"), sa.column("order_ref"), sa.column("offer_id"),
        sa.column("created_at"), sa.column("plan_id"), sa.column("currency"),
        sa.column("subtotal_amount"), sa.column("total_amount"),
        sa.column("payment_reference"), sa.column("offer_snapshot", sa.JSON()),
    )
    offers = sa.table(
        "admin_market_offers",
        sa.column("id"), sa.column("plan_id"), sa.column("offer_code"),
        sa.column("display_name"), sa.column("billing_period"),
        sa.column("currency"), sa.column("amount"), sa.column("sales_channel"),
    )
    plans = sa.table("admin_market_plans", sa.column("id"), sa.column("plan_code"))
    rows = bind.execute(
        sa.select(
            orders.c.id, orders.c.order_ref, orders.c.created_at,
            offers.c.plan_id, offers.c.offer_code, offers.c.display_name,
            offers.c.billing_period, offers.c.currency, offers.c.amount,
            offers.c.sales_channel, plans.c.plan_code,
        ).select_from(
            orders.join(offers, offers.c.id == orders.c.offer_id).join(
                plans, plans.c.id == offers.c.plan_id
            )
        )
    ).mappings()
    for row in rows:
        digest = hashlib.sha256(str(row["order_ref"]).encode("utf-8")).hexdigest()[:12]
        snapshot = {
            "offer_ref": row["offer_code"],
            "plan_ref": row["plan_code"],
            "display_name": row["display_name"],
            "billing_period": row["billing_period"],
            "currency": row["currency"],
            "amount": str(row["amount"]),
            "sales_channel": row["sales_channel"],
            "snapshot_at": row["created_at"].isoformat()
            if hasattr(row["created_at"], "isoformat") else str(row["created_at"]),
        }
        bind.execute(
            orders.update().where(orders.c.id == row["id"]).values(
                plan_id=row["plan_id"], currency=row["currency"],
                subtotal_amount=row["amount"], total_amount=row["amount"],
                payment_reference=f"TN-LEGACY-{digest}", offer_snapshot=snapshot,
            )
        )


def _assert_downgrade_safe() -> None:
    bind = op.get_bind()
    row = bind.execute(sa.text(
        "SELECT 1 FROM admin_market_audit_records "
        "WHERE platform_authority != 'platform_admin' OR action = 'order_created' LIMIT 1"
    )).first()
    if row:
        raise RuntimeError("Downgrade blocked: customer direct-order audit exists")


def upgrade() -> None:
    with op.batch_alter_table("admin_market_offers") as batch_op:
        batch_op.add_column(sa.Column("sales_channel", sa.String(32), server_default="lemon_squeezy", nullable=False))
        batch_op.add_column(sa.Column("billing_period", sa.String(16), server_default="monthly", nullable=False))
        batch_op.alter_column("amount", existing_type=sa.Numeric(18, 2), type_=sa.Numeric(18, 3), existing_nullable=False)
    op.execute("UPDATE admin_market_offers SET sales_channel = CASE WHEN currency = 'TND' THEN 'maestro_direct' ELSE 'lemon_squeezy' END")
    with op.batch_alter_table("admin_market_offers") as batch_op:
        batch_op.create_check_constraint(op.f("ck_admin_market_offers_sales_channel_allowed"), "sales_channel IN ('maestro_direct','lemon_squeezy')")
        batch_op.create_check_constraint(op.f("ck_admin_market_offers_billing_period_allowed"), "billing_period IN ('monthly','annual')")
        batch_op.create_check_constraint(op.f("ck_admin_market_offers_direct_channel_requires_tnd"), "sales_channel != 'maestro_direct' OR currency = 'TND'")
        batch_op.alter_column("sales_channel", server_default=None)
        batch_op.alter_column("billing_period", server_default=None)

    with op.batch_alter_table("admin_market_channel_eligibilities") as batch_op:
        batch_op.add_column(sa.Column("address_status", sa.String(16), server_default="unverified", nullable=False))
        batch_op.add_column(sa.Column("address_source", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("address_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("""UPDATE admin_market_channel_eligibilities SET address_status='confirmed', address_source='trusted_eligibility_backfill_v1', address_verified_at=updated_at WHERE country_code='TN' AND maestro_direct_status='eligible' AND NOT admin_review_required""")
    with op.batch_alter_table("admin_market_channel_eligibilities") as batch_op:
        batch_op.create_check_constraint(op.f("ck_admin_market_channel_eligibilities_address_status_allowed"), "address_status IN ('unverified','confirmed','revoked')")
        batch_op.create_check_constraint(op.f("ck_admin_market_channel_eligibilities_confirmed_address_requires_evidence"), "address_status != 'confirmed' OR (country_code IS NOT NULL AND address_source IS NOT NULL AND address_verified_at IS NOT NULL)")
        batch_op.alter_column("address_status", server_default=None)

    with op.batch_alter_table("admin_market_orders") as batch_op:
        batch_op.add_column(sa.Column("plan_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("billing_period", sa.String(16), server_default="monthly", nullable=False))
        batch_op.add_column(sa.Column("country_code", sa.String(2), server_default="TN", nullable=False))
        batch_op.add_column(sa.Column("currency", sa.String(3), server_default="TND", nullable=False))
        for name in ("subtotal_amount", "tax_amount", "total_amount"):
            batch_op.add_column(sa.Column(name, sa.Numeric(18, 3), server_default="0.000", nullable=False))
        batch_op.add_column(sa.Column("contract_status", sa.String(24), server_default="pending", nullable=False))
        batch_op.add_column(sa.Column("payment_requirement", sa.String(24), server_default="required", nullable=False))
        batch_op.add_column(sa.Column("payment_status", sa.String(32), server_default="pending", nullable=False))
        batch_op.add_column(sa.Column("payment_reference", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("payment_destination_snapshot", sa.JSON(), server_default=sa.text("'{}'"), nullable=False))
        batch_op.add_column(sa.Column("offer_snapshot", sa.JSON(), server_default=sa.text("'{}'"), nullable=False))
        batch_op.add_column(sa.Column("creation_idempotency_key_hash", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
    _backfill_orders()
    op.execute("""UPDATE admin_market_orders SET status = CASE status WHEN 'submitted' THEN 'awaiting_contract' WHEN 'awaiting_payment_verification' THEN 'awaiting_payment' WHEN 'approved' THEN 'ready_for_activation' WHEN 'rejected' THEN 'requires_review' WHEN 'fulfilled' THEN 'activated' ELSE status END""")
    with op.batch_alter_table("admin_market_orders") as batch_op:
        batch_op.alter_column("plan_id", nullable=False)
        batch_op.create_foreign_key(op.f("fk_admin_market_orders_plan_id_admin_market_plans"), "admin_market_plans", ["plan_id"], ["id"], ondelete="RESTRICT")
        batch_op.create_unique_constraint(op.f("uq_admin_market_orders_creation_idem_hash"), ["creation_idempotency_key_hash"])
        batch_op.create_unique_constraint(op.f("uq_admin_market_orders_payment_reference"), ["payment_reference"])
        checks = {
            "ck_admin_market_orders_status_allowed": _ORDER_STATUS,
            "ck_admin_market_orders_billing_period_allowed": "billing_period IN ('monthly','annual')",
            "ck_admin_market_orders_direct_channel_country_tunisia": "selected_channel != 'maestro_direct' OR country_code = 'TN'",
            "ck_admin_market_orders_direct_channel_currency_tnd": "selected_channel != 'maestro_direct' OR currency = 'TND'",
            "ck_admin_market_orders_amounts_nonnegative": "subtotal_amount >= 0 AND tax_amount >= 0 AND total_amount >= 0",
            "ck_admin_market_orders_total_amount_consistent": "total_amount = subtotal_amount + tax_amount",
            "ck_admin_market_orders_contract_status_allowed": "contract_status IN ('not_required','pending','completed','rejected','expired')",
            "ck_admin_market_orders_payment_requirement_allowed": "payment_requirement IN ('required','not_required')",
            "ck_admin_market_orders_payment_status_allowed": "payment_status IN ('pending','customer_reported','notification_received','matched','verified','requires_review','rejected','not_required')",
        }
        for name, expression in checks.items():
            batch_op.create_check_constraint(op.f(name), expression)
        for name in ("billing_period","country_code","currency","subtotal_amount","tax_amount","total_amount","contract_status","payment_requirement","payment_status","payment_destination_snapshot","offer_snapshot"):
            batch_op.alter_column(name, server_default=None)

    with op.batch_alter_table("admin_market_audit_records") as batch_op:
        batch_op.drop_constraint(op.f("ck_admin_market_audit_records_platform_authority_exact"), type_="check")
        batch_op.drop_constraint(op.f("ck_admin_market_audit_records_action_allowed"), type_="check")
        batch_op.create_check_constraint(op.f("ck_admin_market_audit_records_actor_authority_allowed"), "platform_authority IN ('platform_admin','identity_customer','system')")
        batch_op.create_check_constraint(op.f("ck_admin_market_audit_records_action_allowed"), _AUDIT_ACTIONS)


def downgrade() -> None:
    _assert_downgrade_safe()
    with op.batch_alter_table("admin_market_audit_records") as batch_op:
        batch_op.drop_constraint(op.f("ck_admin_market_audit_records_action_allowed"), type_="check")
        batch_op.drop_constraint(op.f("ck_admin_market_audit_records_actor_authority_allowed"), type_="check")
        batch_op.create_check_constraint(op.f("ck_admin_market_audit_records_platform_authority_exact"), "platform_authority = 'platform_admin'")
        batch_op.create_check_constraint(op.f("ck_admin_market_audit_records_action_allowed"), _PREVIOUS_AUDIT_ACTIONS)

    with op.batch_alter_table("admin_market_orders") as batch_op:
        for name in ("ck_admin_market_orders_payment_status_allowed","ck_admin_market_orders_payment_requirement_allowed","ck_admin_market_orders_contract_status_allowed","ck_admin_market_orders_total_amount_consistent","ck_admin_market_orders_amounts_nonnegative","ck_admin_market_orders_direct_channel_currency_tnd","ck_admin_market_orders_direct_channel_country_tunisia","ck_admin_market_orders_billing_period_allowed","ck_admin_market_orders_status_allowed"):
            batch_op.drop_constraint(op.f(name), type_="check")
    op.execute("""UPDATE admin_market_orders SET status = CASE status WHEN 'awaiting_contract' THEN 'submitted' WHEN 'awaiting_payment' THEN 'awaiting_payment_verification' WHEN 'payment_under_review' THEN 'awaiting_payment_verification' WHEN 'ready_for_activation' THEN 'approved' WHEN 'activated' THEN 'fulfilled' WHEN 'requires_review' THEN 'rejected' WHEN 'expired' THEN 'cancelled' ELSE status END""")
    with op.batch_alter_table("admin_market_orders") as batch_op:
        batch_op.create_check_constraint(op.f("ck_admin_market_orders_status_allowed"), _PREVIOUS_ORDER_STATUS)
        batch_op.drop_constraint(op.f("uq_admin_market_orders_payment_reference"), type_="unique")
        batch_op.drop_constraint(op.f("uq_admin_market_orders_creation_idem_hash"), type_="unique")
        batch_op.drop_constraint(op.f("fk_admin_market_orders_plan_id_admin_market_plans"), type_="foreignkey")
        for name in ("cancelled_at","completed_at","creation_idempotency_key_hash","offer_snapshot","payment_destination_snapshot","payment_reference","payment_status","payment_requirement","contract_status","total_amount","tax_amount","subtotal_amount","currency","country_code","billing_period","plan_id"):
            batch_op.drop_column(name)

    with op.batch_alter_table("admin_market_channel_eligibilities") as batch_op:
        batch_op.drop_constraint(op.f("ck_admin_market_channel_eligibilities_confirmed_address_requires_evidence"), type_="check")
        batch_op.drop_constraint(op.f("ck_admin_market_channel_eligibilities_address_status_allowed"), type_="check")
        batch_op.drop_column("address_verified_at")
        batch_op.drop_column("address_source")
        batch_op.drop_column("address_status")

    with op.batch_alter_table("admin_market_offers") as batch_op:
        batch_op.drop_constraint(op.f("ck_admin_market_offers_direct_channel_requires_tnd"), type_="check")
        batch_op.drop_constraint(op.f("ck_admin_market_offers_billing_period_allowed"), type_="check")
        batch_op.drop_constraint(op.f("ck_admin_market_offers_sales_channel_allowed"), type_="check")
        batch_op.alter_column("amount", existing_type=sa.Numeric(18, 3), type_=sa.Numeric(18, 2), existing_nullable=False)
        batch_op.drop_column("billing_period")
        batch_op.drop_column("sales_channel")
