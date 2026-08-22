from __future__ import annotations

import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from processual_api.admin_marketplace.models import AdminMarketPlan, AdminMarketSubscription
from processual_api.admin_marketplace.subscription_quota_rollover_persistence import (
    AdminMarketSubscriptionQuotaCycle,
)
from processual_api.admin_marketplace.subscription_quota_usage_persistence import (
    AdminMarketSubscriptionQuotaCycleUsage,
)
from processual_api.admin_marketplace.subscription_runtime_persistence import (
    AdminMarketSubscriptionQuotaAccount,
    AdminMarketSubscriptionRuntime,
    AdminMarketSubscriptionUsageLedger,
)

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

            session.add(
                AdminMarketPlan(
                    id=plan_id,
                    plan_code="starter",
                    display_name="Retirement migration starter",
                    entitlement_profile_ref=f"starter-ent-{suffix}",
                    quota_profile_ref=quota_profile_ref,
                    metadata_json={},
                )
            )
            await session.flush()
            session.add(
                AdminMarketSubscription(
                    id=subscription_id,
                    subscription_ref=f"retirement-sub-{suffix}",
                    customer_ref=customer_ref,
                    order_id=None,
                    offer_id=None,
                    plan_id=plan_id,
                    status="active",
                    starts_at=period_start,
                    ends_at=None,
                )
            )
            await session.flush()
            session.add_all(
                [
                    AdminMarketSubscriptionRuntime(
                        id=runtime_id,
                        subscription_id=subscription_id,
                        customer_ref=customer_ref,
                        entitlement_profile_ref=f"starter-ent-{suffix}",
                        quota_profile_ref=quota_profile_ref,
                        access_stage="active",
                        version=0,
                        effective_at=period_start,
                    ),
                    AdminMarketSubscriptionQuotaAccount(
                        id=account_id,
                        subscription_id=subscription_id,
                        customer_ref=customer_ref,
                        quota_profile_ref=quota_profile_ref,
                        metric_code="credits",
                        period_start=period_start,
                        period_end=period_end,
                        limit_units=10_000,
                        used_units=3,
                        version=2,
                    ),
                ]
            )
            await session.flush()
            session.add(
                AdminMarketSubscriptionUsageLedger(
                    id=usage_id,
                    quota_account_id=account_id,
                    subscription_id=subscription_id,
                    customer_ref=customer_ref,
                    metric_code="credits",
                    units=3,
                    idempotency_key_hash=idem_hash,
                    dimensions_digest=dimensions_digest,
                    occurred_at=now,
                )
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

            cycle = await session.scalar(
                select(AdminMarketSubscriptionQuotaCycle).where(
                    AdminMarketSubscriptionQuotaCycle.subscription_id == subscription_id
                )
            )
            assert cycle is not None
            assert cycle.customer_ref == customer_ref
            assert cycle.plan_code == "starter"
            assert cycle.plan_catalog_version == "2026-08-plan-fulfillment-v2"
            assert cycle.metric_code == "maestro_units"
            assert cycle.quota_profile_ref == quota_profile_ref
            assert cycle.base_limit_units == 10_000
            assert cycle.used_units == 3
            assert cycle.version == 2
            assert cycle.rollover_units == 0
            assert cycle.top_up_units == 0

            usage = await session.scalar(
                select(AdminMarketSubscriptionQuotaCycleUsage).where(
                    AdminMarketSubscriptionQuotaCycleUsage.idempotency_key_hash
                    == idem_hash
                )
            )
            assert usage is not None
            assert usage.quota_cycle_id == cycle.id
            assert usage.subscription_id == subscription_id
            assert usage.customer_ref == customer_ref
            assert usage.metric_code == "maestro_units"
            assert usage.units == 3
            assert usage.dimensions_digest == dimensions_digest
            assert usage.occurred_at == now
    finally:
        try:
            async with session_factory() as session:
                cycle_ids = select(AdminMarketSubscriptionQuotaCycle.id).where(
                    AdminMarketSubscriptionQuotaCycle.subscription_id == subscription_id
                )
                await session.execute(
                    delete(AdminMarketSubscriptionQuotaCycleUsage).where(
                        AdminMarketSubscriptionQuotaCycleUsage.quota_cycle_id.in_(cycle_ids)
                    )
                )
                await session.execute(
                    delete(AdminMarketSubscriptionQuotaCycle).where(
                        AdminMarketSubscriptionQuotaCycle.subscription_id == subscription_id
                    )
                )
                await session.execute(
                    delete(AdminMarketSubscriptionRuntime).where(
                        AdminMarketSubscriptionRuntime.subscription_id == subscription_id
                    )
                )
                await session.execute(
                    delete(AdminMarketSubscription).where(
                        AdminMarketSubscription.id == subscription_id
                    )
                )
                await session.execute(
                    delete(AdminMarketPlan).where(AdminMarketPlan.id == plan_id)
                )
                await session.commit()
        finally:
            await engine.dispose()
