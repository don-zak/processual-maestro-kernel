import json

from processual_api.billing.subscription_catalog import (
    SUBSCRIPTION_CATALOG_VERSION,
    SUBSCRIPTION_PRICING_STATUS,
    get_subscription_plan,
    list_subscription_plans,
    public_subscription_catalog,
)
from processual_api.billing.usage_pricing import (
    BILLING_POLICY,
    PRICING_VERSION,
    PROVIDER_COST_INCLUDED,
    monthly_unit_allowance,
)

SECRET_MARKERS = (
    "lemonsqueezy_api_key",
    "lemonsqueezy_webhook_secret",
    "provider_secret",
    "encrypted_key",
    "api_key",
)


def test_subscription_catalog_metadata_is_draft_byok() -> None:
    payload = public_subscription_catalog()

    assert payload["catalog_version"] == SUBSCRIPTION_CATALOG_VERSION
    assert payload["pricing_version"] == PRICING_VERSION
    assert payload["pricing_status"] == "draft"
    assert SUBSCRIPTION_PRICING_STATUS == "draft"
    assert payload["billing_policy"] == BILLING_POLICY == "byok"
    assert payload["provider_cost_included"] is PROVIDER_COST_INCLUDED is False
    assert payload["checkout_enabled"] is False
    assert payload["plans"]


def test_commercial_subscription_plans_have_allowances_from_usage_pricing() -> None:
    commercial_plans = list_subscription_plans(include_unlisted=False)

    assert {plan["plan_id"] for plan in commercial_plans} == {
        "starter",
        "business",
        "enterprise_integration_starter",
        "enterprise",
    }

    for plan in commercial_plans:
        assert plan["commercially_listed"] is True
        assert plan["monthly_unit_allowance"] == monthly_unit_allowance(plan["plan_id"])
        assert plan["monthly_unit_allowance"] > 0


def test_draft_catalog_does_not_publish_final_prices_or_checkout() -> None:
    for plan in list_subscription_plans():
        assert plan["pricing_status"] == "draft"
        assert plan["price_label"] == "TBD"
        assert plan["monthly_price_usd"] is None
        assert plan["yearly_price_usd"] is None
        assert plan["checkout_enabled"] is False
        assert plan["lemon_variant_key_monthly"] is None
        assert plan["lemon_variant_key_yearly"] is None


def test_get_subscription_plan_returns_known_plan_copy() -> None:
    starter = get_subscription_plan("starter")

    assert starter is not None
    assert starter["plan_id"] == "starter"

    starter["display_name"] = "Mutated"

    fresh_starter = get_subscription_plan("starter")
    assert fresh_starter is not None
    assert fresh_starter["display_name"] == "Starter"


def test_get_subscription_plan_rejects_unknown_plan() -> None:
    assert get_subscription_plan("professional") is None
    assert get_subscription_plan("unknown") is None
    assert get_subscription_plan("") is None


def test_public_subscription_catalog_is_secret_safe() -> None:
    serialized = json.dumps(public_subscription_catalog()).lower()

    for marker in SECRET_MARKERS:
        assert marker not in serialized
