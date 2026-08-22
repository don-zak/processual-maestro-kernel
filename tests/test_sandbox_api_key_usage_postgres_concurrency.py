from __future__ import annotations

import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, func, select

from processual_api.admin_marketplace.models import (
    AdminMarketPlan,
    AdminMarketSubscription,
)
from processual_api.admin_marketplace.subscription_quota_rollover_persistence import (
    AdminMarketSubscriptionQuotaCycle,
)
from processual_api.admin_marketplace.subscription_quota_usage import (
    SubscriptionQuotaUsageError,
)
from processual_api.admin_marketplace.subscription_quota_usage_persistence import (
    AdminMarketSubscriptionQuotaCycleUsage,
)
from processual_api.admin_marketplace.subscription_runtime_persistence import (
    AdminMarketSubscriptionRuntime,
)
from processual_api.db.session import close_db, get_session_factory, init_db
from processual_api.services.sandbox_api_key_usage import record_sandbox_api_key_usage


_DATABASE_URL = os.environ.get("DATABASE_URL", "").lower()
pytestmark = pytest.mark.skipif(
    not _DATABASE_URL.startswith(("postgresql://", "postgresql+asyncpg://")),
    reason="PostgreSQL concurrency qualification requires DATABASE_URL",
)


@pytest.mark.asyncio
async def test_parallel_sandbox_usage_cannot_overshoot_quota() -> None:
    plan_id = uuid.uuid4()
    subscription_id = uuid.uuid4()
    runtime_id = uuid.uuid4()
    cycle_id = uuid.uuid4()
    suffix = uuid.uuid4().hex
    customer_ref = f"qualification-customer-{suffix}"
    plan_code = f"qualification-plan-{suffix}"
    metric_code = "maestro_units"
    now = datetime.now(UTC)

    await init_db()
    session_factory = get_session_factory()
    try:
        async with session_factory() as session:
            session.add(
                AdminMarketPlan(
                    id=plan_id,
                    plan_code=plan_code,
                    display_name="Sandbox concurrency qualification",
                    entitlement_profile_ref="qualification_entitlements",
                    quota_profile_ref="qualification_quota",
                    metadata_json={},
                )
            )
            session.add(
                AdminMarketSubscription(
                    id=subscription_id,
                    subscription_ref=f"qualification-subscription-{suffix}",
                    customer_ref=customer_ref,
                    order_id=None,
                    offer_id=None,
                    plan_id=plan_id,
                    status="active",
                    starts_at=now,
                    ends_at=None,
                )
            )
            session.add(
                AdminMarketSubscriptionRuntime(
                    id=runtime_id,
                    subscription_id=subscription_id,
                    customer_ref=customer_ref,
                    entitlement_profile_ref="qualification_entitlements",
                    quota_profile_ref="qualification_quota",
                    access_stage="active",
                    version=0,
                    effective_at=now,
                )
            )
            session.add(
                AdminMarketSubscriptionQuotaCycle(
                    id=cycle_id,
                    subscription_id=subscription_id,
                    source_cycle_id=None,
                    customer_ref=customer_ref,
                    plan_code=plan_code,
                    plan_catalog_version="sandbox-concurrency-qualification-v1",
                    entitlement_codes=["maestro_execution"],
                    quota_profile_ref="qualification_quota",
                    metric_code=metric_code,
                    period_start=now - timedelta(minutes=1),
                    period_end=now + timedelta(hours=1),
                    base_limit_units=5,
                    rollover_units=0,
                    top_up_units=0,
                    rollover_status="available",
                    used_units=0,
                    version=0,
                )
            )
            await session.commit()

        identity = {
            "sub": f"qualification-user-{suffix}",
            "user_id": f"qualification-user-{suffix}",
            "client_id": customer_ref,
            "role": "client",
            "auth_method": "api_key",
            "session_type": "sandbox_api_key",
            "api_key_id": str(uuid.uuid4()),
            "subscription_id": str(subscription_id),
            "plan_id": plan_code,
            "operational_profile_id": "service_integration_read_only",
            "environment": "sandbox",
            "scopes": ["read:health"],
            "production_allowed": False,
            "runtime_connector_approved": False,
        }

        async def _consume(index: int):
            try:
                row = await record_sandbox_api_key_usage(
                    current_user=identity,
                    method="POST",
                    endpoint="/v1/analyze",
                    metric_code=metric_code,
                    units=1,
                    idempotency_key=f"qualification-{suffix}-{index}",
                )
                return ("accepted", str(row.id))
            except SubscriptionQuotaUsageError as exc:
                return ("rejected", str(exc))

        results = await asyncio.gather(*(_consume(index) for index in range(10)))
        accepted = [value for status, value in results if status == "accepted"]
        rejected = [value for status, value in results if status == "rejected"]

        assert len(accepted) == 5
        assert len(rejected) == 5
        assert all("balance is insufficient" in value.lower() for value in rejected)

        async with session_factory() as session:
            cycle = await session.get(AdminMarketSubscriptionQuotaCycle, cycle_id)
            assert cycle is not None
            assert cycle.used_units == 5
            assert cycle.version == 5

            ledger_count = await session.scalar(
                select(func.count(AdminMarketSubscriptionQuotaCycleUsage.id)).where(
                    AdminMarketSubscriptionQuotaCycleUsage.subscription_id
                    == subscription_id
                )
            )
            ledger_units = await session.scalar(
                select(
                    func.coalesce(
                        func.sum(AdminMarketSubscriptionQuotaCycleUsage.units),
                        0,
                    )
                ).where(
                    AdminMarketSubscriptionQuotaCycleUsage.subscription_id
                    == subscription_id
                )
            )
            assert ledger_count == 5
            assert ledger_units == 5
    finally:
        async with session_factory() as session:
            await session.execute(
                delete(AdminMarketSubscriptionQuotaCycleUsage).where(
                    AdminMarketSubscriptionQuotaCycleUsage.subscription_id
                    == subscription_id
                )
            )
            await session.execute(
                delete(AdminMarketSubscriptionQuotaCycle).where(
                    AdminMarketSubscriptionQuotaCycle.subscription_id
                    == subscription_id
                )
            )
            await session.execute(
                delete(AdminMarketSubscriptionRuntime).where(
                    AdminMarketSubscriptionRuntime.subscription_id
                    == subscription_id
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
        await close_db()
