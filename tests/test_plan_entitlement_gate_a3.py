import pytest

from processual_api.billing.plan_entitlement_gate import (
    PlanEntitlementDecisionCode,
    PlanEntitlementDeniedError,
    evaluate_plan_entitlement,
    require_plan_entitlement,
)


def test_starter_can_execute_maestro_workflows() -> None:
    decision = evaluate_plan_entitlement("starter", "maestro_execution")

    assert decision.allowed is True
    assert decision.plan_code == "starter"
    assert decision.decision_code is PlanEntitlementDecisionCode.ALLOWED


def test_business_is_not_entitled_to_enterprise_governance() -> None:
    decision = evaluate_plan_entitlement("business", "enterprise_governance")

    assert decision.allowed is False
    assert decision.decision_code is PlanEntitlementDecisionCode.CAPABILITY_NOT_ENTITLED


def test_advanced_integration_is_allowed_only_as_non_production_capability() -> None:
    sandbox = evaluate_plan_entitlement(
        "enterprise_scale",
        "advanced_integration",
    )
    production = evaluate_plan_entitlement(
        "enterprise_scale",
        "advanced_integration",
        require_production=True,
    )

    assert sandbox.allowed is True
    assert production.allowed is False
    assert production.decision_code is (
        PlanEntitlementDecisionCode.CAPABILITY_NOT_PRODUCTION_ALLOWED
    )


def test_non_executable_service_entitlement_is_not_treated_as_runtime_tool() -> None:
    decision = evaluate_plan_entitlement("starter", "standard_support")

    assert decision.allowed is False
    assert decision.decision_code is (
        PlanEntitlementDecisionCode.CAPABILITY_NOT_CUSTOMER_EXECUTABLE
    )


def test_unknown_plan_fails_closed() -> None:
    decision = evaluate_plan_entitlement("unknown-paid-tier", "maestro_execution")

    assert decision.allowed is False
    assert decision.decision_code is PlanEntitlementDecisionCode.UNKNOWN_PLAN


def test_require_plan_entitlement_raises_structured_denial() -> None:
    with pytest.raises(PlanEntitlementDeniedError) as captured:
        require_plan_entitlement(
            "enterprise_integration_starter",
            "advanced_integration",
            require_production=True,
        )

    assert captured.value.decision.allowed is False
    assert captured.value.decision.decision_code is (
        PlanEntitlementDecisionCode.CAPABILITY_NOT_PRODUCTION_ALLOWED
    )


def test_legacy_enterprise_alias_uses_canonical_pilot_entitlements() -> None:
    decision = evaluate_plan_entitlement("enterprise", "enterprise_governance")

    assert decision.allowed is True
    assert decision.plan_code == "enterprise_pilot"
