"""Retire legacy subscription quota accounts and usage ledger safely.

Revision ID: 20260822_0060
Revises: 20260822_0059
Create Date: 2026-08-22
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "20260822_0060"
down_revision: str | None = "20260822_0059"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RUNTIME = "admin_market_subscription_runtime"
LEGACY_QUOTAS = "admin_market_subscription_quota_accounts"
LEGACY_USAGE = "admin_market_subscription_usage_ledger"
CYCLES = "admin_market_subscription_quota_cycles"
CYCLE_USAGE = "admin_market_subscription_quota_cycle_usage"

PLAN_CATALOG_VERSION = "2026-08-plan-fulfillment-v2"
CANONICAL_METRIC = "maestro_units"

_CATALOG: dict[str, tuple[int, tuple[str, ...]]] = {
    "academic": (
        5_000,
        (
            "maestro_execution",
            "byok_provider_connection",
            "standard_support",
            "academic_use",
        ),
    ),
    "starter": (
        10_000,
        (
            "maestro_execution",
            "byok_provider_connection",
            "standard_support",
        ),
    ),
    "enterprise_integration_starter": (
        50_000,
        (
            "maestro_execution",
            "byok_provider_connection",
            "business_support",
            "advanced_integration",
            "enterprise_governance",
        ),
    ),
    "business": (
        100_000,
        (
            "maestro_execution",
            "byok_provider_connection",
            "business_support",
        ),
    ),
    "enterprise_pilot": (
        500_000,
        (
            "maestro_execution",
            "byok_provider_connection",
            "business_support",
            "enterprise_governance",
        ),
    ),
    "enterprise_core": (
        1_500_000,
        (
            "maestro_execution",
            "byok_provider_connection",
            "business_support",
            "enterprise_governance",
        ),
    ),
    "enterprise_scale": (
        3_000_000,
        (
            "maestro_execution",
            "byok_provider_connection",
            "business_support",
            "enterprise_governance",
            "advanced_integration",
        ),
    ),
    "enterprise_strategic": (
        5_000_000,
        (
            "maestro_execution",
            "byok_provider_connection",
            "business_support",
            "enterprise_governance",
            "advanced_integration",
        ),
    ),
}


def _canonical_metric(value: object) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"credits", CANONICAL_METRIC}:
        return CANONICAL_METRIC
    return normalized


def _table(name: str, *columns: sa.Column) -> sa.Table:
    return sa.table(name, *columns)


def _tables() -> dict[str, sa.Table]:
    return {
        "quota": _table(
            LEGACY_QUOTAS,
            sa.column("id", sa.Uuid()),
            sa.column("subscription_id", sa.Uuid()),
            sa.column("customer_ref", sa.String()),
            sa.column("quota_profile_ref", sa.String()),
            sa.column("metric_code", sa.String()),
            sa.column("period_start", sa.DateTime(timezone=True)),
            sa.column("period_end", sa.DateTime(timezone=True)),
            sa.column("limit_units", sa.BigInteger()),
            sa.column("used_units", sa.BigInteger()),
            sa.column("version", sa.Integer()),
        ),
        "usage": _table(
            LEGACY_USAGE,
            sa.column("id", sa.Uuid()),
            sa.column("quota_account_id", sa.Uuid()),
            sa.column("subscription_id", sa.Uuid()),
            sa.column("customer_ref", sa.String()),
            sa.column("metric_code", sa.String()),
            sa.column("units", sa.BigInteger()),
            sa.column("idempotency_key_hash", sa.String()),
            sa.column("dimensions_digest", sa.String()),
            sa.column("occurred_at", sa.DateTime(timezone=True)),
            sa.column("recorded_at", sa.DateTime(timezone=True)),
        ),
        "subscription": _table(
            "admin_market_subscriptions",
            sa.column("id", sa.Uuid()),
            sa.column("customer_ref", sa.String()),
            sa.column("plan_id", sa.Uuid()),
        ),
        "plan": _table(
            "admin_market_plans",
            sa.column("id", sa.Uuid()),
            sa.column("plan_code", sa.String()),
            sa.column("quota_profile_ref", sa.String()),
        ),
        "binding": _table(
            "admin_market_assessment_subscription_bindings",
            sa.column("subscription_id", sa.Uuid()),
            sa.column("customer_ref", sa.String()),
            sa.column("entitlement_plan_id", sa.Uuid()),
            sa.column("entitlement_source_plan_code", sa.String()),
            sa.column("quota_profile_ref", sa.String()),
        ),
        "profile": _table(
            "admin_market_assessment_quota_profiles",
            sa.column("profile_ref", sa.String()),
            sa.column("customer_ref", sa.String()),
            sa.column("metric_code", sa.String()),
            sa.column("limit_units", sa.BigInteger()),
            sa.column("definition_version", sa.String()),
            sa.column("entitlement_codes_json", sa.JSON()),
        ),
        "cycle": _table(
            CYCLES,
            sa.column("id", sa.Uuid()),
            sa.column("subscription_id", sa.Uuid()),
            sa.column("source_cycle_id", sa.Uuid()),
            sa.column("customer_ref", sa.String()),
            sa.column("plan_code", sa.String()),
            sa.column("plan_catalog_version", sa.String()),
            sa.column("entitlement_codes", sa.JSON()),
            sa.column("quota_profile_ref", sa.String()),
            sa.column("metric_code", sa.String()),
            sa.column("period_start", sa.DateTime(timezone=True)),
            sa.column("period_end", sa.DateTime(timezone=True)),
            sa.column("base_limit_units", sa.BigInteger()),
            sa.column("rollover_units", sa.BigInteger()),
            sa.column("top_up_units", sa.BigInteger()),
            sa.column("rollover_status", sa.String()),
            sa.column("used_units", sa.BigInteger()),
            sa.column("version", sa.BigInteger()),
        ),
        "cycle_usage": _table(
            CYCLE_USAGE,
            sa.column("id", sa.Uuid()),
            sa.column("quota_cycle_id", sa.Uuid()),
            sa.column("subscription_id", sa.Uuid()),
            sa.column("customer_ref", sa.String()),
            sa.column("metric_code", sa.String()),
            sa.column("units", sa.BigInteger()),
            sa.column("idempotency_key_hash", sa.String()),
            sa.column("dimensions_digest", sa.String()),
            sa.column("occurred_at", sa.DateTime(timezone=True)),
            sa.column("recorded_at", sa.DateTime(timezone=True)),
        ),
    }


def _one(connection, statement, error: str):
    row = connection.execute(statement).mappings().first()
    if row is None:
        raise RuntimeError(error)
    return row


def _authority(connection, tables, account, subscription, plan):
    binding = connection.execute(
        sa.select(tables["binding"]).where(
            tables["binding"].c.subscription_id == subscription["id"]
        )
    ).mappings().first()
    metric = _canonical_metric(account["metric_code"])

    if binding is not None:
        profile = _one(
            connection,
            sa.select(tables["profile"]).where(
                tables["profile"].c.profile_ref == binding["quota_profile_ref"]
            ),
            "Legacy quota retirement blocked: assessment quota profile is missing.",
        )
        if (
            binding["customer_ref"] != subscription["customer_ref"]
            or binding["entitlement_plan_id"] != subscription["plan_id"]
            or str(binding["entitlement_source_plan_code"]).strip().lower()
            != str(plan["plan_code"]).strip().lower()
            or profile["customer_ref"] != subscription["customer_ref"]
            or account["customer_ref"] != subscription["customer_ref"]
            or account["quota_profile_ref"] != profile["profile_ref"]
            or metric != _canonical_metric(profile["metric_code"])
            or account["limit_units"] != profile["limit_units"]
        ):
            raise RuntimeError(
                "Legacy quota retirement blocked: assessment authority conflicts with legacy quota state."
            )
        return (
            str(binding["entitlement_source_plan_code"]).strip().lower(),
            str(profile["definition_version"]),
            tuple(profile["entitlement_codes_json"] or ()),
            str(profile["profile_ref"]),
            metric,
            int(profile["limit_units"]),
        )

    plan_code = str(plan["plan_code"]).strip().lower()
    spec = _CATALOG.get(plan_code)
    if spec is None:
        raise RuntimeError(
            "Legacy quota retirement blocked: subscription plan is outside the retirement catalog snapshot."
        )
    limit_units, entitlements = spec
    if (
        metric != CANONICAL_METRIC
        or account["customer_ref"] != subscription["customer_ref"]
        or str(account["quota_profile_ref"]).strip().lower()
        != str(plan["quota_profile_ref"]).strip().lower()
        or account["limit_units"] != limit_units
    ):
        raise RuntimeError(
            "Legacy quota retirement blocked: catalog authority conflicts with legacy quota state."
        )
    return (
        plan_code,
        PLAN_CATALOG_VERSION,
        entitlements,
        str(account["quota_profile_ref"]).strip().lower(),
        metric,
        limit_units,
    )


def _assert_cycle(cycle, account, authority) -> None:
    plan_code, version, entitlements, quota_profile_ref, metric, limit_units = authority
    if (
        cycle["subscription_id"] != account["subscription_id"]
        or cycle["customer_ref"] != account["customer_ref"]
        or str(cycle["plan_code"]).strip().lower() != plan_code
        or cycle["plan_catalog_version"] != version
        or tuple(cycle["entitlement_codes"] or ()) != tuple(entitlements)
        or str(cycle["quota_profile_ref"]).strip().lower() != quota_profile_ref
        or _canonical_metric(cycle["metric_code"]) != metric
        or cycle["period_start"] != account["period_start"]
        or cycle["period_end"] != account["period_end"]
        or cycle["base_limit_units"] != limit_units
        or cycle["used_units"] != account["used_units"]
        or cycle["rollover_units"] != 0
        or cycle["top_up_units"] != 0
    ):
        raise RuntimeError(
            "Legacy quota retirement blocked: authoritative quota cycle does not exactly preserve legacy state."
        )


def _assert_usage(modern, legacy, cycle_id) -> None:
    if (
        modern["quota_cycle_id"] != cycle_id
        or modern["subscription_id"] != legacy["subscription_id"]
        or modern["customer_ref"] != legacy["customer_ref"]
        or _canonical_metric(modern["metric_code"])
        != _canonical_metric(legacy["metric_code"])
        or modern["units"] != legacy["units"]
        or modern["idempotency_key_hash"] != legacy["idempotency_key_hash"]
        or modern["dimensions_digest"] != legacy["dimensions_digest"]
        or modern["occurred_at"] != legacy["occurred_at"]
    ):
        raise RuntimeError(
            "Legacy quota retirement blocked: migrated usage replay history conflicts."
        )


def _backfill_and_verify() -> None:
    connection = op.get_bind()
    tables = _tables()
    accounts = connection.execute(
        sa.select(tables["quota"]).order_by(
            tables["quota"].c.period_start,
            tables["quota"].c.id,
        )
    ).mappings().all()

    for account in accounts:
        if (
            account["period_end"] <= account["period_start"]
            or account["limit_units"] <= 0
            or account["used_units"] < 0
            or account["used_units"] > account["limit_units"]
        ):
            raise RuntimeError(
                "Legacy quota retirement blocked: invalid legacy quota account state."
            )
        subscription = _one(
            connection,
            sa.select(tables["subscription"]).where(
                tables["subscription"].c.id == account["subscription_id"]
            ),
            "Legacy quota retirement blocked: subscription is missing.",
        )
        plan = _one(
            connection,
            sa.select(tables["plan"]).where(
                tables["plan"].c.id == subscription["plan_id"]
            ),
            "Legacy quota retirement blocked: plan is missing.",
        )
        authority = _authority(connection, tables, account, subscription, plan)
        metric = authority[4]
        cycle = connection.execute(
            sa.select(tables["cycle"]).where(
                tables["cycle"].c.subscription_id == account["subscription_id"],
                tables["cycle"].c.metric_code == metric,
                tables["cycle"].c.period_start == account["period_start"],
            )
        ).mappings().first()
        if cycle is None:
            cycle_id = uuid.uuid4()
            connection.execute(
                tables["cycle"].insert().values(
                    id=cycle_id,
                    subscription_id=account["subscription_id"],
                    source_cycle_id=None,
                    customer_ref=account["customer_ref"],
                    plan_code=authority[0],
                    plan_catalog_version=authority[1],
                    entitlement_codes=list(authority[2]),
                    quota_profile_ref=authority[3],
                    metric_code=metric,
                    period_start=account["period_start"],
                    period_end=account["period_end"],
                    base_limit_units=authority[5],
                    rollover_units=0,
                    top_up_units=0,
                    rollover_status="available",
                    used_units=account["used_units"],
                    version=account["version"],
                )
            )
            cycle = _one(
                connection,
                sa.select(tables["cycle"]).where(
                    tables["cycle"].c.id == cycle_id
                ),
                "Legacy quota retirement blocked: migrated quota cycle was not persisted.",
            )
        _assert_cycle(cycle, account, authority)

        legacy_rows = connection.execute(
            sa.select(tables["usage"])
            .where(tables["usage"].c.quota_account_id == account["id"])
            .order_by(tables["usage"].c.occurred_at, tables["usage"].c.id)
        ).mappings().all()
        legacy_sum = sum(int(item["units"]) for item in legacy_rows)
        if legacy_sum != int(account["used_units"]):
            raise RuntimeError(
                "Legacy quota retirement blocked: usage ledger does not reconcile to quota used_units."
            )
        for legacy in legacy_rows:
            if (
                legacy["subscription_id"] != account["subscription_id"]
                or legacy["customer_ref"] != account["customer_ref"]
                or _canonical_metric(legacy["metric_code"]) != metric
                or not account["period_start"]
                <= legacy["occurred_at"]
                < account["period_end"]
            ):
                raise RuntimeError(
                    "Legacy quota retirement blocked: usage entry conflicts with its quota account."
                )
            modern = connection.execute(
                sa.select(tables["cycle_usage"]).where(
                    tables["cycle_usage"].c.idempotency_key_hash
                    == legacy["idempotency_key_hash"]
                )
            ).mappings().first()
            if modern is None:
                usage_id = uuid.uuid4()
                connection.execute(
                    tables["cycle_usage"].insert().values(
                        id=usage_id,
                        quota_cycle_id=cycle["id"],
                        subscription_id=legacy["subscription_id"],
                        customer_ref=legacy["customer_ref"],
                        metric_code=metric,
                        units=legacy["units"],
                        idempotency_key_hash=legacy["idempotency_key_hash"],
                        dimensions_digest=legacy["dimensions_digest"],
                        occurred_at=legacy["occurred_at"],
                        recorded_at=legacy["recorded_at"],
                    )
                )
                modern = _one(
                    connection,
                    sa.select(tables["cycle_usage"]).where(
                        tables["cycle_usage"].c.id == usage_id
                    ),
                    "Legacy quota retirement blocked: migrated usage was not persisted.",
                )
            _assert_usage(modern, legacy, cycle["id"])


def upgrade() -> None:
    if not context.is_offline_mode():
        _backfill_and_verify()
    op.drop_index(
        "ix_admin_market_subscription_usage_customer_metric",
        table_name=LEGACY_USAGE,
    )
    op.drop_index(
        "ix_admin_market_subscription_usage_subscription_time",
        table_name=LEGACY_USAGE,
    )
    op.drop_table(LEGACY_USAGE)
    op.drop_index(
        "ix_admin_market_subscription_quota_customer_metric",
        table_name=LEGACY_QUOTAS,
    )
    op.drop_table(LEGACY_QUOTAS)


def downgrade() -> None:
    if not context.is_offline_mode():
        connection = op.get_bind()
        for table_name in (CYCLE_USAGE, CYCLES):
            row = connection.execute(
                sa.text(f"SELECT 1 FROM {table_name} LIMIT 1")
            ).first()
            if row is not None:
                raise RuntimeError(
                    "Downgrade blocked: authoritative quota-cycle data cannot be converted back to retired legacy quota tables."
                )

    op.create_table(
        LEGACY_QUOTAS,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subscription_id", sa.Uuid(), nullable=False),
        sa.Column("customer_ref", sa.String(128), nullable=False),
        sa.Column("quota_profile_ref", sa.String(128), nullable=False),
        sa.Column("metric_code", sa.String(128), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("limit_units", sa.BigInteger(), nullable=False),
        sa.Column("used_units", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "period_end > period_start",
            name=op.f("ck_admin_market_subscription_quota_period"),
        ),
        sa.CheckConstraint(
            "limit_units >= 0 AND used_units >= 0 AND used_units <= limit_units",
            name=op.f("ck_admin_market_subscription_quota_units"),
        ),
        sa.CheckConstraint(
            "version >= 0",
            name=op.f("ck_admin_market_subscription_quota_version"),
        ),
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["admin_market_subscriptions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "subscription_id",
            "metric_code",
            "period_start",
            name="uq_admin_market_subscription_quota_period",
        ),
    )
    op.create_index(
        "ix_admin_market_subscription_quota_customer_metric",
        LEGACY_QUOTAS,
        ["customer_ref", "metric_code", "period_end"],
    )

    op.create_table(
        LEGACY_USAGE,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("quota_account_id", sa.Uuid(), nullable=False),
        sa.Column("subscription_id", sa.Uuid(), nullable=False),
        sa.Column("customer_ref", sa.String(128), nullable=False),
        sa.Column("metric_code", sa.String(128), nullable=False),
        sa.Column("units", sa.BigInteger(), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(64), nullable=False),
        sa.Column("dimensions_digest", sa.String(64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "units > 0",
            name=op.f("ck_admin_market_subscription_usage_units"),
        ),
        sa.CheckConstraint(
            "length(idempotency_key_hash) = 64 AND length(dimensions_digest) = 64",
            name=op.f("ck_admin_market_subscription_usage_digests"),
        ),
        sa.ForeignKeyConstraint(
            ["quota_account_id"],
            [f"{LEGACY_QUOTAS}.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["admin_market_subscriptions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "idempotency_key_hash",
            name="uq_admin_market_subscription_usage_idempotency",
        ),
    )
    op.create_index(
        "ix_admin_market_subscription_usage_subscription_time",
        LEGACY_USAGE,
        ["subscription_id", "occurred_at"],
    )
    op.create_index(
        "ix_admin_market_subscription_usage_customer_metric",
        LEGACY_USAGE,
        ["customer_ref", "metric_code", "occurred_at"],
    )
