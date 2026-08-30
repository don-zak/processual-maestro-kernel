"""Reconcile superseded marketplace CHECK constraints with current authority.

Revision ID: 20260830_0047
Revises: 20260809_0046
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "20260830_0047"
down_revision: str | None = "20260809_0046"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AUDIT_TABLE = "admin_market_audit_records"
ORDER_TABLE = "admin_market_orders"


def _normalized(value: object) -> str:
    return " ".join(str(value or "").lower().split())


def _is_stale_audit_check(sqltext: object) -> bool:
    text = _normalized(sqltext)
    platform_admin_only = (
        "platform_authority" in text
        and "platform_admin" in text
        and "identity_customer" not in text
        and "system" not in text
    )
    pre_order_action_vocabulary = (
        "action" in text
        and "authority_checked" in text
        and "payment_destination_default_set" in text
        and "order_created" not in text
    )
    pre_contract_resource_vocabulary = (
        "resource_type" in text
        and "sales_channel_eligibility" in text
        and "payment_destination" in text
        and "contract" not in text
        and "payment_evidence" not in text
        and "payment_reconciliation" not in text
    )
    return (
        platform_admin_only
        or pre_order_action_vocabulary
        or pre_contract_resource_vocabulary
    )


def _is_stale_order_status_check(sqltext: object) -> bool:
    text = _normalized(sqltext)
    return (
        "status" in text
        and "submitted" in text
        and "awaiting_payment_verification" in text
        and "fulfilled" in text
        and "awaiting_contract" not in text
        and "activated" not in text
    )


def _drop_stale_online() -> None:
    inspector = sa.inspect(op.get_bind())
    targets: list[tuple[str, str]] = []
    for row in inspector.get_check_constraints(AUDIT_TABLE):
        name = row.get("name")
        if name and _is_stale_audit_check(row.get("sqltext")):
            targets.append((AUDIT_TABLE, str(name)))
    for row in inspector.get_check_constraints(ORDER_TABLE):
        name = row.get("name")
        if name and _is_stale_order_status_check(row.get("sqltext")):
            targets.append((ORDER_TABLE, str(name)))

    # The names above are already the dialect-rendered identifiers reflected
    # from the live database. Mark them as finalized with op.f() so Alembic's
    # naming convention does not prefix/truncate them a second time.
    for table_name, constraint_name in targets:
        with op.batch_alter_table(table_name) as batch:
            batch.drop_constraint(op.f(constraint_name), type_="check")


def _drop_stale_postgresql_offline() -> None:
    # Offline SQL cannot use Inspector. Ask PostgreSQL itself to locate only the
    # superseded definitions, keeping the emitted migration executable rather
    # than guessing naming-convention/truncation results.
    op.execute(
        sa.text(
            r"""
DO $$
DECLARE r record;
BEGIN
  FOR r IN
    SELECT c.conname, t.relname
    FROM pg_constraint c
    JOIN pg_class t ON t.oid = c.conrelid
    WHERE c.contype = 'c'
      AND t.relname IN ('admin_market_audit_records', 'admin_market_orders')
      AND (
        (
          t.relname = 'admin_market_audit_records'
          AND (
            (pg_get_constraintdef(c.oid) ILIKE '%platform_authority%platform_admin%'
             AND pg_get_constraintdef(c.oid) NOT ILIKE '%identity_customer%'
             AND pg_get_constraintdef(c.oid) NOT ILIKE '%system%')
            OR
            (pg_get_constraintdef(c.oid) ILIKE '%authority_checked%payment_destination_default_set%'
             AND pg_get_constraintdef(c.oid) NOT ILIKE '%order_created%')
            OR
            (pg_get_constraintdef(c.oid) ILIKE '%sales_channel_eligibility%payment_destination%'
             AND pg_get_constraintdef(c.oid) NOT ILIKE '%contract%'
             AND pg_get_constraintdef(c.oid) NOT ILIKE '%payment_evidence%'
             AND pg_get_constraintdef(c.oid) NOT ILIKE '%payment_reconciliation%')
          )
        )
        OR
        (
          t.relname = 'admin_market_orders'
          AND pg_get_constraintdef(c.oid) ILIKE '%submitted%awaiting_payment_verification%fulfilled%'
          AND pg_get_constraintdef(c.oid) NOT ILIKE '%awaiting_contract%'
          AND pg_get_constraintdef(c.oid) NOT ILIKE '%activated%'
        )
      )
  LOOP
    EXECUTE format('ALTER TABLE %I DROP CONSTRAINT %I', r.relname, r.conname);
  END LOOP;
END $$;
"""
        )
    )


def upgrade() -> None:
    if context.is_offline_mode():
        _drop_stale_postgresql_offline()
        return
    _drop_stale_online()


def _assert_downgrade_safe() -> None:
    bind = op.get_bind()
    incompatible_audit = bind.execute(
        sa.text(
            f"SELECT 1 FROM {AUDIT_TABLE} WHERE "
            "platform_authority != 'platform_admin' "
            "OR action = 'order_created' "
            "OR resource_type IN ('contract','payment_evidence','payment_reconciliation') "
            "LIMIT 1"
        )
    ).first()
    incompatible_order = bind.execute(
        sa.text(
            f"SELECT 1 FROM {ORDER_TABLE} WHERE status NOT IN ("
            "'draft','submitted','awaiting_payment_verification','approved',"
            "'rejected','cancelled','fulfilled') LIMIT 1"
        )
    ).first()
    if incompatible_audit or incompatible_order:
        raise RuntimeError(
            "Downgrade blocked: rows require the reconciled marketplace CHECK vocabulary"
        )


def downgrade() -> None:
    if not context.is_offline_mode():
        _assert_downgrade_safe()

    with op.batch_alter_table(AUDIT_TABLE) as batch:
        batch.create_check_constraint(
            op.f("ck_admin_market_audit_records_platform_authority_exact"),
            "platform_authority = 'platform_admin'",
        )
        batch.create_check_constraint(
            op.f("ck_admin_market_audit_records_action_allowed"),
            "action IN ('authority_checked','offer_decided','channel_eligibility_decided',"
            "'channel_selected','payment_verification_decided',"
            "'subscription_activation_decided','payment_destination_created',"
            "'payment_destination_validated','payment_destination_activated',"
            "'payment_destination_deactivated','payment_destination_default_set')",
        )
        batch.create_check_constraint(
            op.f("ck_admin_market_audit_records_resource_type_allowed"),
            "resource_type IN ('offer','plan','order','payment_verification',"
            "'subscription','trial','sales_channel_eligibility','payment_destination')",
        )

    with op.batch_alter_table(ORDER_TABLE) as batch:
        batch.create_check_constraint(
            op.f("ck_admin_market_orders_status_allowed"),
            "status IN ('draft','submitted','awaiting_payment_verification','approved',"
            "'rejected','cancelled','fulfilled')",
        )
