from processual_api.billing.commercial_catalog_contracts import (
    CATALOG_CONTRACT_VERSION,
    CATALOG_STATUS,
    build_catalog_plan_contracts,
)
from processual_api.billing.maestro_group1_selected_pricing import (
    PROVIDER_COST_INCLUDED,
    SELECTED_PROPOSAL_VERSION,
)
from processual_api.billing.pricing_catalog import (
    get_subscription_plan,
    list_subscription_plans,
    public_subscription_catalog,
)
from processual_api.billing.subscription_catalog import (
    public_subscription_catalog as legacy_public_subscription_catalog,
)


def test_public_pricing_catalog_projects_canonical_contracts() -> None:
    contracts = build_catalog_plan_contracts()
    payload = public_subscription_catalog()

    assert payload["catalog_version"] == CATALOG_CONTRACT_VERSION
    assert payload["pricing_version"] == SELECTED_PROPOSAL_VERSION
    assert payload["pricing_status"] == CATALOG_STATUS
    assert payload["billing_policy"] == "byok"
    assert payload["provider_cost_included"] is PROVIDER_COST_INCLUDED
    assert payload["checkout_enabled"] is False
    assert [plan["plan_id"] for plan in payload["plans"]] == [
        contract.plan_code for contract in contracts
    ]

    for plan, contract in zip(payload["plans"], contracts, strict=True):
        assert plan["monthly_price_usd"] == str(contract.monthly_price_usd)
        assert plan["yearly_price_usd"] == str(contract.annual_price_usd)
        assert plan["monthly_unit_allowance"] == contract.included_maestro_units
        assert plan["features"] == [item.value for item in contract.entitlements]
        assert plan["checkout_enabled"] is False
        assert plan["lemon_variant_key_monthly"] is None
        assert plan["lemon_variant_key_yearly"] is None


def test_pricing_catalog_lookup_and_listing_use_canonical_plan_ids() -> None:
    canonical_plan_ids = [
        contract.plan_code for contract in build_catalog_plan_contracts()
    ]

    assert [
        plan["plan_id"]
        for plan in list_subscription_plans(include_unlisted=False)
    ] == canonical_plan_ids
    assert get_subscription_plan("enterprise_core")["plan_id"] == "enterprise_core"
    assert get_subscription_plan("enterprise") is None
    assert get_subscription_plan("developer") is None


def test_legacy_subscription_catalog_is_only_a_compatibility_surface() -> None:
    assert legacy_public_subscription_catalog() == public_subscription_catalog()
