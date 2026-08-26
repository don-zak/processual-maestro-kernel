from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from processual_api.admin_marketplace.models import (
    AdminMarketPlan,
    AdminMarketSubscription,
)
from processual_api.admin_marketplace.persistence.unit_of_work import (
    SqlAlchemyAdminMarketplaceUnitOfWork,
)
from processual_api.admin_marketplace.subscription_quota_rollover_persistence import (
    AdminMarketSubscriptionQuotaCycle,
)
from processual_api.admin_marketplace.subscription_quota_usage import (
    SubscriptionQuotaUsageCommand,
    SubscriptionQuotaUsageError,
    record_subscription_quota_usage_factory,
)
from processual_api.admin_marketplace.subscription_quota_usage_persistence import (
    AdminMarketSubscriptionQuotaCycleUsage,
)
from processual_api.admin_marketplace.subscription_runtime_persistence import (
    AdminMarketSubscriptionRuntime,
)

DATABASE_URL = os.environ.get("ADMIN_MARKET_INTEGRATION_DATABASE_URL", "")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason=(
        "Set ADMIN_MARKET_INTEGRATION_DATABASE_URL to a migrated PostgreSQL "
        "database to run the quota-cycle usage gate."
    ),
)

NOW = datetime(2026, 8, 22, 11, 30, tzinfo=UTC)


def _async_database_url() -> str:
    if DATABASE_URL.startswith("postgresql+asyncpg://"):
        return DATABASE_URL
    return DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)


@pytest.mark.asyncio
async def test_quota_cycle_usage_is_atomic_replay_safe_and_fail_closed() -> None:
    engine = create_async_engine(_async_database_url())
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    suffix = uuid.uuid4().hex[:18]
    plan_id = uuid.uuid4()
    subscription_id = uuid.uuid4()
    runtime_id = uuid.uuid4()
    cycle_id = uuid.uuid4()

    customer_ref = f"pg-quota-customer-{suffix}"
    plan_code = f"pg-quota-plan-{suffix}"
    quota_profile_ref = f"pg-quota-profile-{suffix}"
    subscription_ref = f"pg-quota-sub-{suffix}"
    period_start = NOW - timedelta(days=5)
    period_end = NOW + timedelta(days=25)

    async with session_factory() as session:
        session.add(
            AdminMarketPlan(
                id=plan_id,
                plan_code=plan_code,
                display_name="PostgreSQL quota-cycle plan",
                entitlement_profile_ref=f"ent-{suffix}",
                quota_profile_ref=quota_profile_ref,
                metadata_json={},
            )
        )
        await session.flush()
        session.add(
            AdminMarketSubscription(
                id=subscription_id,
                subscription_ref=subscription_ref,
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
                    entitlement_profile_ref=f"ent-{suffix}",
                    quota_profile_ref=quota_profile_ref,
                    access_stage="active",
                    version=0,
                    effective_at=period_start,
                    grace_until=None,
                    suspended_at=None,
                    terminated_at=None,
                ),
                AdminMarketSubscriptionQuotaCycle(
                    id=cycle_id,
                    subscription_id=subscription_id,
                    source_cycle_id=None,
                    customer_ref=customer_ref,
                    plan_code=plan_code,
                    plan_catalog_version="postgres-integration-proof",
                    entitlement_codes=["maestro_execution"],
                    quota_profile_ref=quota_profile_ref,
                    metric_code="maestro_units",
                    period_start=period_start,
                    period_end=period_end,
                    base_limit_units=10,
                    rollover_units=2,
                    top_up_units=3,
                    rollover_status="available",
                    rollover_expires_at=None,
                    rollover_locked_at=None,
                    rollover_restored_at=None,
                    rollover_expired_at=None,
                    used_units=4,
                    version=1,
                ),
            ]
        )
        await session.commit()

    record = record_subscription_quota_usage_factory(
        unit_of_work_factory=lambda: SqlAlchemyAdminMarketplaceUnitOfWork(
            session_factory
        )
    )

    first_command = SubscriptionQuotaUsageCommand(
        subscription_id=subscription_id,
        customer_ref=customer_ref,
        metric_code="credits",
        units=5,
        idempotency_key_hash="a" * 64,
        dimensions_digest="b" * 64,
        occurred_at=NOW,
        quota_cycle_id=None,
    )

    try:
        first = await record(first_command)
        assert first.subscription_id == subscription_id
        assert first.quota_cycle_id == cycle_id
        assert first.metric_code == "maestro_units"
        assert first.units == 5

        async with session_factory() as session:
            cycle = await session.get(AdminMarketSubscriptionQuotaCycle, cycle_id)
            ledgers = (
                await session.scalars(
                    select(AdminMarketSubscriptionQuotaCycleUsage).where(
                        AdminMarketSubscriptionQuotaCycleUsage.quota_cycle_id
                        == cycle_id
                    )
                )
            ).all()
            assert cycle is not None
            assert cycle.used_units == 9
            assert cycle.version == 2
            assert len(ledgers) == 1
            assert ledgers[0].idempotency_key_hash == "a" * 64

        replay = await record(first_command)
        assert replay.id == first.id

        async with session_factory() as session:
            cycle = await session.get(AdminMarketSubscriptionQuotaCycle, cycle_id)
            ledgers = (
                await session.scalars(
                    select(AdminMarketSubscriptionQuotaCycleUsage).where(
                        AdminMarketSubscriptionQuotaCycleUsage.quota_cycle_id
                        == cycle_id
                    )
                )
            ).all()
            assert cycle is not None and cycle.used_units == 9
            assert cycle.version == 2
            assert len(ledgers) == 1

        over_limit = SubscriptionQuotaUsageCommand(
            subscription_id=subscription_id,
            customer_ref=customer_ref,
            metric_code="maestro_units",
            units=7,
            idempotency_key_hash="c" * 64,
            dimensions_digest="d" * 64,
            occurred_at=NOW + timedelta(seconds=1),
            quota_cycle_id=None,
        )
        with pytest.raises(SubscriptionQuotaUsageError, match="insufficient"):
            await record(over_limit)

        async with session_factory() as session:
            cycle = await session.get(AdminMarketSubscriptionQuotaCycle, cycle_id)
            rejected = await session.scalar(
                select(AdminMarketSubscriptionQuotaCycleUsage).where(
                    AdminMarketSubscriptionQuotaCycleUsage.idempotency_key_hash
                    == "c" * 64
                )
            )
            assert cycle is not None and cycle.used_units == 9
            assert cycle.version == 2
            assert rejected is None

            runtime = await session.get(AdminMarketSubscriptionRuntime, runtime_id)
            assert runtime is not None
            runtime.access_stage = "suspended"
            runtime.suspended_at = NOW + timedelta(seconds=2)
            runtime.effective_at = NOW + timedelta(seconds=2)
            runtime.version += 1
            await session.commit()

        suspended_attempt = SubscriptionQuotaUsageCommand(
            subscription_id=subscription_id,
            customer_ref=customer_ref,
            metric_code="maestro_units",
            units=1,
            idempotency_key_hash="e" * 64,
            dimensions_digest="f" * 64,
            occurred_at=NOW + timedelta(seconds=3),
            quota_cycle_id=None,
        )
        with pytest.raises(SubscriptionQuotaUsageError, match="blocked"):
            await record(suspended_attempt)

        async with session_factory() as session:
            cycle = await session.get(AdminMarketSubscriptionQuotaCycle, cycle_id)
            suspended_ledger = await session.scalar(
                select(AdminMarketSubscriptionQuotaCycleUsage).where(
                    AdminMarketSubscriptionQuotaCycleUsage.idempotency_key_hash
                    == "e" * 64
                )
            )
            assert cycle is not None and cycle.used_units == 9
            assert cycle.version == 2
            assert suspended_ledger is None
    finally:
        async with session_factory() as session:
            await session.execute(
                delete(AdminMarketSubscriptionQuotaCycleUsage).where(
                    AdminMarketSubscriptionQuotaCycleUsage.quota_cycle_id == cycle_id
                )
            )
            await session.execute(
                delete(AdminMarketSubscriptionQuotaCycle).where(
                    AdminMarketSubscriptionQuotaCycle.id == cycle_id
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
        await engine.dispose()
