"""Group 2 quota top-up quote contracts.

These contracts define authoritative bundle geometry, derived price previews, and
upgrade guidance. Public purchase exposure remains disabled here for backward
compatibility. Operational purchase activation is a separate server-side
runtime/readiness decision in ``admin_marketplace`` and must not be inferred
from these public-preview flags.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from decimal import Decimal
from enum import StrEnum
from typing import Any, Final

from processual_api.billing.commercial_catalog_contracts import (
    CatalogPlanContract,
    build_catalog_plan_contracts,
)

TOP_UP_CONTRACT_VERSION: Final = "2026-08-group2-top-up-v2"
TOP_UP_STATUS: Final = "public_exposure_disabled"
TOP_UP_AUTHORITY_SCOPE: Final = "quote_policy_only"
TOP_UP_RUNTIME_ACTIVATION_AUTHORITY: Final = "admin_marketplace_top_up_readiness"

# Compatibility/public-exposure flags. They are deliberately not runtime
# activation authority. Runtime purchase routes use their own fail-closed
# feature and readiness gates.
TOP_UP_PURCHASE_ENABLED: Final = False
TOP_UP_CHECKOUT_ENABLED: Final = False
TOP_UP_GRANT_ENABLED: Final = False
TOP_UP_PERSISTENCE_ENABLED: Final = False

TOP_UP_REQUIRES_ACTIVE_SUBSCRIPTION: Final = True
TOP_UP_MULTIPLES_ONLY: Final = True
TOP_UP_SEAT_BASED: Final = False


class TopUpRolloverPolicy(StrEnum):
    EXPIRES_WITH_BILLING_CYCLE = "expires_with_billing_cycle"
    CONTRACT_DEFINED = "contract_defined"


class TopUpPurchaseState(StrEnum):
    READY_FOR_REVIEW = "ready_for_review"
    BELOW_MINIMUM = "below_minimum"
    INVALID_MULTIPLE = "invalid_multiple"
    ABOVE_MAXIMUM = "above_maximum"
    UPGRADE_RECOMMENDED = "upgrade_recommended"
    DISABLED = "disabled"


@dataclass(frozen=True, slots=True)
class TopUpPolicy:
    plan_code: str
    bundle_units: int
    minimum_bundle_count: int
    maximum_bundle_count: int
    price_per_bundle_usd: Decimal
    rollover_policy: TopUpRolloverPolicy
    purchase_enabled: bool

    def __post_init__(self) -> None:
        if not self.plan_code.strip():
            raise ValueError("plan_code must not be blank")
        if self.bundle_units <= 0:
            raise ValueError("bundle_units must be positive")
        if self.minimum_bundle_count <= 0:
            raise ValueError("minimum_bundle_count must be positive")
        if self.maximum_bundle_count < self.minimum_bundle_count:
            raise ValueError("maximum_bundle_count must not be below minimum")
        if self.price_per_bundle_usd <= 0:
            raise ValueError("price_per_bundle_usd must be positive")
        if self.purchase_enabled:
            raise ValueError("public Group 2 top-up exposure must remain disabled")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["price_per_bundle_usd"] = str(self.price_per_bundle_usd)
        payload["rollover_policy"] = self.rollover_policy.value
        return payload


@dataclass(frozen=True, slots=True)
class TopUpQuote:
    plan_code: str
    requested_units: int
    bundle_units: int
    bundle_count: int
    total_units: int
    total_price_usd: Decimal
    state: TopUpPurchaseState
    upgrade_plan_code: str | None
    upgrade_monthly_difference_usd: Decimal | None
    purchase_enabled: bool

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["total_price_usd"] = str(self.total_price_usd)
        payload["state"] = self.state.value
        payload["upgrade_monthly_difference_usd"] = (
            None
            if self.upgrade_monthly_difference_usd is None
            else str(self.upgrade_monthly_difference_usd)
        )
        return payload


_TOP_UP_POLICY_INPUTS: Final[
    dict[str, tuple[int, int, int, TopUpRolloverPolicy]]
] = {
    "academic": (
        5_000,
        1,
        4,
        TopUpRolloverPolicy.EXPIRES_WITH_BILLING_CYCLE,
    ),
    "starter": (
        10_000,
        1,
        8,
        TopUpRolloverPolicy.EXPIRES_WITH_BILLING_CYCLE,
    ),
    "enterprise_integration_starter": (
        25_000,
        1,
        8,
        TopUpRolloverPolicy.CONTRACT_DEFINED,
    ),
    "business": (
        25_000,
        1,
        16,
        TopUpRolloverPolicy.EXPIRES_WITH_BILLING_CYCLE,
    ),
    "enterprise_pilot": (
        100_000,
        1,
        10,
        TopUpRolloverPolicy.CONTRACT_DEFINED,
    ),
    "enterprise_core": (
        250_000,
        1,
        10,
        TopUpRolloverPolicy.CONTRACT_DEFINED,
    ),
    "enterprise_scale": (
        500_000,
        1,
        8,
        TopUpRolloverPolicy.CONTRACT_DEFINED,
    ),
    "enterprise_strategic": (
        500_000,
        1,
        10,
        TopUpRolloverPolicy.CONTRACT_DEFINED,
    ),
}


def _catalog_by_code() -> dict[str, CatalogPlanContract]:
    return {plan.plan_code: plan for plan in build_catalog_plan_contracts()}


def build_top_up_policies() -> tuple[TopUpPolicy, ...]:
    catalog = _catalog_by_code()
    policies: list[TopUpPolicy] = []

    for plan_code, (
        bundle_units,
        minimum_bundle_count,
        maximum_bundle_count,
        rollover_policy,
    ) in _TOP_UP_POLICY_INPUTS.items():
        plan = catalog[plan_code]
        price_per_bundle = (
            plan.overage_per_1000_usd
            * Decimal(bundle_units)
            / Decimal(1_000)
        ).quantize(Decimal("0.01"))

        policies.append(
            TopUpPolicy(
                plan_code=plan_code,
                bundle_units=bundle_units,
                minimum_bundle_count=minimum_bundle_count,
                maximum_bundle_count=maximum_bundle_count,
                price_per_bundle_usd=price_per_bundle,
                rollover_policy=rollover_policy,
                purchase_enabled=False,
            )
        )

    return tuple(policies)


def _next_plan_code(plan_code: str) -> str | None:
    ordered = [
        "academic",
        "starter",
        "business",
        "enterprise_pilot",
        "enterprise_core",
        "enterprise_scale",
        "enterprise_strategic",
    ]
    if plan_code == "enterprise_integration_starter":
        return "business"
    try:
        index = ordered.index(plan_code)
    except ValueError:
        return None
    if index >= len(ordered) - 1:
        return None
    return ordered[index + 1]


def _quote_top_up_base(plan_code: str, requested_units: int) -> TopUpQuote:
    policies = {policy.plan_code: policy for policy in build_top_up_policies()}
    catalog = _catalog_by_code()

    if plan_code not in policies:
        raise ValueError(f"Unknown top-up plan: {plan_code}")
    if requested_units <= 0:
        raise ValueError("requested_units must be positive")

    policy = policies[plan_code]
    minimum_units = policy.bundle_units * policy.minimum_bundle_count
    maximum_units = policy.bundle_units * policy.maximum_bundle_count

    if requested_units < minimum_units:
        state = TopUpPurchaseState.BELOW_MINIMUM
        bundle_count = 0
        total_units = 0
        total_price = Decimal("0.00")
    elif requested_units > maximum_units:
        state = TopUpPurchaseState.ABOVE_MAXIMUM
        bundle_count = 0
        total_units = 0
        total_price = Decimal("0.00")
    elif requested_units % policy.bundle_units != 0:
        state = TopUpPurchaseState.INVALID_MULTIPLE
        bundle_count = 0
        total_units = 0
        total_price = Decimal("0.00")
    else:
        bundle_count = requested_units // policy.bundle_units
        total_units = bundle_count * policy.bundle_units
        total_price = (
            policy.price_per_bundle_usd * Decimal(bundle_count)
        ).quantize(Decimal("0.01"))
        state = TopUpPurchaseState.READY_FOR_REVIEW

    upgrade_plan_code = _next_plan_code(plan_code)
    upgrade_monthly_difference: Decimal | None = None

    if state is TopUpPurchaseState.READY_FOR_REVIEW and upgrade_plan_code is not None:
        current_plan = catalog[plan_code]
        upgrade_plan = catalog[upgrade_plan_code]
        upgrade_monthly_difference = (
            upgrade_plan.monthly_price_usd - current_plan.monthly_price_usd
        ).quantize(Decimal("0.01"))

        if upgrade_monthly_difference > 0 and total_price >= upgrade_monthly_difference:
            state = TopUpPurchaseState.UPGRADE_RECOMMENDED

    return TopUpQuote(
        plan_code=plan_code,
        requested_units=requested_units,
        bundle_units=policy.bundle_units,
        bundle_count=bundle_count,
        total_units=total_units,
        total_price_usd=total_price,
        state=state,
        upgrade_plan_code=upgrade_plan_code,
        upgrade_monthly_difference_usd=upgrade_monthly_difference,
        purchase_enabled=False,
    )


def quote_top_up(plan_code: str, requested_units: int) -> TopUpQuote:
    """Return the public-preview quote without implying runtime activation."""

    quote = _quote_top_up_base(plan_code, requested_units)
    if quote.state is TopUpPurchaseState.READY_FOR_REVIEW:
        return replace(quote, state=TopUpPurchaseState.DISABLED)
    return quote


def quote_top_up_for_runtime(plan_code: str, requested_units: int) -> TopUpQuote:
    """Return authoritative bundle/price validation for guarded runtime flows.

    This function does not activate purchase, checkout, persistence, or grants.
    Callers must independently pass server-side feature and readiness gates.
    ``purchase_enabled`` therefore deliberately remains ``False``.
    """

    return _quote_top_up_base(plan_code, requested_units)


def build_top_up_contract_bundle() -> dict[str, Any]:
    return {
        "contract_version": TOP_UP_CONTRACT_VERSION,
        "status": TOP_UP_STATUS,
        "authority_scope": TOP_UP_AUTHORITY_SCOPE,
        "runtime_activation_authority": TOP_UP_RUNTIME_ACTIVATION_AUTHORITY,
        "purchase_enabled": TOP_UP_PURCHASE_ENABLED,
        "checkout_enabled": TOP_UP_CHECKOUT_ENABLED,
        "grant_enabled": TOP_UP_GRANT_ENABLED,
        "persistence_enabled": TOP_UP_PERSISTENCE_ENABLED,
        "requires_active_subscription": TOP_UP_REQUIRES_ACTIVE_SUBSCRIPTION,
        "multiples_only": TOP_UP_MULTIPLES_ONLY,
        "seat_based": TOP_UP_SEAT_BASED,
        "policies": [policy.to_dict() for policy in build_top_up_policies()],
    }


__all__ = [
    "TOP_UP_AUTHORITY_SCOPE",
    "TOP_UP_CHECKOUT_ENABLED",
    "TOP_UP_CONTRACT_VERSION",
    "TOP_UP_GRANT_ENABLED",
    "TOP_UP_MULTIPLES_ONLY",
    "TOP_UP_PERSISTENCE_ENABLED",
    "TOP_UP_PURCHASE_ENABLED",
    "TOP_UP_REQUIRES_ACTIVE_SUBSCRIPTION",
    "TOP_UP_RUNTIME_ACTIVATION_AUTHORITY",
    "TOP_UP_SEAT_BASED",
    "TOP_UP_STATUS",
    "TopUpPolicy",
    "TopUpPurchaseState",
    "TopUpQuote",
    "TopUpRolloverPolicy",
    "build_top_up_contract_bundle",
    "build_top_up_policies",
    "quote_top_up",
    "quote_top_up_for_runtime",
]
