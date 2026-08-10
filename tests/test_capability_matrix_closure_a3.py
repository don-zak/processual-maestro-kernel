from processual_api.billing.plan_capability_matrix import (
    CapabilityStatus,
    EXECUTION_CAPABILITY_POLICIES,
    TOOL_CAPABILITIES,
    plan_can_execute,
    validate_plan_capability_matrix,
)
from processual_api.billing.plan_fulfillment_catalog import PLAN_FULFILLMENT_SPECS


def test_all_plan_entitlements_resolve_to_capabilities() -> None:
    validate_plan_capability_matrix()

    for plan in PLAN_FULFILLMENT_SPECS.values():
        for entitlement_code in plan.entitlement_codes:
            assert entitlement_code in TOOL_CAPABILITIES


def test_execution_policies_use_customer_capabilities_and_canonical_credits() -> None:
    assert EXECUTION_CAPABILITY_POLICIES

    for policy in EXECUTION_CAPABILITY_POLICIES.values():
        capability = TOOL_CAPABILITIES[policy.capability_code]
        assert capability.customer_executable is True
        assert policy.quota_metric == "credits"
        assert policy.quota_cost > 0


def test_advanced_integrations_remain_sandbox_only() -> None:
    advanced = TOOL_CAPABILITIES["advanced_integration"]

    assert advanced.status is CapabilityStatus.SANDBOX_ONLY
    assert advanced.production_allowed is False
    assert plan_can_execute(
        "enterprise_strategic",
        "advanced_integration",
        require_production=True,
    ) is False


def test_durable_execution_is_not_customer_plan_authority() -> None:
    durable = TOOL_CAPABILITIES["durable_execution_internal"]

    assert durable.status is CapabilityStatus.INTERNAL_ONLY
    assert durable.customer_executable is False
    assert durable.production_allowed is False

    for plan_code, plan in PLAN_FULFILLMENT_SPECS.items():
        assert "durable_execution_internal" not in plan.entitlement_codes
        assert plan_can_execute(plan_code, "durable_execution_internal") is False
