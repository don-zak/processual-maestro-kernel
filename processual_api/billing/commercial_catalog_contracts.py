"""Group 2 commercial catalog and entitlement contracts.

The contracts bind the selected Maestro pricing proposal to neutral catalog,
quota, and entitlement metadata. They do not publish offers, activate checkout,
persist subscriptions, or enforce quotas.

Numeric quota and price values are derived from the selected-pricing proposal;
this module owns catalog policy only and must not shadow those values.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Any, Final

from processual_api.billing.maestro_group1_selected_pricing import (
    build_selected_pricing_proposal,
)

CATALOG_CONTRACT_VERSION: Final = "2026-07-group2-catalog-v1"
CATALOG_STATUS: Final = "draft_review"

CATALOG_PUBLICATION_APPROVED: Final = False
OFFER_PURCHASE_ENABLED: Final = False
ENTITLEMENT_GRANT_ENABLED: Final = False
QUOTA_ENFORCEMENT_ENABLED: Final = False
SUBSCRIPTION_MIGRATION_ENABLED: Final = False

SEAT_BASED_ENTERPRISE_QUOTAS: Final = False
BYOK_ONLY: Final = True


class PlanAudience(StrEnum):
    ACADEMIC = "academic"
    INDIVIDUAL = "individual"
    BUSINESS = "business"
    ENTERPRISE = "enterprise"


class OfferVisibility(StrEnum):
    PUBLIC_CANDIDATE = "public_candidate"
    ENTERPRISE_SALES = "enterprise_sales"
    CONTRACT_ONLY = "contract_only"


class EntitlementCode(StrEnum):
    MAESTRO_EXECUTION = "maestro_execution"
    BYOK_PROVIDER_CONNECTION = "byok_provider_connection"
    STANDARD_SUPPORT = "standard_support"
    BUSINESS_SUPPORT = "business_support"
    ENTERPRISE_GOVERNANCE = "enterprise_governance"
    ADVANCED_INTEGRATION = "advanced_integration"
    ACADEMIC_USE = "academic_use"


@dataclass(frozen=True, slots=True)
class CatalogPlanContract:
    plan_code: str
    audience: PlanAudience
    visibility: OfferVisibility
    included_maestro_units: int
    monthly_price_usd: Decimal
    annual_price_usd: Decimal
    overage_per_1000_usd: Decimal
    entitlements: tuple[EntitlementCode, ...]
    seat_limit: int | None
    published: bool
    purchasable: bool
    quota_enforced: bool

    def __post_init__(self) -> None:
        if not self.plan_code.strip():
            raise ValueError("plan_code must not be blank")
        if self.included_maestro_units <= 0:
            raise ValueError("included_maestro_units must be positive")
        if self.monthly_price_usd <= 0:
            raise ValueError("monthly_price_usd must be positive")
        if self.annual_price_usd <= 0:
            raise ValueError("annual_price_usd must be positive")
        if self.overage_per_1000_usd <= 0:
            raise ValueError("overage_per_1000_usd must be positive")
        if not self.entitlements:
            raise ValueError("entitlements must not be empty")
        if self.audience is PlanAudience.ENTERPRISE and self.seat_limit is not None:
            raise ValueError("enterprise plans must not be seat based")
        if self.published or self.purchasable or self.quota_enforced:
            raise ValueError("Group 2 catalog contracts must remain non-activating")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["audience"] = self.audience.value
        payload["visibility"] = self.visibility.value
        payload["monthly_price_usd"] = str(self.monthly_price_usd)
        payload["annual_price_usd"] = str(self.annual_price_usd)
        payload["overage_per_1000_usd"] = str(self.overage_per_1000_usd)
        payload["entitlements"] = [item.value for item in self.entitlements]
        return payload


_PLAN_POLICY: Final[
    dict[
        str,
        tuple[
            PlanAudience,
            OfferVisibility,
            tuple[EntitlementCode, ...],
            int | None,
        ],
    ]
] = {
    "academic": (
        PlanAudience.ACADEMIC,
        OfferVisibility.PUBLIC_CANDIDATE,
        (
            EntitlementCode.MAESTRO_EXECUTION,
            EntitlementCode.BYOK_PROVIDER_CONNECTION,
            EntitlementCode.STANDARD_SUPPORT,
            EntitlementCode.ACADEMIC_USE,
        ),
        1,
    ),
    "starter": (
        PlanAudience.INDIVIDUAL,
        OfferVisibility.PUBLIC_CANDIDATE,
        (
            EntitlementCode.MAESTRO_EXECUTION,
            EntitlementCode.BYOK_PROVIDER_CONNECTION,
            EntitlementCode.STANDARD_SUPPORT,
        ),
        1,
    ),
    "enterprise_integration_starter": (
        PlanAudience.ENTERPRISE,
        OfferVisibility.ENTERPRISE_SALES,
        (
            EntitlementCode.MAESTRO_EXECUTION,
            EntitlementCode.BYOK_PROVIDER_CONNECTION,
            EntitlementCode.BUSINESS_SUPPORT,
            EntitlementCode.ADVANCED_INTEGRATION,
            EntitlementCode.ENTERPRISE_GOVERNANCE,
        ),
        None,
    ),
    "business": (
        PlanAudience.BUSINESS,
        OfferVisibility.PUBLIC_CANDIDATE,
        (
            EntitlementCode.MAESTRO_EXECUTION,
            EntitlementCode.BYOK_PROVIDER_CONNECTION,
            EntitlementCode.BUSINESS_SUPPORT,
        ),
        None,
    ),
    "enterprise_pilot": (
        PlanAudience.ENTERPRISE,
        OfferVisibility.ENTERPRISE_SALES,
        (
            EntitlementCode.MAESTRO_EXECUTION,
            EntitlementCode.BYOK_PROVIDER_CONNECTION,
            EntitlementCode.BUSINESS_SUPPORT,
            EntitlementCode.ENTERPRISE_GOVERNANCE,
        ),
        None,
    ),
    "enterprise_core": (
        PlanAudience.ENTERPRISE,
        OfferVisibility.ENTERPRISE_SALES,
        (
            EntitlementCode.MAESTRO_EXECUTION,
            EntitlementCode.BYOK_PROVIDER_CONNECTION,
            EntitlementCode.BUSINESS_SUPPORT,
            EntitlementCode.ENTERPRISE_GOVERNANCE,
        ),
        None,
    ),
    "enterprise_scale": (
        PlanAudience.ENTERPRISE,
        OfferVisibility.ENTERPRISE_SALES,
        (
            EntitlementCode.MAESTRO_EXECUTION,
            EntitlementCode.BYOK_PROVIDER_CONNECTION,
            EntitlementCode.BUSINESS_SUPPORT,
            EntitlementCode.ENTERPRISE_GOVERNANCE,
            EntitlementCode.ADVANCED_INTEGRATION,
        ),
        None,
    ),
    "enterprise_strategic": (
        PlanAudience.ENTERPRISE,
        OfferVisibility.CONTRACT_ONLY,
        (
            EntitlementCode.MAESTRO_EXECUTION,
            EntitlementCode.BYOK_PROVIDER_CONNECTION,
            EntitlementCode.BUSINESS_SUPPORT,
            EntitlementCode.ENTERPRISE_GOVERNANCE,
            EntitlementCode.ADVANCED_INTEGRATION,
        ),
        None,
    ),
}


_CANONICAL_PLAN_ORDER: Final[tuple[str, ...]] = (
    "academic",
    "starter",
    "enterprise_integration_starter",
    "business",
    "enterprise_pilot",
    "enterprise_core",
    "enterprise_scale",
    "enterprise_strategic",
)


def _required_selected_value(plan: dict[str, Any], key: str) -> Any:
    if key not in plan:
        raise ValueError(f"Selected-pricing plan is missing required field: {key}")
    return plan[key]


def _selected_contract_values(
    *,
    expected_plan_code: str,
    plan: dict[str, Any],
) -> tuple[int, Decimal, Decimal, Decimal]:
    plan_code = str(_required_selected_value(plan, "plan_id")).strip().lower()
    if plan_code != expected_plan_code:
        raise ValueError(
            "Selected-pricing plan order does not match canonical catalog order: "
            f"{plan_code!r} != {expected_plan_code!r}"
        )

    try:
        included_units = int(_required_selected_value(plan, "monthly_unit_allowance"))
        monthly_price = Decimal(
            str(_required_selected_value(plan, "selected_monthly_price"))
        )
        annual_price = Decimal(
            str(_required_selected_value(plan, "selected_yearly_price"))
        )
        overage_price = Decimal(
            str(
                _required_selected_value(
                    plan,
                    "selected_overage_price_per_1000_units",
                )
            )
        )
    except (TypeError, ValueError, ArithmeticError) as exc:
        raise ValueError(
            f"Selected-pricing numeric fields are invalid for plan: {expected_plan_code}"
        ) from exc

    return included_units, monthly_price, annual_price, overage_price


def build_catalog_plan_contracts() -> tuple[CatalogPlanContract, ...]:
    proposal = build_selected_pricing_proposal()
    plans = proposal["plans"]

    if len(plans) != len(_CANONICAL_PLAN_ORDER):
        raise ValueError(
            "Selected-pricing plan count does not match canonical catalog order: "
            f"{len(plans)} != {len(_CANONICAL_PLAN_ORDER)}"
        )

    contracts: list[CatalogPlanContract] = []
    for code, plan in zip(_CANONICAL_PLAN_ORDER, plans, strict=True):
        included_units, monthly_price, annual_price, overage_price = (
            _selected_contract_values(
                expected_plan_code=code,
                plan=plan,
            )
        )
        audience, visibility, entitlements, seat_limit = _PLAN_POLICY[code]
        contracts.append(
            CatalogPlanContract(
                plan_code=code,
                audience=audience,
                visibility=visibility,
                included_maestro_units=included_units,
                monthly_price_usd=monthly_price,
                annual_price_usd=annual_price,
                overage_per_1000_usd=overage_price,
                entitlements=entitlements,
                seat_limit=seat_limit,
                published=False,
                purchasable=False,
                quota_enforced=False,
            )
        )

    return tuple(contracts)


def build_catalog_contract_bundle() -> dict[str, Any]:
    contracts = build_catalog_plan_contracts()
    return {
        "contract_version": CATALOG_CONTRACT_VERSION,
        "status": CATALOG_STATUS,
        "catalog_publication_approved": CATALOG_PUBLICATION_APPROVED,
        "offer_purchase_enabled": OFFER_PURCHASE_ENABLED,
        "entitlement_grant_enabled": ENTITLEMENT_GRANT_ENABLED,
        "quota_enforcement_enabled": QUOTA_ENFORCEMENT_ENABLED,
        "subscription_migration_enabled": SUBSCRIPTION_MIGRATION_ENABLED,
        "seat_based_enterprise_quotas": SEAT_BASED_ENTERPRISE_QUOTAS,
        "byok_only": BYOK_ONLY,
        "plans": [contract.to_dict() for contract in contracts],
    }
