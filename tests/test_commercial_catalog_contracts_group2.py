from decimal import Decimal

from processual_api.billing.commercial_catalog_contracts import (
    BYOK_ONLY,
    CATALOG_PUBLICATION_APPROVED,
    ENTITLEMENT_GRANT_ENABLED,
    OFFER_PURCHASE_ENABLED,
    QUOTA_ENFORCEMENT_ENABLED,
    SEAT_BASED_ENTERPRISE_QUOTAS,
    SUBSCRIPTION_MIGRATION_ENABLED,
    EntitlementCode,
    PlanAudience,
    build_catalog_contract_bundle,
    build_catalog_plan_contracts,
)


def test_catalog_contracts_cover_all_selected_plans() -> None:
    contracts = build_catalog_plan_contracts()
    assert [item.plan_code for item in contracts] == [
        "academic",
        "starter",
        "enterprise_integration_starter",
        "business",
        "enterprise_pilot",
        "enterprise_core",
        "enterprise_scale",
        "enterprise_strategic",
    ]


def test_catalog_contracts_preserve_selected_prices_and_units() -> None:
    contracts = {item.plan_code: item for item in build_catalog_plan_contracts()}
    assert contracts["academic"].monthly_price_usd == Decimal("29")
    assert contracts["starter"].monthly_price_usd == Decimal("49")
    assert contracts["business"].included_maestro_units == 100_000
    assert contracts["enterprise_pilot"].included_maestro_units == 500_000
    assert contracts["enterprise_core"].included_maestro_units == 1_500_000
    assert contracts["enterprise_scale"].included_maestro_units == 3_000_000
    assert contracts["enterprise_strategic"].included_maestro_units == 5_000_000


def test_enterprise_quotas_are_not_seat_based() -> None:
    enterprise = [item for item in build_catalog_plan_contracts() if item.audience is PlanAudience.ENTERPRISE]
    assert enterprise
    assert all(item.seat_limit is None for item in enterprise)
    assert SEAT_BASED_ENTERPRISE_QUOTAS is False


def test_all_plans_include_execution_and_byok_entitlements() -> None:
    for contract in build_catalog_plan_contracts():
        assert EntitlementCode.MAESTRO_EXECUTION in contract.entitlements
        assert EntitlementCode.BYOK_PROVIDER_CONNECTION in contract.entitlements


def test_catalog_foundation_remains_non_activating() -> None:
    assert CATALOG_PUBLICATION_APPROVED is False
    assert OFFER_PURCHASE_ENABLED is False
    assert ENTITLEMENT_GRANT_ENABLED is False
    assert QUOTA_ENFORCEMENT_ENABLED is False
    assert SUBSCRIPTION_MIGRATION_ENABLED is False
    assert BYOK_ONLY is True

    for contract in build_catalog_plan_contracts():
        assert contract.published is False
        assert contract.purchasable is False
        assert contract.quota_enforced is False


def test_bundle_is_serializable_and_draft_review() -> None:
    bundle = build_catalog_contract_bundle()
    assert bundle["status"] == "draft_review"
    assert bundle["catalog_publication_approved"] is False
    assert bundle["offer_purchase_enabled"] is False
    assert len(bundle["plans"]) == 8
