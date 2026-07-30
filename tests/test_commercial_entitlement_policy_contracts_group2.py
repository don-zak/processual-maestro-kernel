from decimal import Decimal

from processual_api.billing.commercial_entitlement_policy_contracts import (
    BALANCE_MAXIMUM_UNITS,
    BALANCE_MUTATION_ENABLED,
    ENTITLEMENT_POLICY_STATUS,
    ENTITLEMENT_RUNTIME_ENABLED,
    LEDGER_PERSISTENCE_ENABLED,
    MONTHLY_GRANT_EXECUTION_ENABLED,
    UNITS_ARE_CASH_EQUIVALENT,
    UNITS_OFFSET_SUBSCRIPTION_FEES,
    USAGE_COMMIT_ENABLED,
    USAGE_RESERVATION_ENABLED,
    MonthlyRolloverPolicy,
    OveragePolicy,
    PurchasedUnitsRolloverPolicy,
    build_plan_entitlement_policies,
    entitlement_policy_review_payload,
)


def test_entitlement_policy_remains_review_only() -> None:
    payload = entitlement_policy_review_payload()

    assert ENTITLEMENT_POLICY_STATUS == "draft_review"
    assert payload["status"] == "draft_review"
    assert ENTITLEMENT_RUNTIME_ENABLED is False
    assert MONTHLY_GRANT_EXECUTION_ENABLED is False
    assert BALANCE_MUTATION_ENABLED is False
    assert LEDGER_PERSISTENCE_ENABLED is False
    assert USAGE_RESERVATION_ENABLED is False
    assert USAGE_COMMIT_ENABLED is False


def test_units_are_usage_rights_not_subscription_credit() -> None:
    assert UNITS_ARE_CASH_EQUIVALENT is False
    assert UNITS_OFFSET_SUBSCRIPTION_FEES is False
    assert BALANCE_MAXIMUM_UNITS is None


def test_all_canonical_plans_have_entitlement_policy() -> None:
    policies = build_plan_entitlement_policies()

    assert [policy.plan_code for policy in policies] == [
        "academic",
        "starter",
        "enterprise_integration_starter",
        "business",
        "enterprise_pilot",
        "enterprise_core",
        "enterprise_scale",
        "enterprise_strategic",
    ]


def test_rollover_policy_preserves_unused_and_purchased_units() -> None:
    for policy in build_plan_entitlement_policies():
        assert (
            policy.monthly_rollover_policy
            is MonthlyRolloverPolicy
            .PERMANENT_WHILE_SUBSCRIPTION_ACTIVE
        )
        assert (
            policy.purchased_units_rollover_policy
            is PurchasedUnitsRolloverPolicy.NON_EXPIRING_USAGE_RIGHT
        )
        assert policy.maximum_balance_units is None


def test_consumption_caps_do_not_delete_owned_balance() -> None:
    for policy in build_plan_entitlement_policies():
        expected_cap = int(
            Decimal(policy.monthly_included_units)
            * policy.monthly_consumption_multiplier
        )

        assert policy.monthly_consumption_cap == expected_cap
        assert (
            policy.monthly_consumption_cap
            >= policy.monthly_included_units
        )
        assert policy.maximum_balance_units is None


def test_enterprise_overage_requires_contract() -> None:
    policies = {
        policy.plan_code: policy
        for policy in build_plan_entitlement_policies()
    }

    for code in (
        "academic",
        "starter",
        "enterprise_integration_starter",
        "business",
    ):
        assert (
            policies[code].overage_policy
            is OveragePolicy.PREPAID_TOP_UP_ONLY
        )

    for code in (
        "enterprise_pilot",
        "enterprise_core",
        "enterprise_scale",
        "enterprise_strategic",
    ):
        assert (
            policies[code].overage_policy
            is OveragePolicy.CONTRACTED_ENTERPRISE_OVERAGE
        )


def test_elastic_concurrency_never_below_guaranteed() -> None:
    for policy in build_plan_entitlement_policies():
        assert (
            policy.maximum_elastic_concurrency
            >= policy.guaranteed_concurrency
        )
