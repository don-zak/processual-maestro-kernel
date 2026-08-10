from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select

from processual_api.admin_marketplace.models import AdminMarketPlan, AdminMarketSubscription
from processual_api.admin_marketplace.subscription_runtime_persistence import (
    AdminMarketSubscriptionRuntime,
)
from processual_api.db.session import get_session_factory


@dataclass(frozen=True, slots=True)
class SubscriptionAccessSnapshot:
    runtime_id: uuid.UUID
    subscription_id: uuid.UUID
    customer_ref: str
    access_stage: str
    plan_code: str
    entitlement_profile_ref: str
    quota_profile_ref: str
    effective_at: datetime
    grace_until: datetime | None


async def resolve_subscription_access(
    customer_ref: str,
) -> SubscriptionAccessSnapshot | None:
    normalized = customer_ref.strip().lower()
    if not normalized:
        return None

    session_factory = get_session_factory()
    async with session_factory() as session:
        statement = (
            select(
                AdminMarketSubscriptionRuntime,
                AdminMarketSubscription.plan_id,
                AdminMarketPlan.plan_code,
            )
            .join(
                AdminMarketSubscription,
                AdminMarketSubscription.id
                == AdminMarketSubscriptionRuntime.subscription_id,
            )
            .join(
                AdminMarketPlan,
                AdminMarketPlan.id == AdminMarketSubscription.plan_id,
            )
            .where(AdminMarketSubscriptionRuntime.customer_ref == normalized)
            .order_by(
                AdminMarketSubscriptionRuntime.effective_at.desc(),
                AdminMarketSubscriptionRuntime.id.desc(),
            )
            .limit(2)
        )
        rows = tuple((await session.execute(statement)).all())

    if not rows:
        return None
    if len(rows) != 1:
        raise RuntimeError("multiple subscription runtime rows found for customer")

    runtime, subscription_plan_id, plan_code = rows[0]
    if not isinstance(subscription_plan_id, uuid.UUID):
        raise RuntimeError("subscription plan identity is unavailable")
    normalized_plan_code = str(plan_code or "").strip().lower()
    if not normalized_plan_code:
        raise RuntimeError("subscription plan identity is unavailable")

    return SubscriptionAccessSnapshot(
        runtime_id=runtime.id,
        subscription_id=runtime.subscription_id,
        customer_ref=runtime.customer_ref,
        access_stage=runtime.access_stage,
        plan_code=normalized_plan_code,
        entitlement_profile_ref=runtime.entitlement_profile_ref,
        quota_profile_ref=runtime.quota_profile_ref,
        effective_at=runtime.effective_at,
        grace_until=runtime.grace_until,
    )
