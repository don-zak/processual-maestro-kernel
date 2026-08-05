from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select

from processual_api.admin_marketplace.subscription_runtime_persistence import (
    AdminMarketSubscriptionRuntime,
)
from processual_api.db.session import get_session_factory


@dataclass(frozen=True, slots=True)
class SubscriptionAccessSnapshot:
    customer_ref: str
    access_stage: str
    entitlement_profile_ref: str
    quota_profile_ref: str


async def resolve_subscription_access(
    customer_ref: str,
) -> SubscriptionAccessSnapshot | None:
    normalized = customer_ref.strip().lower()
    if not normalized:
        return None

    session_factory = get_session_factory()
    async with session_factory() as session:
        statement = (
            select(AdminMarketSubscriptionRuntime)
            .where(AdminMarketSubscriptionRuntime.customer_ref == normalized)
            .order_by(
                AdminMarketSubscriptionRuntime.effective_at.desc(),
                AdminMarketSubscriptionRuntime.id.desc(),
            )
            .limit(2)
        )
        result = await session.scalars(statement)
        rows = tuple(result.all())

    if not rows:
        return None
    if len(rows) != 1:
        raise RuntimeError("multiple subscription runtime rows found for customer")

    runtime = rows[0]
    return SubscriptionAccessSnapshot(
        customer_ref=runtime.customer_ref,
        access_stage=runtime.access_stage,
        entitlement_profile_ref=runtime.entitlement_profile_ref,
        quota_profile_ref=runtime.quota_profile_ref,
    )
