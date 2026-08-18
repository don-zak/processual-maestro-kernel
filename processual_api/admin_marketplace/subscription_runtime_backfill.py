from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from processual_api.admin_marketplace.commercial_plan_projection import (
    build_commercial_plan_projections,
    build_subscription_quota_profiles,
)
from processual_api.admin_marketplace.models import (
    AdminMarketPlan,
    AdminMarketSubscription,
)
from processual_api.admin_marketplace.subscription_runtime import (
    SubscriptionRuntimeError,
)
from processual_api.admin_marketplace.subscription_runtime_bootstrap import (
    SubscriptionRuntimeBootstrapInput,
    bootstrap_subscription_runtime_in_unit,
)
from processual_api.admin_marketplace.subscription_runtime_persistence import (
    AdminMarketSubscriptionRuntime,
    SqlAlchemySubscriptionQuotaRepository,
    SqlAlchemySubscriptionRuntimeRepository,
)
from processual_api.db.session import get_session_factory


@dataclass(frozen=True, slots=True)
class SubscriptionRuntimeBackfillResult:
    scanned: int
    created: int


class _BootstrapUnit:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.subscription_runtime = SqlAlchemySubscriptionRuntimeRepository(session)
        self.subscription_quotas = SqlAlchemySubscriptionQuotaRepository(session)

    async def __aenter__(self) -> _BootstrapUnit:
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

    async def commit(self) -> None:
        await self._session.commit()


def _effective_at(subscription: AdminMarketSubscription) -> datetime:
    value = subscription.starts_at or subscription.created_at
    if value is None:
        raise SubscriptionRuntimeError(
            "active subscription backfill requires an effective timestamp."
        )
    if value.tzinfo is None:
        # SQLAlchemy's SQLite dialect drops tzinfo even for DateTime(timezone=True).
        # Persisted marketplace timestamps are UTC, so restore that contract at the
        # persistence/domain boundary before passing the value to runtime bootstrap.
        return value.replace(tzinfo=UTC)
    return value


async def backfill_active_subscription_runtime_in_session(
    *,
    session: AsyncSession,
) -> SubscriptionRuntimeBackfillResult:
    """Backfill every active subscription missing runtime in one transaction."""

    missing_runtime = ~exists(
        select(AdminMarketSubscriptionRuntime.id).where(
            AdminMarketSubscriptionRuntime.subscription_id
            == AdminMarketSubscription.id
        )
    )
    statement = (
        select(AdminMarketSubscription)
        .where(
            AdminMarketSubscription.status == "active",
            missing_runtime,
        )
        .order_by(
            AdminMarketSubscription.created_at.asc(),
            AdminMarketSubscription.id.asc(),
        )
        .with_for_update()
    )
    subscriptions = tuple((await session.scalars(statement)).all())
    if not subscriptions:
        return SubscriptionRuntimeBackfillResult(scanned=0, created=0)

    projections = {
        projection.plan_code: projection
        for projection in build_commercial_plan_projections()
    }
    profiles = {
        profile.profile_ref: profile
        for profile in build_subscription_quota_profiles()
    }
    unit = _BootstrapUnit(session)

    for subscription in subscriptions:
        plan = await session.scalar(
            select(AdminMarketPlan)
            .where(AdminMarketPlan.id == subscription.plan_id)
            .with_for_update()
        )
        if plan is None:
            raise SubscriptionRuntimeError(
                "active subscription backfill requires an authoritative plan."
            )

        plan_code = plan.plan_code.strip().lower()
        projection = projections.get(plan_code)
        if projection is None:
            raise SubscriptionRuntimeError(
                "active subscription plan is not in the canonical commercial catalog."
            )

        entitlement_profile_ref = plan.entitlement_profile_ref.strip().lower()
        quota_profile_ref = plan.quota_profile_ref.strip().lower()
        if (
            entitlement_profile_ref != projection.entitlement_profile_ref
            or quota_profile_ref != projection.quota_profile_ref
        ):
            raise SubscriptionRuntimeError(
                "active subscription plan runtime bindings diverge from the canonical projection."
            )

        quota_profile = profiles.get(projection.quota_profile_ref)
        if quota_profile is None:
            raise SubscriptionRuntimeError(
                "canonical subscription quota profile is unavailable."
            )

        await bootstrap_subscription_runtime_in_unit(
            source=SubscriptionRuntimeBootstrapInput(
                subscription_id=subscription.id,
                customer_ref=subscription.customer_ref,
                entitlement_profile_ref=projection.entitlement_profile_ref,
                quota_profile_ref=projection.quota_profile_ref,
                subscription_status=subscription.status,
                effective_at=_effective_at(subscription),
            ),
            quota_profile=quota_profile,
            uow=unit,
        )

    await session.commit()
    return SubscriptionRuntimeBackfillResult(
        scanned=len(subscriptions),
        created=len(subscriptions),
    )


async def _run() -> SubscriptionRuntimeBackfillResult:
    session_factory = get_session_factory()
    async with session_factory() as session:
        return await backfill_active_subscription_runtime_in_session(
            session=session,
        )


def main() -> int:
    result = asyncio.run(_run())
    print(
        "subscription-runtime-backfill "
        f"scanned={result.scanned} created={result.created}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "SubscriptionRuntimeBackfillResult",
    "backfill_active_subscription_runtime_in_session",
    "main",
]
