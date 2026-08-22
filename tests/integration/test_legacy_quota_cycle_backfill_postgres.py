from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from processual_api.admin_marketplace.assessment_quota_profile_persistence import (
    AdminMarketAssessmentQuotaProfile,
)
from processual_api.admin_marketplace.assessment_subscription_persistence import (
    AdminMarketAssessmentSubscriptionBinding,
)
from processual_api.admin_marketplace.models import (
    AdminMarketPlan,
    AdminMarketSubscription,
)
from processual_api.admin_marketplace.subscription_legacy_quota_cycle_backfill import (
    backfill_legacy_quota_cycles_in_session,
)
from processual_api.admin_marketplace.subscription_quota_rollover_persistence import (
    AdminMarketSubscriptionQuotaCycle,
)
from processual_api.admin_marketplace.subscription_quota_usage_persistence import (
    AdminMarketSubscriptionQuotaCycleUsage,
)
from processual_api.admin_marketplace.subscription_runtime_persistence import (
    AdminMarketSubscriptionQuotaAccount,
    AdminMarketSubscriptionUsageLedger,
)

DATABASE_URL = os.environ.get("ADMIN_MARKET_INTEGRATION_DATABASE_URL", "")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason=(
        "Set ADMIN_MARKET_INTEGRATION_DATABASE_URL to a migrated PostgreSQL "
        "database to run the legacy quota migration gate."
    ),
)

NOW = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)


def _async_database_url() -> str:
    if DATABASE_URL.startswith("postgresql+asyncpg://"):
        return DATABASE_URL
    return DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)


@pytest.mark.asyncio
async def test_assessment_legacy_quota_backfill_preserves_usage_and_replay() -> None:
    engine = create_async_engine(_async_database_url())
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    suffix = uuid.uuid4().hex[:18]
    plan_id = uuid.uuid4()
    subscription_id = uuid.uuid4()
    account_id = uuid.uuid4()
    usage_id = uuid.uuid4()
    binding_id = uuid.uuid4()
    profile_ref = f"assessment_quota_pg_{suffix}"
    binding_hash = "a" * 64
    activation_hash = "b" * 64
    payload_digest = "c" * 64
    usage_hash = "d" * 64
    dimensions_digest = "e" * 64
    customer_ref = f"pg-assessment-customer-{suffix}"
    plan_code = f"academic-assessment-{suffix}"
    subscription_ref = f"pg-assessment-sub-{suffix}"
    period_start = NOW - timedelta(days=5)
    period_end = NOW + timedelta(days=26)

    try:
        async with session_factory() as session:
            plan = AdminMarketPlan(
                id=plan_id,
                plan_code=plan_code,
                display_name="PostgreSQL assessment migration plan",
                entitlement_profile_ref=f"assessment-ent-{suffix}",
                quota_profile_ref=f"catalog-quota-not-authoritative-{suffix}",
                metadata_json={},
            )
            subscription = AdminMarketSubscription(
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
            profile = AdminMarketAssessmentQuotaProfile(
                profile_ref=profile_ref,
                assessment_binding_hash=binding_hash,
                assessment_id=f"assessment-{suffix}",
                customer_ref=customer_ref,
                public_plan_id="academic_institution",
                entitlement_source_plan_code=plan_code,
                approved_by="postgres-integration-reviewer",
                approval_reference=f"approval-{suffix}",
                entitlement_codes_json=["maestro_execution", "academic_use"],
                metric_code="maestro_units",
                limit_units=125_000,
                cycle_kind="calendar_month",
                compatibility_period_days=30,
                definition_version="2026-08-assessment-quota-profile-v1",
                payload_digest=payload_digest,
            )
            session.add_all([plan, subscription, profile])
            await session.flush()
            session.add(
                AdminMarketAssessmentSubscriptionBinding(
                    id=binding_id,
                    binding_ref=f"asb-pg-{suffix}",
                    subscription_id=subscription_id,
                    assessment_binding_hash=binding_hash,
                    assessment_id=f"assessment-{suffix}",
                    customer_ref=customer_ref,
                    public_plan_id="academic_institution",
                    entitlement_source_plan_code=plan_code,
                    entitlement_plan_id=plan_id,
                    entitlement_profile_ref=plan.entitlement_profile_ref,
                    quota_profile_ref=profile_ref,
                    activation_idempotency_key_hash=activation_hash,
                    created_at=NOW,
                )
            )
            session.add(
                AdminMarketSubscriptionQuotaAccount(
                    id=account_id,
                    subscription_id=subscription_id,
                    customer_ref=customer_ref,
                    quota_profile_ref=profile_ref,
                    metric_code="maestro_units",
                    period_start=period_start,
                    period_end=period_end,
                    limit_units=125_000,
                    used_units=25_000,
                    version=4,
                )
            )
            await session.flush()
            session.add(
                AdminMarketSubscriptionUsageLedger(
                    id=usage_id,
                    quota_account_id=account_id,
                    subscription_id=subscription_id,
                    customer_ref=customer_ref,
                    metric_code="maestro_units",
                    units=25_000,
                    idempotency_key_hash=usage_hash,
                    dimensions_digest=dimensions_digest,
                    occurred_at=NOW,
                    recorded_at=NOW,
                )
            )
            await session.commit()

        async with session_factory() as session:
            first = await backfill_legacy_quota_cycles_in_session(session=session)
            assert first.scanned_accounts == 1
            assert first.created_cycles == 1
            assert first.scanned_usage == 1
            assert first.created_usage == 1

        async with session_factory() as session:
            cycle = await session.scalar(
                select(AdminMarketSubscriptionQuotaCycle).where(
                    AdminMarketSubscriptionQuotaCycle.subscription_id
                    == subscription_id
                )
            )
            assert cycle is not None
            assert cycle.customer_ref == customer_ref
            assert cycle.plan_code == plan_code
            assert cycle.plan_catalog_version == (
                "2026-08-assessment-quota-profile-v1"
            )
            assert cycle.quota_profile_ref == profile_ref
            assert cycle.metric_code == "maestro_units"
            assert cycle.base_limit_units == 125_000
            assert cycle.used_units == 25_000
            assert cycle.period_start == period_start
            assert cycle.period_end == period_end
            assert tuple(cycle.entitlement_codes) == (
                "maestro_execution",
                "academic_use",
            )

            migrated = await session.scalar(
                select(AdminMarketSubscriptionQuotaCycleUsage).where(
                    AdminMarketSubscriptionQuotaCycleUsage.idempotency_key_hash
                    == usage_hash
                )
            )
            assert migrated is not None
            assert migrated.quota_cycle_id == cycle.id
            assert migrated.subscription_id == subscription_id
            assert migrated.units == 25_000
            assert migrated.dimensions_digest == dimensions_digest
            assert migrated.occurred_at == NOW

            replay = await backfill_legacy_quota_cycles_in_session(session=session)
            assert replay.scanned_accounts == 1
            assert replay.created_cycles == 0
            assert replay.scanned_usage == 1
            assert replay.created_usage == 0

            cycle_count = await session.scalar(
                select(func.count())
                .select_from(AdminMarketSubscriptionQuotaCycle)
                .where(
                    AdminMarketSubscriptionQuotaCycle.subscription_id
                    == subscription_id
                )
            )
            usage_count = await session.scalar(
                select(func.count())
                .select_from(AdminMarketSubscriptionQuotaCycleUsage)
                .where(
                    AdminMarketSubscriptionQuotaCycleUsage.subscription_id
                    == subscription_id
                )
            )
            assert cycle_count == 1
            assert usage_count == 1
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
                delete(AdminMarketSubscriptionUsageLedger).where(
                    AdminMarketSubscriptionUsageLedger.subscription_id
                    == subscription_id
                )
            )
            await session.execute(
                delete(AdminMarketSubscriptionQuotaAccount).where(
                    AdminMarketSubscriptionQuotaAccount.subscription_id
                    == subscription_id
                )
            )
            await session.execute(
                delete(AdminMarketAssessmentSubscriptionBinding).where(
                    AdminMarketAssessmentSubscriptionBinding.subscription_id
                    == subscription_id
                )
            )
            await session.execute(
                delete(AdminMarketAssessmentQuotaProfile).where(
                    AdminMarketAssessmentQuotaProfile.profile_ref == profile_ref
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
