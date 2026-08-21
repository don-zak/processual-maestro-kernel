from __future__ import annotations

import asyncio
import os
import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from processual_api.admin_marketplace.models import (
    AdminMarketPlan,
    AdminMarketSubscription,
)
from processual_api.admin_marketplace.subscription_runtime_persistence import (
    AdminMarketSubscriptionRuntime,
)
from processual_api.db.session import close_db, get_session_factory, init_db
from processual_api.settings import settings


PLAN_CODE = "enterprise_integration_starter"
CUSTOMER_REF_ENV = "PMK_LOCAL_REVIEW_CUSTOMER_REF"


def _guard_local_sqlite_only() -> str:
    if settings.is_production:
        raise RuntimeError("local review subscription seed is forbidden in production")

    database_url = str(settings.database_url or "").strip()
    if not database_url.startswith("sqlite+aiosqlite:///"):
        raise RuntimeError(
            "local review subscription seed requires a local sqlite+aiosqlite database"
        )
    return database_url


def _customer_ref() -> str:
    value = str(os.environ.get(CUSTOMER_REF_ENV, "admin")).strip().lower()
    if not value or len(value) > 128:
        raise RuntimeError("local review customer reference is invalid")
    return value


async def seed() -> None:
    _guard_local_sqlite_only()
    customer_ref = _customer_ref()
    now = datetime.now(UTC)

    await init_db()
    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            plan = await session.scalar(
                select(AdminMarketPlan).where(AdminMarketPlan.plan_code == PLAN_CODE)
            )
            if plan is None:
                plan = AdminMarketPlan(
                    id=uuid.uuid4(),
                    plan_code=PLAN_CODE,
                    display_name="Enterprise Integration Starter - Local Review",
                    entitlement_profile_ref=PLAN_CODE,
                    quota_profile_ref=PLAN_CODE,
                    metadata_json={
                        "local_review_only": "true",
                        "production_authority": "false",
                    },
                    created_at=now,
                    updated_at=now,
                )
                session.add(plan)
                await session.flush()
            else:
                plan.display_name = "Enterprise Integration Starter - Local Review"
                plan.entitlement_profile_ref = PLAN_CODE
                plan.quota_profile_ref = PLAN_CODE
                plan.metadata_json = {
                    "local_review_only": "true",
                    "production_authority": "false",
                }
                plan.updated_at = now
                await session.flush()

            subscription = await session.scalar(
                select(AdminMarketSubscription)
                .where(AdminMarketSubscription.customer_ref == customer_ref)
                .order_by(AdminMarketSubscription.created_at.desc())
                .limit(1)
            )
            if subscription is None:
                subscription = AdminMarketSubscription(
                    id=uuid.uuid4(),
                    subscription_ref=f"local-review-{customer_ref}",
                    customer_ref=customer_ref,
                    order_id=None,
                    offer_id=None,
                    plan_id=plan.id,
                    status="active",
                    starts_at=now,
                    ends_at=None,
                    created_at=now,
                    updated_at=now,
                )
                session.add(subscription)
                await session.flush()
            else:
                subscription.plan_id = plan.id
                subscription.status = "active"
                subscription.starts_at = subscription.starts_at or now
                subscription.ends_at = None
                subscription.updated_at = now
                await session.flush()

            runtime = await session.scalar(
                select(AdminMarketSubscriptionRuntime).where(
                    AdminMarketSubscriptionRuntime.subscription_id == subscription.id
                )
            )
            if runtime is None:
                runtime = AdminMarketSubscriptionRuntime(
                    id=uuid.uuid4(),
                    subscription_id=subscription.id,
                    customer_ref=customer_ref,
                    entitlement_profile_ref=PLAN_CODE,
                    quota_profile_ref=PLAN_CODE,
                    access_stage="active",
                    version=0,
                    effective_at=now,
                    grace_until=None,
                    suspended_at=None,
                    terminated_at=None,
                    created_at=now,
                    updated_at=now,
                )
                session.add(runtime)
            else:
                runtime.customer_ref = customer_ref
                runtime.entitlement_profile_ref = PLAN_CODE
                runtime.quota_profile_ref = PLAN_CODE
                runtime.access_stage = "active"
                runtime.effective_at = now
                runtime.grace_until = None
                runtime.suspended_at = None
                runtime.terminated_at = None
                runtime.updated_at = now

            await session.commit()
            print(
                "local review subscription seeded: "
                f"customer_ref={customer_ref} plan={PLAN_CODE} access_stage=active"
            )
            print(
                "authority remains local-review only: "
                "runtime_connector_approved=false production_allowed=false"
            )
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(seed())
