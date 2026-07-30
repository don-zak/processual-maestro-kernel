"""Commercial entitlement and rollover policy contracts for Group 2.

This module defines review-only entitlement policy. It does not grant units,
mutate balances, activate quota enforcement, or replace the runtime ledger.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Final

from processual_api.billing.commercial_catalog_contracts import (
    build_catalog_plan_contracts,
)

ENTITLEMENT_POLICY_VERSION: Final = "2026-07-group2-entitlement-policy-v1"
ENTITLEMENT_POLICY_STATUS: Final = "draft_review"

ENTITLEMENT_RUNTIME_ENABLED: Final = False
MONTHLY_GRANT_EXECUTION_ENABLED: Final = False
ROLLOVER_ENFORCEMENT_ENABLED: Final = False
BALANCE_MUTATION_ENABLED: Final = False
LEDGER_PERSISTENCE_ENABLED: Final = False
USAGE_RESERVATION_ENABLED: Final = False
USAGE_COMMIT_ENABLED: Final = False

UNITS_ARE_CASH_EQUIVALENT: Final = False
UNITS_OFFSET_SUBSCRIPTION_FEES: Final = False
SEAT_BASED_ENTERPRISE_QUOTAS: Final = False
BALANCE_MAXIMUM_UNITS: Final[int | None] = None


class MonthlyRolloverPolicy(StrEnum):
    """Lifecycle of unused monthly units."""

    PERMANENT_WHILE_SUBSCRIPTION_ACTIVE = (
        "permanent_while_subscription_active"
    )


class PurchasedUnitsRolloverPolicy(StrEnum):
    """Lifecycle of separately purchased Top-Up units."""

    NON_EXPIRING_USAGE_RIGHT = "non_expiring_usage_right"


class OveragePolicy(StrEnum):
    """Permitted behavior after prepaid balance depletion."""

    PREPAID_TOP_UP_ONLY = "prepaid_top_up_only"
    CONTRACTED_ENTERPRISE_OVERAGE = "contracted_enterprise_overage"


@dataclass(frozen=True, slots=True)
class PlanEntitlementPolicy:
    """Review-only entitlement policy for one canonical catalog plan."""

    plan_code: str
    monthly_included_units: int
    monthly_consumption_multiplier: Decimal
    monthly_consumption_cap: int
    daily_consumption_cap: int
    hourly_consumption_cap: int
    per_job_unit_cap: int
    guaranteed_concurrency: int
    maximum_elastic_concurrency: int
    monthly_rollover_policy: MonthlyRolloverPolicy
    purchased_units_rollover_policy: PurchasedUnitsRolloverPolicy
    overage_policy: OveragePolicy
    maximum_balance_units: int | None = BALANCE_MAXIMUM_UNITS
    runtime_enabled: bool = ENTITLEMENT_RUNTIME_ENABLED

    def __post_init__(self) -> None:
        if not self.plan_code.strip():
            raise ValueError("plan_code must not be blank")
        if self.monthly_included_units <= 0:
            raise ValueError("monthly_included_units must be positive")
        if self.monthly_consumption_multiplier < Decimal("1"):
            raise ValueError(
                "monthly_consumption_multiplier must be at least one"
            )
        if self.monthly_consumption_cap < self.monthly_included_units:
            raise ValueError(
                "monthly_consumption_cap must not be below included units"
            )

        positive_fields = (
            self.daily_consumption_cap,
            self.hourly_consumption_cap,
            self.per_job_unit_cap,
            self.guaranteed_concurrency,
            self.maximum_elastic_concurrency,
        )
        if any(value <= 0 for value in positive_fields):
            raise ValueError("operational limits must be positive")
        if self.maximum_elastic_concurrency < self.guaranteed_concurrency:
            raise ValueError(
                "maximum_elastic_concurrency must be at least guaranteed"
            )
        if self.maximum_balance_units is not None:
            raise ValueError(
                "maximum_balance_units must remain unlimited in this policy"
            )
        if self.runtime_enabled:
            raise ValueError(
                "entitlement runtime must remain disabled during draft review"
            )

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["monthly_consumption_multiplier"] = str(
            self.monthly_consumption_multiplier
        )
        payload["monthly_rollover_policy"] = (
            self.monthly_rollover_policy.value
        )
        payload["purchased_units_rollover_policy"] = (
            self.purchased_units_rollover_policy.value
        )
        payload["overage_policy"] = self.overage_policy.value
        return payload


# multiplier, daily cap, hourly cap, per-job cap,
# guaranteed concurrency, maximum elastic concurrency, overage policy
_PLAN_OPERATIONAL_POLICY: Final[
    dict[
        str,
        tuple[
            Decimal,
            int,
            int,
            int,
            int,
            int,
            OveragePolicy,
        ],
    ]
] = {
    "academic": (
        Decimal("2"),
        1_500,
        1_000,
        500,
        1,
        3,
        OveragePolicy.PREPAID_TOP_UP_ONLY,
    ),
    "starter": (
        Decimal("2"),
        3_000,
        2_500,
        1_000,
        2,
        5,
        OveragePolicy.PREPAID_TOP_UP_ONLY,
    ),
    "enterprise_integration_starter": (
        Decimal("2"),
        15_000,
        10_000,
        5_000,
        4,
        10,
        OveragePolicy.PREPAID_TOP_UP_ONLY,
    ),
    "business": (
        Decimal("2.5"),
        30_000,
        25_000,
        10_000,
        8,
        15,
        OveragePolicy.PREPAID_TOP_UP_ONLY,
    ),
    "enterprise_pilot": (
        Decimal("3"),
        150_000,
        100_000,
        50_000,
        15,
        30,
        OveragePolicy.CONTRACTED_ENTERPRISE_OVERAGE,
    ),
    "enterprise_core": (
        Decimal("3"),
        450_000,
        250_000,
        100_000,
        25,
        50,
        OveragePolicy.CONTRACTED_ENTERPRISE_OVERAGE,
    ),
    "enterprise_scale": (
        Decimal("4"),
        900_000,
        500_000,
        250_000,
        35,
        75,
        OveragePolicy.CONTRACTED_ENTERPRISE_OVERAGE,
    ),
    "enterprise_strategic": (
        Decimal("4"),
        1_500_000,
        750_000,
        500_000,
        50,
        100,
        OveragePolicy.CONTRACTED_ENTERPRISE_OVERAGE,
    ),
}


def build_plan_entitlement_policies() -> tuple[PlanEntitlementPolicy, ...]:
    """Build policies from the canonical commercial catalog."""

    catalog = build_catalog_plan_contracts()
    catalog_codes = {plan.plan_code for plan in catalog}
    policy_codes = set(_PLAN_OPERATIONAL_POLICY)

    if catalog_codes != policy_codes:
        missing = sorted(catalog_codes - policy_codes)
        unexpected = sorted(policy_codes - catalog_codes)
        raise ValueError(
            "entitlement policy and catalog plans differ: "
            f"missing={missing}, unexpected={unexpected}"
        )

    policies: list[PlanEntitlementPolicy] = []

    for plan in catalog:
        (
            multiplier,
            daily_cap,
            hourly_cap,
            per_job_cap,
            guaranteed_concurrency,
            maximum_elastic_concurrency,
            overage_policy,
        ) = _PLAN_OPERATIONAL_POLICY[plan.plan_code]

        monthly_cap = int(
            Decimal(plan.included_maestro_units) * multiplier
        )

        policies.append(
            PlanEntitlementPolicy(
                plan_code=plan.plan_code,
                monthly_included_units=plan.included_maestro_units,
                monthly_consumption_multiplier=multiplier,
                monthly_consumption_cap=monthly_cap,
                daily_consumption_cap=daily_cap,
                hourly_consumption_cap=hourly_cap,
                per_job_unit_cap=per_job_cap,
                guaranteed_concurrency=guaranteed_concurrency,
                maximum_elastic_concurrency=(
                    maximum_elastic_concurrency
                ),
                monthly_rollover_policy=(
                    MonthlyRolloverPolicy
                    .PERMANENT_WHILE_SUBSCRIPTION_ACTIVE
                ),
                purchased_units_rollover_policy=(
                    PurchasedUnitsRolloverPolicy
                    .NON_EXPIRING_USAGE_RIGHT
                ),
                overage_policy=overage_policy,
            )
        )

    return tuple(policies)


def entitlement_policy_review_payload() -> dict[str, object]:
    """Return a deterministic review payload without runtime authority."""

    policies = build_plan_entitlement_policies()

    return {
        "version": ENTITLEMENT_POLICY_VERSION,
        "status": ENTITLEMENT_POLICY_STATUS,
        "entitlement_runtime_enabled": ENTITLEMENT_RUNTIME_ENABLED,
        "monthly_grant_execution_enabled": (
            MONTHLY_GRANT_EXECUTION_ENABLED
        ),
        "rollover_enforcement_enabled": ROLLOVER_ENFORCEMENT_ENABLED,
        "balance_mutation_enabled": BALANCE_MUTATION_ENABLED,
        "ledger_persistence_enabled": LEDGER_PERSISTENCE_ENABLED,
        "usage_reservation_enabled": USAGE_RESERVATION_ENABLED,
        "usage_commit_enabled": USAGE_COMMIT_ENABLED,
        "units_are_cash_equivalent": UNITS_ARE_CASH_EQUIVALENT,
        "units_offset_subscription_fees": (
            UNITS_OFFSET_SUBSCRIPTION_FEES
        ),
        "seat_based_enterprise_quotas": (
            SEAT_BASED_ENTERPRISE_QUOTAS
        ),
        "maximum_balance_units": BALANCE_MAXIMUM_UNITS,
        "plans": [policy.to_dict() for policy in policies],
    }


__all__ = [
    "BALANCE_MAXIMUM_UNITS",
    "BALANCE_MUTATION_ENABLED",
    "ENTITLEMENT_POLICY_STATUS",
    "ENTITLEMENT_POLICY_VERSION",
    "ENTITLEMENT_RUNTIME_ENABLED",
    "LEDGER_PERSISTENCE_ENABLED",
    "MONTHLY_GRANT_EXECUTION_ENABLED",
    "MonthlyRolloverPolicy",
    "OveragePolicy",
    "PlanEntitlementPolicy",
    "PurchasedUnitsRolloverPolicy",
    "ROLLOVER_ENFORCEMENT_ENABLED",
    "SEAT_BASED_ENTERPRISE_QUOTAS",
    "UNITS_ARE_CASH_EQUIVALENT",
    "UNITS_OFFSET_SUBSCRIPTION_FEES",
    "USAGE_COMMIT_ENABLED",
    "USAGE_RESERVATION_ENABLED",
    "build_plan_entitlement_policies",
    "entitlement_policy_review_payload",
]
