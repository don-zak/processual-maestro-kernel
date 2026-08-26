from __future__ import annotations

import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

DATABASE_URL = os.environ.get("ADMIN_MARKET_INTEGRATION_DATABASE_URL", "")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="Set ADMIN_MARKET_INTEGRATION_DATABASE_URL to migrated PostgreSQL.",
)


def _async_database_url() -> str:
    if DATABASE_URL.startswith("postgresql+asyncpg://"):
        return DATABASE_URL
    return DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)


def _sync_database_url() -> str:
    return DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)


@pytest.mark.asyncio
async def test_0060_migrates_and_retires_legacy_quota_history() -> None:
    engine = create_async_engine(_async_database_url())
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    suffix = uuid.uuid4().hex[:18]
    now = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)
    period_start = now - timedelta(days=3)
    period_end = now + timedelta(days=27)

    plan_id = uuid.uuid4()
    subscription_id = uuid.uuid4()
    runtime_id = uuid.uuid4()
    account_id = uuid.uuid4()
    usage_id = uuid.uuid4()
    customer_ref = f"retirement-customer-{suffix}"
    quota_profile_ref = f"retirement-quota-{suffix}"
    idem_hash = "7" * 64
    dimensions_digest = "8" * 64

    try:
        async with session_factory() as session:
            current = await session.scalar(text("SELECT version_num FROM alembic_version"))
            assert current == "20260822_0059"

            await session.execute(
                text(
                    """
                    INSERT INTO admin_market_plans (
                        id, plan_code, display_name, entitlement_profile_ref,
                        quota_profile_ref, metadata_json
                    ) VALUES (
                        :id, 'starter', 'Retirement migration starter',
                        :entitlement_profile_ref, :quota_profile_ref, CAST('{}' AS JSON)
                    )
                    """
                ),
                {
                    "id": plan_id,
                    "entitlement_profile_ref": f"starter-ent-{suffix}",
                    "quota_profile_ref": quota_profile_ref,
                },
            )
            await session.execute(
                text(
                    """
                    INSERT INTO admin_market_subscriptions (
                        id, subscription_ref, customer_ref, order_id, offer_id,
                        plan_id, status, starts_at, ends_at
                    ) VALUES (
                        :id, :subscription_ref, :customer_ref, NULL, NULL,
                        :plan_id, 'active', :starts_at, NULL
                    )
                    """
                ),
                {
                    "id": subscription_id,
                    "subscription_ref": f"retirement-sub-{suffix}",
                    "customer_ref": customer_ref,
                    "plan_id": plan_id,
                    "starts_at": period_start,
                },
            )
            await session.execute(
                text(
                    """
                    INSERT INTO admin_market_subscription_runtime (
                        id, subscription_id, customer_ref, entitlement_profile_ref,
                        quota_profile_ref, access_stage, version, effective_at
                    ) VALUES (
                        :id, :subscription_id, :customer_ref, :entitlement_profile_ref,
                        :quota_profile_ref, 'active', 0, :effective_at
                    )
                    """
                ),
                {
                    "id": runtime_id,
                    "subscription_id": subscription_id,
                    "customer_ref": customer_ref,
                    "entitlement_profile_ref": f"starter-ent-{suffix}",
                    "quota_profile_ref": quota_profile_ref,
                    "effective_at": period_start,
                },
            )
            await session.execute(
                text(
                    """
                    INSERT INTO admin_market_subscription_quota_accounts (
                        id, subscription_id, customer_ref, quota_profile_ref,
                        metric_code, period_start, period_end, limit_units,
                        used_units, version
                    ) VALUES (
                        :id, :subscription_id, :customer_ref, :quota_profile_ref,
                        'credits', :period_start, :period_end, 10000, 3, 2
                    )
                    """
                ),
                {
                    "id": account_id,
                    "subscription_id": subscription_id,
                    "customer_ref": customer_ref,
                    "quota_profile_ref": quota_profile_ref,
                    "period_start": period_start,
                    "period_end": period_end,
                },
            )
            await session.execute(
                text(
                    """
                    INSERT INTO admin_market_subscription_usage_ledger (
                        id, quota_account_id, subscription_id, customer_ref,
                        metric_code, units, idempotency_key_hash,
                        dimensions_digest, occurred_at
                    ) VALUES (
                        :id, :quota_account_id, :subscription_id, :customer_ref,
                        'credits', 3, :idempotency_key_hash,
                        :dimensions_digest, :occurred_at
                    )
                    """
                ),
                {
                    "id": usage_id,
                    "quota_account_id": account_id,
                    "subscription_id": subscription_id,
                    "customer_ref": customer_ref,
                    "idempotency_key_hash": idem_hash,
                    "dimensions_digest": dimensions_digest,
                    "occurred_at": now,
                },
            )
            await session.commit()

        await engine.dispose()

        env = os.environ.copy()
        env["DATABASE_URL"] = _sync_database_url()
        completed = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, (
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )

        engine = create_async_engine(_async_database_url())
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            current = await session.scalar(text("SELECT version_num FROM alembic_version"))
            assert current == "20260822_0060"
            assert await session.scalar(
                text("SELECT to_regclass('admin_market_subscription_quota_accounts')")
            ) is None
            assert await session.scalar(
                text("SELECT to_regclass('admin_market_subscription_usage_ledger')")
            ) is None

            cycle = (
                await session.execute(
                    text(
                        """
                        SELECT id, customer_ref, plan_code, plan_catalog_version,
                               metric_code, quota_profile_ref, base_limit_units,
                               used_units, version, rollover_units, top_up_units
                        FROM admin_market_subscription_quota_cycles
                        WHERE subscription_id = :subscription_id
                        """
                    ),
                    {"subscription_id": subscription_id},
                )
            ).mappings().one()
            assert cycle["customer_ref"] == customer_ref
            assert cycle["plan_code"] == "starter"
            assert cycle["plan_catalog_version"] == "2026-08-plan-fulfillment-v2"
            assert cycle["metric_code"] == "maestro_units"
            assert cycle["quota_profile_ref"] == quota_profile_ref
            assert cycle["base_limit_units"] == 10_000
            assert cycle["used_units"] == 3
            assert cycle["version"] == 2
            assert cycle["rollover_units"] == 0
            assert cycle["top_up_units"] == 0

            usage = (
                await session.execute(
                    text(
                        """
                        SELECT quota_cycle_id, subscription_id, customer_ref,
                               metric_code, units, dimensions_digest, occurred_at
                        FROM admin_market_subscription_quota_cycle_usage
                        WHERE idempotency_key_hash = :idempotency_key_hash
                        """
                    ),
                    {"idempotency_key_hash": idem_hash},
                )
            ).mappings().one()
            assert usage["quota_cycle_id"] == cycle["id"]
            assert usage["subscription_id"] == subscription_id
            assert usage["customer_ref"] == customer_ref
            assert usage["metric_code"] == "maestro_units"
            assert usage["units"] == 3
            assert usage["dimensions_digest"] == dimensions_digest
            assert usage["occurred_at"] == now
    finally:
        try:
            async with session_factory() as session:
                await session.execute(
                    text(
                        """
                        DELETE FROM admin_market_subscription_quota_cycle_usage
                        WHERE subscription_id = :subscription_id
                        """
                    ),
                    {"subscription_id": subscription_id},
                )
                await session.execute(
                    text(
                        """
                        DELETE FROM admin_market_subscription_quota_cycles
                        WHERE subscription_id = :subscription_id
                        """
                    ),
                    {"subscription_id": subscription_id},
                )
                await session.execute(
                    text(
                        """
                        DELETE FROM admin_market_subscription_runtime
                        WHERE subscription_id = :subscription_id
                        """
                    ),
                    {"subscription_id": subscription_id},
                )
                await session.execute(
                    text("DELETE FROM admin_market_subscriptions WHERE id = :id"),
                    {"id": subscription_id},
                )
                await session.execute(
                    text("DELETE FROM admin_market_plans WHERE id = :id"),
                    {"id": plan_id},
                )
                await session.commit()
        finally:
            await engine.dispose()
