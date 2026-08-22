from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
from processual_api.admin_marketplace.subscription_quota_rollover_persistence import (
    AdminMarketSubscriptionQuotaCycle,
)
from processual_api.admin_marketplace.subscription_quota_usage_persistence import (
    AdminMarketSubscriptionQuotaCycleUsage,
)
from processual_api.admin_marketplace.subscription_runtime import SubscriptionRuntimeError
from processual_api.admin_marketplace.subscription_runtime_persistence import (
    AdminMarketSubscriptionQuotaAccount,
    AdminMarketSubscriptionUsageLedger,
)
from processual_api.billing.maestro_units import normalize_maestro_metric_code
from processual_api.billing.plan_fulfillment_catalog import (
    PLAN_FULFILLMENT_CATALOG_VERSION,
    QUOTA_METRIC_CODE,
    get_plan_fulfillment_spec,
)
from processual_api.db.session import get_session_factory


@dataclass(frozen=True, slots=True)
class LegacyQuotaCycleBackfillResult:
    scanned_accounts: int
    created_cycles: int
    scanned_usage: int
    created_usage: int


@dataclass(frozen=True, slots=True)
class _CycleAuthority:
    plan_code: str
    authority_version: str
    entitlement_codes: tuple[str, ...]
    quota_profile_ref: str
    metric_code: str
    base_limit_units: int


def _assert_account_shape(account: AdminMarketSubscriptionQuotaAccount) -> None:
    if account.period_start.tzinfo is None or account.period_end.tzinfo is None:
        raise SubscriptionRuntimeError(
            "legacy quota account contains a naive billing period."
        )
    if account.period_end <= account.period_start:
        raise SubscriptionRuntimeError(
            "legacy quota account contains an invalid billing period."
        )
    if account.limit_units <= 0:
        raise SubscriptionRuntimeError(
            "legacy quota account contains a non-positive quota limit."
        )
    if not 0 <= account.used_units <= account.limit_units:
        raise SubscriptionRuntimeError(
            "legacy quota account contains invalid usage state."
        )


async def _resolve_authority(
    *,
    session: AsyncSession,
    subscription: AdminMarketSubscription,
    plan: AdminMarketPlan,
    account: AdminMarketSubscriptionQuotaAccount,
) -> _CycleAuthority:
    binding = await session.scalar(
        select(AdminMarketAssessmentSubscriptionBinding).where(
            AdminMarketAssessmentSubscriptionBinding.subscription_id
            == subscription.id
        )
    )
    canonical_metric = normalize_maestro_metric_code(account.metric_code)

    if binding is not None:
        profile = await session.scalar(
            select(AdminMarketAssessmentQuotaProfile).where(
                AdminMarketAssessmentQuotaProfile.profile_ref
                == binding.quota_profile_ref
            )
        )
        if profile is None:
            raise SubscriptionRuntimeError(
                "assessment subscription is missing its authoritative quota profile."
            )
        if (
            profile.customer_ref != subscription.customer_ref
            or binding.customer_ref != subscription.customer_ref
            or binding.entitlement_plan_id != subscription.plan_id
            or binding.entitlement_source_plan_code
            != plan.plan_code.strip().lower()
            or account.quota_profile_ref != profile.profile_ref
            or canonical_metric
            != normalize_maestro_metric_code(profile.metric_code)
            or account.limit_units != profile.limit_units
        ):
            raise SubscriptionRuntimeError(
                "legacy assessment quota state conflicts with its authoritative binding."
            )
        return _CycleAuthority(
            plan_code=binding.entitlement_source_plan_code,
            authority_version=profile.definition_version,
            entitlement_codes=tuple(profile.entitlement_codes_json),
            quota_profile_ref=profile.profile_ref,
            metric_code=canonical_metric,
            base_limit_units=profile.limit_units,
        )

    try:
        spec = get_plan_fulfillment_spec(plan.plan_code)
    except KeyError as exc:
        raise SubscriptionRuntimeError(
            "legacy subscription plan is not in the authoritative catalog."
        ) from exc
    if (
        canonical_metric != QUOTA_METRIC_CODE
        or account.customer_ref != subscription.customer_ref
        or account.quota_profile_ref != plan.quota_profile_ref.strip().lower()
        or account.limit_units != spec.monthly_unit_allowance
    ):
        raise SubscriptionRuntimeError(
            "legacy quota state conflicts with the authoritative plan snapshot."
        )
    return _CycleAuthority(
        plan_code=spec.plan_code,
        authority_version=PLAN_FULFILLMENT_CATALOG_VERSION,
        entitlement_codes=tuple(spec.entitlement_codes),
        quota_profile_ref=account.quota_profile_ref,
        metric_code=canonical_metric,
        base_limit_units=spec.monthly_unit_allowance,
    )


def _cycle_matches(
    cycle: AdminMarketSubscriptionQuotaCycle,
    *,
    account: AdminMarketSubscriptionQuotaAccount,
    authority: _CycleAuthority,
) -> bool:
    return (
        cycle.subscription_id == account.subscription_id
        and cycle.customer_ref == account.customer_ref
        and cycle.plan_code == authority.plan_code
        and cycle.plan_catalog_version == authority.authority_version
        and tuple(cycle.entitlement_codes) == authority.entitlement_codes
        and cycle.quota_profile_ref == authority.quota_profile_ref
        and normalize_maestro_metric_code(cycle.metric_code)
        == authority.metric_code
        and cycle.period_start == account.period_start
        and cycle.period_end == account.period_end
        and cycle.base_limit_units == account.limit_units
        and cycle.used_units == account.used_units
        and cycle.rollover_units == 0
        and cycle.top_up_units == 0
    )


def _usage_matches(
    usage: AdminMarketSubscriptionQuotaCycleUsage,
    *,
    legacy: AdminMarketSubscriptionUsageLedger,
    cycle: AdminMarketSubscriptionQuotaCycle,
) -> bool:
    return (
        usage.quota_cycle_id == cycle.id
        and usage.subscription_id == legacy.subscription_id
        and usage.customer_ref == legacy.customer_ref
        and normalize_maestro_metric_code(usage.metric_code)
        == normalize_maestro_metric_code(legacy.metric_code)
        and usage.units == legacy.units
        and usage.idempotency_key_hash == legacy.idempotency_key_hash
        and usage.dimensions_digest == legacy.dimensions_digest
        and usage.occurred_at == legacy.occurred_at
    )


async def backfill_legacy_quota_cycles_in_session(
    *,
    session: AsyncSession,
) -> LegacyQuotaCycleBackfillResult:
    accounts = tuple(
        (
            await session.scalars(
                select(AdminMarketSubscriptionQuotaAccount).order_by(
                    AdminMarketSubscriptionQuotaAccount.period_start.asc(),
                    AdminMarketSubscriptionQuotaAccount.id.asc(),
                )
            )
        ).all()
    )
    created_cycles = 0
    scanned_usage = 0
    created_usage = 0

    for account in accounts:
        _assert_account_shape(account)
        subscription = await session.scalar(
            select(AdminMarketSubscription).where(
                AdminMarketSubscription.id == account.subscription_id
            )
        )
        if subscription is None:
            raise SubscriptionRuntimeError(
                "legacy quota account references a missing subscription."
            )
        if account.customer_ref != subscription.customer_ref:
            raise SubscriptionRuntimeError(
                "legacy quota customer conflicts with its subscription."
            )
        plan = await session.scalar(
            select(AdminMarketPlan).where(
                AdminMarketPlan.id == subscription.plan_id
            )
        )
        if plan is None:
            raise SubscriptionRuntimeError(
                "legacy quota account references a missing plan."
            )
        authority = await _resolve_authority(
            session=session,
            subscription=subscription,
            plan=plan,
            account=account,
        )
        cycle = await session.scalar(
            select(AdminMarketSubscriptionQuotaCycle).where(
                AdminMarketSubscriptionQuotaCycle.subscription_id
                == account.subscription_id,
                AdminMarketSubscriptionQuotaCycle.metric_code
                == authority.metric_code,
                AdminMarketSubscriptionQuotaCycle.period_start
                == account.period_start,
            )
        )
        if cycle is None:
            cycle = AdminMarketSubscriptionQuotaCycle(
                id=uuid.uuid4(),
                subscription_id=account.subscription_id,
                source_cycle_id=None,
                customer_ref=account.customer_ref,
                plan_code=authority.plan_code,
                plan_catalog_version=authority.authority_version,
                entitlement_codes=list(authority.entitlement_codes),
                quota_profile_ref=authority.quota_profile_ref,
                metric_code=authority.metric_code,
                period_start=account.period_start,
                period_end=account.period_end,
                base_limit_units=account.limit_units,
                rollover_units=0,
                top_up_units=0,
                rollover_status="available",
                used_units=account.used_units,
                version=account.version,
            )
            session.add(cycle)
            await session.flush()
            created_cycles += 1
        elif not _cycle_matches(
            cycle,
            account=account,
            authority=authority,
        ):
            raise SubscriptionRuntimeError(
                "existing quota cycle conflicts with legacy quota history."
            )

        legacy_usage = tuple(
            (
                await session.scalars(
                    select(AdminMarketSubscriptionUsageLedger)
                    .where(
                        AdminMarketSubscriptionUsageLedger.quota_account_id
                        == account.id
                    )
                    .order_by(
                        AdminMarketSubscriptionUsageLedger.occurred_at.asc(),
                        AdminMarketSubscriptionUsageLedger.id.asc(),
                    )
                )
            ).all()
        )
        scanned_usage += len(legacy_usage)
        for legacy in legacy_usage:
            existing_usage = await session.scalar(
                select(AdminMarketSubscriptionQuotaCycleUsage).where(
                    AdminMarketSubscriptionQuotaCycleUsage.idempotency_key_hash
                    == legacy.idempotency_key_hash
                )
            )
            if existing_usage is not None:
                if not _usage_matches(
                    existing_usage,
                    legacy=legacy,
                    cycle=cycle,
                ):
                    raise SubscriptionRuntimeError(
                        "quota usage replay conflicts with migrated legacy history."
                    )
                continue
            if (
                legacy.subscription_id != account.subscription_id
                or legacy.customer_ref != account.customer_ref
                or normalize_maestro_metric_code(legacy.metric_code)
                != authority.metric_code
                or not account.period_start
                <= legacy.occurred_at
                < account.period_end
            ):
                raise SubscriptionRuntimeError(
                    "legacy usage entry conflicts with its quota account."
                )
            session.add(
                AdminMarketSubscriptionQuotaCycleUsage(
                    id=uuid.uuid4(),
                    quota_cycle_id=cycle.id,
                    subscription_id=legacy.subscription_id,
                    customer_ref=legacy.customer_ref,
                    metric_code=authority.metric_code,
                    units=legacy.units,
                    idempotency_key_hash=legacy.idempotency_key_hash,
                    dimensions_digest=legacy.dimensions_digest,
                    occurred_at=legacy.occurred_at,
                    recorded_at=legacy.recorded_at,
                )
            )
            created_usage += 1

    await session.commit()
    return LegacyQuotaCycleBackfillResult(
        scanned_accounts=len(accounts),
        created_cycles=created_cycles,
        scanned_usage=scanned_usage,
        created_usage=created_usage,
    )


async def _run() -> LegacyQuotaCycleBackfillResult:
    session_factory = get_session_factory()
    async with session_factory() as session:
        return await backfill_legacy_quota_cycles_in_session(session=session)


def main() -> int:
    result = asyncio.run(_run())
    print(
        "legacy-quota-cycle-backfill "
        f"scanned_accounts={result.scanned_accounts} "
        f"created_cycles={result.created_cycles} "
        f"scanned_usage={result.scanned_usage} "
        f"created_usage={result.created_usage}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "LegacyQuotaCycleBackfillResult",
    "backfill_legacy_quota_cycles_in_session",
    "main",
]
