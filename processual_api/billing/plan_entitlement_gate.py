from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from processual_api.billing.plan_capability_matrix import (
    CapabilityStatus,
    capabilities_for_plan,
)
from processual_api.billing.plan_fulfillment_catalog import normalize_plan_code


class PlanEntitlementDecisionCode(StrEnum):
    ALLOWED = "allowed"
    UNKNOWN_PLAN = "unknown_plan"
    CAPABILITY_NOT_ENTITLED = "capability_not_entitled"
    CAPABILITY_NOT_CUSTOMER_EXECUTABLE = "capability_not_customer_executable"
    CAPABILITY_NOT_PRODUCTION_ALLOWED = "capability_not_production_allowed"


@dataclass(frozen=True, slots=True)
class PlanEntitlementDecision:
    allowed: bool
    plan_code: str
    capability_code: str
    decision_code: PlanEntitlementDecisionCode
    production_requested: bool


class PlanEntitlementDeniedError(PermissionError):
    def __init__(self, decision: PlanEntitlementDecision) -> None:
        self.decision = decision
        super().__init__(decision.decision_code.value)


def evaluate_plan_entitlement(
    plan_code: str | None,
    capability_code: str,
    *,
    require_production: bool = False,
) -> PlanEntitlementDecision:
    canonical = normalize_plan_code(plan_code)
    capability_id = str(capability_code or "").strip().lower()

    try:
        capabilities = capabilities_for_plan(canonical)
    except KeyError:
        return PlanEntitlementDecision(
            allowed=False,
            plan_code=canonical,
            capability_code=capability_id,
            decision_code=PlanEntitlementDecisionCode.UNKNOWN_PLAN,
            production_requested=require_production,
        )

    matching = next(
        (
            capability
            for capability in capabilities
            if capability.capability_code == capability_id
        ),
        None,
    )
    if matching is None:
        return PlanEntitlementDecision(
            allowed=False,
            plan_code=canonical,
            capability_code=capability_id,
            decision_code=PlanEntitlementDecisionCode.CAPABILITY_NOT_ENTITLED,
            production_requested=require_production,
        )

    if not matching.customer_executable:
        return PlanEntitlementDecision(
            allowed=False,
            plan_code=canonical,
            capability_code=capability_id,
            decision_code=(
                PlanEntitlementDecisionCode.CAPABILITY_NOT_CUSTOMER_EXECUTABLE
            ),
            production_requested=require_production,
        )

    if require_production and not matching.production_allowed:
        return PlanEntitlementDecision(
            allowed=False,
            plan_code=canonical,
            capability_code=capability_id,
            decision_code=(
                PlanEntitlementDecisionCode.CAPABILITY_NOT_PRODUCTION_ALLOWED
            ),
            production_requested=True,
        )

    if matching.status not in {CapabilityStatus.READY, CapabilityStatus.SANDBOX_ONLY}:
        return PlanEntitlementDecision(
            allowed=False,
            plan_code=canonical,
            capability_code=capability_id,
            decision_code=(
                PlanEntitlementDecisionCode.CAPABILITY_NOT_CUSTOMER_EXECUTABLE
            ),
            production_requested=require_production,
        )

    return PlanEntitlementDecision(
        allowed=True,
        plan_code=canonical,
        capability_code=capability_id,
        decision_code=PlanEntitlementDecisionCode.ALLOWED,
        production_requested=require_production,
    )


def require_plan_entitlement(
    plan_code: str | None,
    capability_code: str,
    *,
    require_production: bool = False,
) -> PlanEntitlementDecision:
    decision = evaluate_plan_entitlement(
        plan_code,
        capability_code,
        require_production=require_production,
    )
    if not decision.allowed:
        raise PlanEntitlementDeniedError(decision)
    return decision


__all__ = [
    "PlanEntitlementDecision",
    "PlanEntitlementDecisionCode",
    "PlanEntitlementDeniedError",
    "evaluate_plan_entitlement",
    "require_plan_entitlement",
]
