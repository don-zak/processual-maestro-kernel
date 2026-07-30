from processual_api.billing.commercial_entitlement_policy_contracts import (
    PurchasedUnitsRolloverPolicy,
    build_plan_entitlement_policies,
)
from processual_api.billing.commercial_quota_top_up_contracts import (
    TopUpRolloverPolicy,
    build_top_up_policies,
)


def test_top_up_contract_has_no_billing_cycle_expiration_policy() -> None:
    values = {policy.value for policy in TopUpRolloverPolicy}

    assert "expires_with_billing_cycle" not in values
    assert "non_expiring_usage_right" in values


def test_standard_prepaid_top_up_plans_are_non_expiring() -> None:
    entitlement_policies = {policy.plan_code: policy for policy in build_plan_entitlement_policies()}
    top_up_policies = {policy.plan_code: policy for policy in build_top_up_policies()}

    for plan_code in (
        "academic",
        "starter",
        "business",
    ):
        assert top_up_policies[plan_code].rollover_policy is TopUpRolloverPolicy.NON_EXPIRING_USAGE_RIGHT
        assert (
            entitlement_policies[plan_code].purchased_units_rollover_policy
            is PurchasedUnitsRolloverPolicy.NON_EXPIRING_USAGE_RIGHT
        )


def test_integration_starter_rollover_is_contract_defined() -> None:
    policies = {policy.plan_code: policy for policy in build_top_up_policies()}

    assert policies["enterprise_integration_starter"].rollover_policy is TopUpRolloverPolicy.CONTRACT_DEFINED


def test_enterprise_rollover_is_contract_defined() -> None:
    policies = {policy.plan_code: policy for policy in build_top_up_policies()}

    for plan_code in (
        "enterprise_pilot",
        "enterprise_core",
        "enterprise_scale",
        "enterprise_strategic",
    ):
        assert policies[plan_code].rollover_policy is TopUpRolloverPolicy.CONTRACT_DEFINED


def test_contract_defined_never_implies_cycle_expiration() -> None:
    for policy in build_top_up_policies():
        assert policy.rollover_policy.value != "expires_with_billing_cycle"
