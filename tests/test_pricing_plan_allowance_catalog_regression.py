from __future__ import annotations

from processual_api.billing.usage_pricing import (
    ENTERPRISE_INTEGRATION_STARTER_UNIT_ALLOWANCE,
    ENTERPRISE_INTEGRATION_UNIT_ALLOWANCE,
    allows_enterprise_integration,
    monthly_unit_allowance,
)


def test_market_positioned_monthly_unit_allowance_catalog():
    expected = {
        "developer": 2_000,
        "internal": 2_000,
        "starter": 10_000,
        "pilot_starter": 10_000,
        "business": 100_000,
        "enterprise_integration_starter": 50_000,
        "enterprise": 500_000,
        "enterprise_integration": 500_000,
    }

    for plan_id, allowance in expected.items():
        assert monthly_unit_allowance(plan_id) == allowance


def test_50k_is_enterprise_integration_starter_not_main_enterprise():
    assert ENTERPRISE_INTEGRATION_STARTER_UNIT_ALLOWANCE == 50_000
    assert ENTERPRISE_INTEGRATION_UNIT_ALLOWANCE == 500_000

    assert monthly_unit_allowance("enterprise_integration_starter") == 50_000
    assert monthly_unit_allowance("enterprise_integration") == 500_000


def test_enterprise_custom_allows_integration_without_fixed_catalog_quota():
    assert allows_enterprise_integration("enterprise_custom") is True
    assert monthly_unit_allowance("enterprise_custom") == 0


def test_enterprise_integration_entitlement_plans_include_starter_and_main():
    assert allows_enterprise_integration("enterprise_integration_starter")
    assert allows_enterprise_integration("enterprise_integration")
    assert allows_enterprise_integration("enterprise")
    assert not allows_enterprise_integration("business")
    assert not allows_enterprise_integration("starter")
