from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from processual_api.admin_marketplace.commercial_plan_projection import (
    build_commercial_plan_projections,
)
from processual_api.admin_marketplace.subscription_authoritative_quota_bootstrap import (
    AuthoritativeQuotaBootstrapInput,
    AuthoritativeQuotaBootstrapUnitOfWork,
    bootstrap_authoritative_quota_in_unit,
)
from processual_api.admin_marketplace.subscription_quota_profiles import (
    SubscriptionQuotaProfile,
    validate_quota_profile,
)
from processual_api.admin_marketplace.subscription_quota_rollover_persistence import (
    AdminMarketSubscriptionQuotaCycle,
)
from processual_api.admin_marketplace.subscription_runtime import (
    SubscriptionRuntimeError,
)
from processual_api.admin_marketplace.subscription_runtime_persistence import (
    AdminMarketSubscriptionRuntime,
)
from processual_api.billing.maestro_units import normalize_maestro_metric_code
from processual_api.billing.plan_fulfillment_catalog import (
    PLAN_FULFILLMENT_CATALOG_VERSION,
    QUOTA_METRIC_CODE,
)


@dataclass(frozen=True, slots=True)
class SubscriptionRuntimeBootstrapInput:
    subscription_id: uuid.UUID
    customer_ref: str
    entitlement_profile_ref: str
    quota_profile_ref: str
    subscription_status: str
    effective_at: datetime


@dataclass(frozen=True, slots=True)
class SubscriptionRuntimeBootstrapResult:
    runtime: AdminMarketSubscriptionRuntime
    quota_cycles: tuple[AdminMarketSubscriptionQuotaCycle, ...]
    replayed: bool


class SubscriptionRuntimeBootstrapUnitOfWork(
    AuthoritativeQuotaBootstrapUnitOfWork,
    Protocol,
):
    pass


def _projection_for_source(
    *,
    source: SubscriptionRuntimeBootstrapInput,
    quota_profile: SubscriptionQuotaProfile,
):
    profile = validate_quota_profile(quota_profile)
    entitlement_profile_ref = source.entitlement_profile_ref.strip().lower()
    quota_profile_ref = source.quota_profile_ref.strip().lower()
    matches = tuple(
        projection
        for projection in build_commercial_plan_projections()
        if projection.entitlement_profile_ref == entitlement_profile_ref
        and projection.quota_profile_ref == quota_profile_ref
    )
    if len(matches) != 1:
        raise SubscriptionRuntimeError(
            "commercial runtime bootstrap requires one authoritative plan projection."
        )
    projection = matches[0]
    if profile.profile_ref != projection.quota_profile_ref:
        raise SubscriptionRuntimeError(
            "quota profile binding diverges from the authoritative plan projection."
        )
    if len(profile.metrics) != 1:
        raise SubscriptionRuntimeError(
            "commercial runtime bootstrap requires one canonical quota metric."
        )
    metric = profile.metrics[0]
    if (
        normalize_maestro_metric_code(metric.metric_code) != QUOTA_METRIC_CODE
        or metric.limit_units != projection.monthly_unit_allowance
    ):
        raise SubscriptionRuntimeError(
            "quota profile diverges from the authoritative plan fulfillment contract."
        )
    return projection, metric


async def bootstrap_subscription_runtime_in_unit(
    *,
    source: SubscriptionRuntimeBootstrapInput,
    quota_profile: SubscriptionQuotaProfile,
    uow: SubscriptionRuntimeBootstrapUnitOfWork,
) -> SubscriptionRuntimeBootstrapResult:
    """Bootstrap catalog subscription runtime and quota-cycle authority in one unit."""

    projection, metric = _projection_for_source(
        source=source,
        quota_profile=quota_profile,
    )
    result = await bootstrap_authoritative_quota_in_unit(
        source=AuthoritativeQuotaBootstrapInput(
            subscription_id=source.subscription_id,
            customer_ref=source.customer_ref,
            entitlement_profile_ref=projection.entitlement_profile_ref,
            quota_profile_ref=projection.quota_profile_ref,
            subscription_status=source.subscription_status,
            effective_at=source.effective_at,
            plan_code=projection.plan_code,
            authority_version=PLAN_FULFILLMENT_CATALOG_VERSION,
            entitlement_codes=projection.entitlement_codes,
            metric_code=metric.metric_code,
            base_limit_units=metric.limit_units,
        ),
        uow=uow,
    )
    return SubscriptionRuntimeBootstrapResult(
        runtime=result.runtime,
        quota_cycles=(result.quota_cycle,),
        replayed=result.replayed,
    )


def bootstrap_subscription_runtime_factory(
    *,
    uow_factory: Callable[[], SubscriptionRuntimeBootstrapUnitOfWork],
):
    async def bootstrap(
        *,
        source: SubscriptionRuntimeBootstrapInput,
        quota_profile: SubscriptionQuotaProfile,
    ) -> SubscriptionRuntimeBootstrapResult:
        async with uow_factory() as uow:
            result = await bootstrap_subscription_runtime_in_unit(
                source=source,
                quota_profile=quota_profile,
                uow=uow,
            )
            if not result.replayed:
                await uow.commit()
            return result

    return bootstrap


__all__ = [
    "SubscriptionRuntimeBootstrapInput",
    "SubscriptionRuntimeBootstrapResult",
    "SubscriptionRuntimeBootstrapUnitOfWork",
    "bootstrap_subscription_runtime_factory",
    "bootstrap_subscription_runtime_in_unit",
]
