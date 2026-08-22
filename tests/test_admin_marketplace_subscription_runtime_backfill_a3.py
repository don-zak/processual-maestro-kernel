from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from processual_api.admin_marketplace.commercial_plan_projection import (
    build_commercial_plan_projections,
)
from processual_api.admin_marketplace.models import (
    AdminMarketPlan,
    AdminMarketSubscription,
)
from processual_api.admin_marketplace.subscription_quota_rollover_persistence import (
    AdminMarketSubscriptionQuotaCycle,
)
from processual_api.admin_marketplace.subscription_runtime import (
    SubscriptionRuntimeError,
)
from processual_api.admin_marketplace.subscription_runtime_backfill import (
    backfill_active_subscription_runtime_in_session,
)
from processual_api.admin_marketplace.subscription_runtime_persistence import (
    AdminMarketSubscriptionRuntime,
)
from processual_api.billing.plan_fulfillment_catalog import (
    PLAN_FULFILLMENT_CATALOG_VERSION,
    QUOTA_METRIC_CODE,
)


async def _engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        for table in (
            AdminMarketPlan.__table__,
            AdminMarketSubscription.__table__,
            AdminMarketSubscriptionRuntime.__table__,
            AdminMarketSubscriptionQuotaCycle.__table__,
        ):
            await connection.run_sync(table.create)
    return engine


def _canonical_plan() -> AdminMarketPlan:
    projection = build_commercial_plan_projections()[0]
    return AdminMarketPlan(
        id=uuid.uuid4(),
        plan_code=projection.plan_code,
        display_name=projection.display_name,
        entitlement_profile_ref=projection.entitlement_profile_ref,
        quota_profile_ref=projection.quota_profile_ref,
        metadata_json=dict(projection.metadata),
    )


def _subscription(
    *,
    plan: AdminMarketPlan,
    status: str = "active",
    customer_ref: str | None = None,
) -> AdminMarketSubscription:
    now = datetime(2026, 8, 1, tzinfo=UTC)
    return AdminMarketSubscription(
        id=uuid.uuid4(),
        subscription_ref=f"sub_{uuid.uuid4().hex}",
        customer_ref=customer_ref or f"customer_{uuid.uuid4().hex}",
        order_id=None,
        offer_id=None,
        plan_id=plan.id,
        status=status,
        starts_at=now,
        ends_at=None,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_backfill_creates_runtime_and_quota_cycle_then_replays_empty() -> None:
    engine = await _engine()
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        plan = _canonical_plan()
        projection = build_commercial_plan_projections()[0]
        subscription = _subscription(plan=plan)
        async with factory() as session:
            session.add_all([plan, subscription])
            await session.commit()

        async with factory() as session:
            first = await backfill_active_subscription_runtime_in_session(
                session=session
            )
            assert first.scanned == 1
            assert first.created == 1

        async with factory() as session:
            runtime = await session.scalar(
                select(AdminMarketSubscriptionRuntime).where(
                    AdminMarketSubscriptionRuntime.subscription_id
                    == subscription.id
                )
            )
            assert runtime is not None
            assert runtime.customer_ref == subscription.customer_ref
            assert runtime.entitlement_profile_ref == plan.entitlement_profile_ref
            assert runtime.quota_profile_ref == plan.quota_profile_ref
            cycle = await session.scalar(
                select(AdminMarketSubscriptionQuotaCycle).where(
                    AdminMarketSubscriptionQuotaCycle.subscription_id
                    == subscription.id
                )
            )
            assert cycle is not None
            assert cycle.metric_code == QUOTA_METRIC_CODE
            assert cycle.plan_code == projection.plan_code
            assert cycle.plan_catalog_version == PLAN_FULFILLMENT_CATALOG_VERSION
            assert tuple(cycle.entitlement_codes) == projection.entitlement_codes
            assert cycle.base_limit_units == projection.monthly_unit_allowance
            assert cycle.used_units == 0

            replay = await backfill_active_subscription_runtime_in_session(
                session=session
            )
            assert replay.scanned == 0
            assert replay.created == 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_backfill_ignores_non_active_subscriptions() -> None:
    engine = await _engine()
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        plan = _canonical_plan()
        subscription = _subscription(plan=plan, status="suspended")
        async with factory() as session:
            session.add_all([plan, subscription])
            await session.commit()
            result = await backfill_active_subscription_runtime_in_session(
                session=session
            )
            assert result.scanned == 0
            assert result.created == 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_backfill_rolls_back_batch_when_any_plan_is_not_canonical() -> None:
    engine = await _engine()
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        valid_plan = _canonical_plan()
        invalid_plan = AdminMarketPlan(
            id=uuid.uuid4(),
            plan_code="legacy-plan",
            display_name="Legacy Plan",
            entitlement_profile_ref="legacy:entitlements:v0",
            quota_profile_ref="legacy:quota:v0",
            metadata_json={},
        )
        valid_subscription = _subscription(
            plan=valid_plan,
            customer_ref="customer-valid",
        )
        invalid_subscription = _subscription(
            plan=invalid_plan,
            customer_ref="customer-invalid",
        )
        async with factory() as session:
            session.add_all(
                [
                    valid_plan,
                    invalid_plan,
                    valid_subscription,
                    invalid_subscription,
                ]
            )
            await session.commit()

        async with factory() as session:
            with pytest.raises(
                SubscriptionRuntimeError,
                match="canonical commercial catalog",
            ):
                await backfill_active_subscription_runtime_in_session(
                    session=session
                )
            await session.rollback()

        async with factory() as session:
            runtime_count = await session.scalar(
                select(func.count()).select_from(AdminMarketSubscriptionRuntime)
            )
            cycle_count = await session.scalar(
                select(func.count()).select_from(AdminMarketSubscriptionQuotaCycle)
            )
            assert runtime_count == 0
            assert cycle_count == 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_backfill_rejects_canonical_plan_with_drifted_runtime_binding() -> None:
    engine = await _engine()
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        plan = _canonical_plan()
        plan.entitlement_profile_ref = "drifted:entitlements:v0"
        subscription = _subscription(plan=plan)
        async with factory() as session:
            session.add_all([plan, subscription])
            await session.commit()

        async with factory() as session:
            with pytest.raises(
                SubscriptionRuntimeError,
                match="diverge from the canonical projection",
            ):
                await backfill_active_subscription_runtime_in_session(
                    session=session
                )
            await session.rollback()

        async with factory() as session:
            runtime_count = await session.scalar(
                select(func.count()).select_from(AdminMarketSubscriptionRuntime)
            )
            cycle_count = await session.scalar(
                select(func.count()).select_from(AdminMarketSubscriptionQuotaCycle)
            )
            assert runtime_count == 0
            assert cycle_count == 0
    finally:
        await engine.dispose()
