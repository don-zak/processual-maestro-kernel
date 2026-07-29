"""Group 2 commercial catalog and entitlement contracts.

The contracts bind the selected Maestro pricing proposal to neutral catalog,
quota, and entitlement metadata. They do not publish offers, activate checkout,
persist subscriptions, or enforce quotas.
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

_EXPECTED_INCLUDED_UNITS: Final[dict[str, int]] = {
    "academic": 5_000,
    "starter": 10_000,
    "enterprise_integration_starter": 50_000,
    "business": 100_000,
    "enterprise_pilot": 500_000,
    "enterprise_core": 1_500_000,
    "enterprise_scale": 3_000_000,
    "enterprise_strategic": 5_000_000,
}

_EXPECTED_MONTHLY_PRICE_USD: Final[dict[str, Decimal]] = {
    "academic": Decimal("29"),
    "starter": Decimal("49"),
    "enterprise_integration_starter": Decimal("259"),
    "business": Decimal("519"),
    "enterprise_pilot": Decimal("2790"),
    "enterprise_core": Decimal("7890"),
    "enterprise_scale": Decimal("14990"),
    "enterprise_strategic": Decimal("23900"),
}

_EXPECTED_ANNUAL_PRICE_USD: Final[dict[str, Decimal]] = {
    "academic": Decimal("295.80"),
    "starter": Decimal("499.80"),
    "enterprise_integration_starter": Decimal("2641.80"),
    "business": Decimal("5293.80"),
    "enterprise_pilot": Decimal("28458.00"),
    "enterprise_core": Decimal("80478.00"),
    "enterprise_scale": Decimal("152898.00"),
    "enterprise_strategic": Decimal("243780.00"),
}

_EXPECTED_OVERAGE_USD: Final[dict[str, Decimal]] = {
    "academic": Decimal("6.50"),
    "starter": Decimal("5.90"),
    "enterprise_integration_starter": Decimal("6.00"),
    "business": Decimal("6.00"),
    "enterprise_pilot": Decimal("6.50"),
    "enterprise_core": Decimal("6.20"),
    "enterprise_scale": Decimal("5.95"),
    "enterprise_strategic": Decimal("5.75"),
}


def _unique_numeric_value(
    plan: dict[str, Any],
    *,
    expected: Decimal,
    preferred_tokens: tuple[str, ...],
    excluded_tokens: tuple[str, ...] = (),
) -> Any:
    preferred: list[tuple[str, Any]] = []
    fallback: list[tuple[str, Any]] = []

    for key, value in plan.items():
        if isinstance(value, bool):
            continue
        try:
            numeric = Decimal(str(value))
        except Exception:
            continue
        if numeric != expected:
            continue

        normalized = key.lower()
        if any(token in normalized for token in excluded_tokens):
            continue

        fallback.append((key, value))
        if all(token in normalized for token in preferred_tokens):
            preferred.append((key, value))

    matches = preferred if len(preferred) == 1 else fallback
    if len(matches) != 1:
        found = ", ".join(key for key, _ in matches) or "(none)"
        available = ", ".join(sorted(plan))
        raise ValueError(
            f"Unable to resolve unique selected-pricing value {expected}; matches: [{found}]; available: [{available}]"
        )

    return matches[0][1]


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
        expected_units = _EXPECTED_INCLUDED_UNITS[code]
        expected_monthly = _EXPECTED_MONTHLY_PRICE_USD[code]
        expected_annual = _EXPECTED_ANNUAL_PRICE_USD[code]
        expected_overage = _EXPECTED_OVERAGE_USD[code]

        included_units = int(
            _unique_numeric_value(
                plan,
                expected=Decimal(expected_units),
                preferred_tokens=("unit",),
                excluded_tokens=("overage", "price", "cost"),
            )
        )
        monthly_price = Decimal(
            str(
                _unique_numeric_value(
                    plan,
                    expected=expected_monthly,
                    preferred_tokens=("price",),
                    excluded_tokens=("minimum", "calculated", "cost", "annual"),
                )
            )
        )
        annual_price = Decimal(
            str(
                _unique_numeric_value(
                    plan,
                    expected=expected_annual,
                    preferred_tokens=("annual",),
                    excluded_tokens=("minimum", "calculated", "cost"),
                )
            )
        )
        overage_price = Decimal(
            str(
                _unique_numeric_value(
                    plan,
                    expected=expected_overage,
                    preferred_tokens=("overage",),
                )
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
