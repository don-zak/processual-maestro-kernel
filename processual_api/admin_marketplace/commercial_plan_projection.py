from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from processual_api.admin_marketplace.subscription_quota_profiles import (
    SubscriptionQuotaMetric,
    SubscriptionQuotaProfile,
)
from processual_api.billing.commercial_catalog_contracts import (
    CATALOG_CONTRACT_VERSION,
    build_catalog_plan_contracts,
)
from processual_api.billing.plan_fulfillment_catalog import (
    PLAN_FULFILLMENT_CATALOG_VERSION,
    PLAN_FULFILLMENT_SPECS,
    QUOTA_METRIC_CODE,
)

COMMERCIAL_PLAN_PROJECTION_VERSION: Final = "2026-08-admin-market-plan-projection-v1"

_DISPLAY_NAMES: Final = MappingProxyType(
    {
        "academic": "Academic Individual",
        "starter": "Starter",
        "enterprise_integration_starter": "Enterprise Integration Trial",
        "business": "Business",
        "enterprise_pilot": "Enterprise Pilot",
        "enterprise_core": "Enterprise Core",
        "enterprise_scale": "Enterprise Scale",
        "enterprise_strategic": "Enterprise Strategic",
    }
)


@dataclass(frozen=True, slots=True)
class CommercialPlanProjection:
    plan_code: str
    display_name: str
    entitlement_profile_ref: str
    quota_profile_ref: str
    monthly_unit_allowance: int
    entitlement_codes: tuple[str, ...]
    metadata: dict[str, str]


def _versioned_ref(plan_code: str, kind: str) -> str:
    return f"{plan_code}:{kind}:{PLAN_FULFILLMENT_CATALOG_VERSION}".lower()


def build_commercial_plan_projections() -> tuple[CommercialPlanProjection, ...]:
    contracts = {item.plan_code: item for item in build_catalog_plan_contracts()}

    if set(contracts) != set(PLAN_FULFILLMENT_SPECS):
        raise ValueError("commercial catalog and fulfillment plan identities diverged")

    projections: list[CommercialPlanProjection] = []
    for plan_code, spec in PLAN_FULFILLMENT_SPECS.items():
        contract = contracts[plan_code]
        entitlement_codes = tuple(item.value for item in contract.entitlements)
        if entitlement_codes != spec.entitlement_codes:
            raise ValueError(
                f"commercial entitlements diverged from fulfillment for plan: {plan_code}"
            )
        if contract.included_maestro_units != spec.monthly_unit_allowance:
            raise ValueError(
                f"commercial quota diverged from fulfillment for plan: {plan_code}"
            )

        projections.append(
            CommercialPlanProjection(
                plan_code=plan_code,
                display_name=_DISPLAY_NAMES[plan_code],
                entitlement_profile_ref=_versioned_ref(plan_code, "entitlements"),
                quota_profile_ref=_versioned_ref(plan_code, "quota"),
                monthly_unit_allowance=spec.monthly_unit_allowance,
                entitlement_codes=spec.entitlement_codes,
                metadata={
                    "projection_version": COMMERCIAL_PLAN_PROJECTION_VERSION,
                    "catalog_contract_version": CATALOG_CONTRACT_VERSION,
                    "fulfillment_catalog_version": PLAN_FULFILLMENT_CATALOG_VERSION,
                    "commercial_authority": "commercial_catalog_contracts",
                },
            )
        )

    return tuple(projections)


def build_subscription_quota_profiles() -> tuple[SubscriptionQuotaProfile, ...]:
    return tuple(
        SubscriptionQuotaProfile(
            profile_ref=projection.quota_profile_ref,
            period_days=30,
            metrics=(
                SubscriptionQuotaMetric(
                    metric_code=QUOTA_METRIC_CODE,
                    limit_units=projection.monthly_unit_allowance,
                ),
            ),
        )
        for projection in build_commercial_plan_projections()
    )


__all__ = [
    "COMMERCIAL_PLAN_PROJECTION_VERSION",
    "CommercialPlanProjection",
    "build_commercial_plan_projections",
    "build_subscription_quota_profiles",
]
