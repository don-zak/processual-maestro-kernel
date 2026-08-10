from pathlib import Path

from processual_api.billing.commercial_catalog_contracts import build_catalog_plan_contracts
from processual_api.billing.maestro_group1_selected_pricing import build_selected_pricing_proposal
from processual_api.billing.public_plan_journey import public_plan_journey_catalog


def test_catalog_contracts_derive_numeric_values_from_selected_pricing_fields() -> None:
    selected = {
        plan["plan_id"]: plan
        for plan in build_selected_pricing_proposal()["plans"]
    }
    contracts = {contract.plan_code: contract for contract in build_catalog_plan_contracts()}

    assert contracts.keys() == selected.keys()
    for plan_code, contract in contracts.items():
        source = selected[plan_code]
        assert contract.included_maestro_units == int(source["monthly_unit_allowance"])
        assert str(contract.monthly_price_usd) == source["selected_monthly_price"]
        assert str(contract.annual_price_usd) == source["selected_yearly_price"]
        assert str(contract.overage_per_1000_usd) == source[
            "selected_overage_price_per_1000_units"
        ]


def test_catalog_contract_module_does_not_shadow_selected_numeric_tables() -> None:
    source = Path(
        "processual_api/billing/commercial_catalog_contracts.py"
    ).read_text(encoding="utf-8")

    for forbidden_name in (
        "_EXPECTED_INCLUDED_UNITS",
        "_EXPECTED_MONTHLY_PRICE_USD",
        "_EXPECTED_ANNUAL_PRICE_USD",
        "_EXPECTED_OVERAGE_USD",
    ):
        assert forbidden_name not in source


def test_academic_institution_does_not_inherit_academic_individual_numeric_price() -> None:
    public = {
        plan["plan_id"]: plan
        for plan in public_plan_journey_catalog()["plans"]
    }
    institution = public["academic_institution"]
    individual = public["academic_individual"]

    assert institution["entitlement_source_plan_code"] == "academic"
    assert institution["price_sources"] == ["assessment", "contract"]
    assert institution["monthly_price_usd"] is None
    assert institution["annual_price_usd"] is None
    assert institution["included_quota_units"] is None

    assert individual["monthly_price_usd"] is not None
    assert individual["included_quota_units"] is not None
    assert institution["monthly_price_usd"] != individual["monthly_price_usd"]
