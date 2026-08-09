from decimal import Decimal

from processual_api.billing.maestro_group1_selected_pricing import (
    DEFAULT_YEARLY_DISCOUNT_PERCENT,
)
from processual_api.billing.public_plan_journey import (
    ANNUAL_DISCOUNT_PERCENT,
    PUBLIC_PLAN_ORDER,
    public_plan_journey_catalog,
    resolve_direct_registration_plan,
)


def test_catalog_separates_academic_individual_and_institution() -> None:
    payload = public_plan_journey_catalog()
    by_id = {plan["plan_id"]: plan for plan in payload["plans"]}

    assert "academic" not in by_id
    assert by_id["academic_individual"]["account_type"] == "individual"
    assert by_id["academic_individual"]["registration_available"] is True
    assert by_id["academic_institution"]["account_type"] == "organization"
    assert by_id["academic_institution"]["requires_assessment"] is True


def test_annual_discount_uses_selected_pricing_authority_on_base_plan() -> None:
    payload = public_plan_journey_catalog()
    multiplier = Decimal("1") - DEFAULT_YEARLY_DISCOUNT_PERCENT / Decimal("100")

    assert ANNUAL_DISCOUNT_PERCENT == DEFAULT_YEARLY_DISCOUNT_PERCENT
    assert payload["annual_discount_percent"] == int(DEFAULT_YEARLY_DISCOUNT_PERCENT)

    for plan in payload["plans"]:
        monthly = plan["monthly_price_usd"]
        annual = plan["annual_price_usd"]
        if monthly is None:
            assert annual is None
            continue

        expected = (Decimal(monthly) * Decimal("12") * multiplier).quantize(Decimal("0.01"))
        assert Decimal(annual) == expected
        assert plan["annual_discount_percent"] == int(DEFAULT_YEARLY_DISCOUNT_PERCENT)


def test_quota_add_ons_are_on_demand_and_never_discounted() -> None:
    payload = public_plan_journey_catalog()

    for plan in payload["plans"]:
        policy = plan["quota_add_ons_policy"]
        assert policy["purchase_model"] == "on_demand"
        assert policy["recurring"] is False
        assert policy["annual_discount_applies"] is False


def test_every_plan_exposes_byok_and_trial_information() -> None:
    payload = public_plan_journey_catalog()

    for plan in payload["plans"]:
        assert plan["member_policy"] == "unlimited_within_quota"
        assert plan["byok"]["required"] is True
        assert plan["byok"]["provider_cost_included"] is False
        assert plan["features"]
        assert plan["trial"]["success_criteria"]


def test_direct_registration_resolver_supports_new_academic_id_and_legacy_alias() -> None:
    assert resolve_direct_registration_plan("academic_individual") == "academic_individual"
    assert resolve_direct_registration_plan("academic") == "academic_individual"


def test_public_order_contains_two_academic_offers() -> None:
    assert PUBLIC_PLAN_ORDER[:2] == ("academic_individual", "academic_institution")


def test_catalog_exposes_top_up_package_prices_without_enabling_purchase() -> None:
    payload = public_plan_journey_catalog()
    by_id = {plan["plan_id"]: plan for plan in payload["plans"]}
    academic = by_id["academic_individual"]["quota_add_ons"][0]
    assert academic["units"] == 5_000
    assert academic["price_usd"] == "32.50"
    assert academic["billing_model"] == "on_demand"
    assert academic["recurring"] is False
    assert academic["annual_discount_percent"] == 0
    assert academic["purchase_enabled"] is False


def test_assessment_plan_does_not_publish_zero_values() -> None:
    payload = public_plan_journey_catalog()
    plan = {item["plan_id"]: item for item in payload["plans"]}["academic_institution"]
    assert plan["included_quota_units"] is None
    assert plan["monthly_price_usd"] is None
    assert plan["annual_price_usd"] is None
    assert plan["quota_add_ons"] == []


def test_included_quota_uses_commercial_catalog_values() -> None:
    payload = public_plan_journey_catalog()
    by_id = {plan["plan_id"]: plan for plan in payload["plans"]}

    assert by_id["academic_individual"]["included_quota_units"] == 5_000
    assert by_id["enterprise_pilot"]["included_quota_units"] == 500_000


def test_enterprise_integration_is_contract_scoped_trial() -> None:
    payload = public_plan_journey_catalog()
    by_id = {plan["plan_id"]: plan for plan in payload["plans"]}
    trial = by_id["enterprise_integration_starter"]

    assert trial["display_name"] == "Enterprise Integration Trial"
    assert trial["requires_assessment"] is True
    assert trial["registration_available"] is False
    assert trial["monthly_price_usd"] is None
    assert trial["annual_price_usd"] is None
    assert trial["included_quota_units"] is None
    assert trial["quota_add_ons"] == []
    assert trial["trial"]["duration_days"] == 30
    assert trial["trial"]["termination_policy"] == "30_days_or_agreed_quota_exhausted"
