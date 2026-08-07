"""Add top-up quota units and immutable grant ledger.

Revision ID: 20260807_0039
Revises: 20260806_0038
Create Date: 2026-08-07
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260807_0039"
down_revision: str | None = "20260806_0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CYCLE_TABLE = "admin_market_subscription_quota_cycles"
GRANT_TABLE = "admin_market_subscription_top_up_grants"
CATALOG_VERSION = "2026-08-plan-fulfillment-v1"

_ENTITLEMENTS_BY_PLAN = {
    "academic": '["maestro_execution","byok_provider_connection","standard_support","academic_use"]',
    "starter": '["maestro_execution","byok_provider_connection","standard_support"]',
    "enterprise_integration_starter": '["maestro_execution","byok_provider_connection","business_support","advanced_integration","enterprise_governance"]',
    "business": '["maestro_execution","byok_provider_connection","business_support"]',
    "enterprise_pilot": '["maestro_execution","byok_provider_connection","business_support","enterprise_governance"]',
    "enterprise_core": '["maestro_execution","byok_provider_connection","business_support","enterprise_governance"]',
    "enterprise_scale": '["maestro_execution","byok_provider_connection","business_support","enterprise_governance","advanced_integration"]',
    "enterprise_strategic": '["maestro_execution","byok_provider_connection","business_support","enterprise_governance","advanced_integration"]',
}


def upgrade() -> None:
    with op.batch_alter_table(CYCLE_TABLE) as batch:
        batch.add_column(
            sa.Column(
                "top_up_units",
                sa.BigInteger(),
                nullable=False,
                server_default="0",
            )
        )
        batch.drop_constraint("usage_within_available", type_="check")
        batch.create_check_constraint(
            "usage_within_available",
            "used_units >= 0 AND used_units <= base_limit_units + rollover_units + top_up_units",
        )
        batch.create_check_constraint("top_up_nonnegative", "top_up_units >= 0")

    connection = op.get_bind()
    for plan_code, entitlements_json in _ENTITLEMENTS_BY_PLAN.items():
        connection.execute(
            sa.text(
                f"""
                UPDATE {CYCLE_TABLE}
                SET entitlement_codes = :entitlements,
                    plan_catalog_version = :version
                WHERE plan_code = :plan_code
                  AND (
                      entitlement_codes IS NULL
                      OR entitlement_codes = '[]'
                      OR entitlement_codes = 'null'
                  )
                """
            ),
            {
                "entitlements": entitlements_json,
                "version": CATALOG_VERSION,
                "plan_code": plan_code,
            },
        )

    unresolved = connection.execute(
        sa.text(
            f"""
            SELECT plan_code
            FROM {CYCLE_TABLE}
            WHERE entitlement_codes IS NULL
               OR entitlement_codes = '[]'
               OR entitlement_codes = 'null'
            LIMIT 1
            """
        )
    ).first()
    if unresolved:
        raise RuntimeError(
            "Top-up migration found quota cycles without authoritative entitlements"
        )

    op.create_table(
        GRANT_TABLE,
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "order_id",
            sa.Uuid(),
            sa.ForeignKey("commercial_top_up_orders.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "subscription_id",
            sa.Uuid(),
            sa.ForeignKey("admin_market_subscriptions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "quota_cycle_id",
            sa.Uuid(),
            sa.ForeignKey(
                "admin_market_subscription_quota_cycles.id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column("customer_ref", sa.String(128), nullable=False),
        sa.Column("plan_code", sa.String(128), nullable=False),
        sa.Column("plan_catalog_version", sa.String(64), nullable=False),
        sa.Column("units", sa.BigInteger(), nullable=False),
        sa.Column("grant_idempotency_key", sa.String(500), nullable=False),
        sa.Column("provider_reference", sa.String(255), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("units > 0", name="units_positive"),
        sa.CheckConstraint("expires_at > granted_at", name="expiry_after_grant"),
        sa.UniqueConstraint("order_id", name="uq_admin_market_top_up_grant_order"),
        sa.UniqueConstraint(
            "grant_idempotency_key",
            name="uq_admin_market_top_up_grant_idempotency",
        ),
    )
    op.create_index(
        "ix_admin_market_top_up_grant_subscription_cycle",
        GRANT_TABLE,
        ["subscription_id", "quota_cycle_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_admin_market_top_up_grant_subscription_cycle",
        table_name=GRANT_TABLE,
    )
    op.drop_table(GRANT_TABLE)

    with op.batch_alter_table(CYCLE_TABLE) as batch:
        batch.drop_constraint("top_up_nonnegative", type_="check")
        batch.drop_constraint("usage_within_available", type_="check")
        batch.create_check_constraint(
            "usage_within_available",
            "used_units >= 0 AND used_units <= base_limit_units + rollover_units",
        )
        batch.drop_column("top_up_units")
