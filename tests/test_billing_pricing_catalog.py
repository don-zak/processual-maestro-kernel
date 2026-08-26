from processual_api.billing.commercial_catalog_contracts import (
    build_catalog_plan_contracts,
)
from processual_api.billing.maestro_group1_selected_pricing import (
    PROVIDER_COST_INCLUDED,
)
from processual_api.billing.pricing_catalog import (
    SUBSCRIPTION_CATALOG_VERSION,
    SUBSCRIPTION_PRICING_STATUS,
    get_subscription_plan,
    list_subscription_plans,
    public_subscription_catalog,
)
from processual_api.billing.public_plan_journey import PUBLIC_PLAN_ORDER
from processual_api.billing.subscription_catalog import (
    public_subscription_catalog as legacy_public_subscription_catalog,
)
from processual_api.billing.usage_pricing import PRICING_VERSION


def _canonical_contracts_by_plan():
    return {
        contract.plan_code: contract
        for contract in build_catalog_plan_contracts()
    }


def test_public_pricing_catalog_projects_current_public_journey_without_checkout() -> None:
    payload = public_subscription_catalog()

    assert payload["catalog_version"] == SUBSCRIPTION_CATALOG_VERSION
    assert payload["pricing_version"] == PRICING_VERSION
    assert payload["pricing_status"] == SUBSCRIPTION_PRICING_STATUS == "draft"
    assert payload["billing_policy"] == "byok"
    assert payload["provider_cost_included"] is PROVIDER_COST_INCLUDED is False
    assert payload["checkout_enabled"] is False
    assert tuple(plan["plan_id"] for plan in payload["plans"]) == PUBLIC_PLAN_ORDER

    by_id = {plan["plan_id"]: plan for plan in payload["plans"]}
    for plan_id in ("academic_individual", "starter", "business"):
        plan = by_id[plan_id]
        assert plan["monthly_price_usd"] is not None
        assert plan["yearly_price_usd"] is not None
        assert plan["price_label"].startswith("USD ")
        assert plan["requires_assessment"] is False
        assert plan["checkout_enabled"] is False
        assert plan["lemon_variant_key_monthly"] is None
        assert plan["lemon_variant_key_yearly"] is None

    for plan_id in (
        "academic_institution",
        "enterprise_integration_starter",
        "enterprise_deployment",
    ):
        plan = by_id[plan_id]
        assert plan["monthly_price_usd"] is None
        assert plan["yearly_price_usd"] is None
        assert plan["requires_assessment"] is True
        assert plan["checkout_enabled"] is False
        assert plan["lemon_variant_key_monthly"] is None
        assert plan["lemon_variant_key_yearly"] is None


def test_commercially_listed_compatibility_plans_project_canonical_contract_values() -> None:
    contracts = _canonical_contracts_by_plan()
    commercial_plans = {
        plan["plan_id"]: plan
        for plan in list_subscription_plans(include_unlisted=False)
    }

    assert set(commercial_plans) == {"starter", "business"}

    for plan_id in ("starter", "business"):
        plan = commercial_plans[plan_id]
        contract = contracts[plan_id]
        assert plan["monthly_unit_allowance"] == contract.included_maestro_units
        assert plan["features"] == [item.value for item in contract.entitlements]


def test_legacy_aliases_do_not_expose_new_canonical_tiers_as_separate_plans() -> None:
    enterprise = get_subscription_plan("enterprise")
    enterprise_integration = get_subscription_plan("enterprise_integration")

    assert enterprise is not None
    assert enterprise_integration is not None
    assert enterprise["commercially_listed"] is False
    assert enterprise_integration["commercially_listed"] is False
    assert enterprise["monthly_unit_allowance"] == enterprise_integration[
        "monthly_unit_allowance"
    ]
    assert get_subscription_plan("enterprise_core") is None
    assert get_subscription_plan("enterprise_scale") is None
    assert get_subscription_plan("enterprise_strategic") is None


def test_legacy_subscription_catalog_is_only_a_compatibility_surface() -> None:
    assert legacy_public_subscription_catalog() == public_subscription_catalog()
