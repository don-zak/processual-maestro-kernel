from processual_api.billing.commercial_public_catalog import (
    public_commercial_subscription_catalog,
)


def test_public_catalog_contains_all_governed_plans() -> None:
    payload = public_commercial_subscription_catalog()
    plans = payload["plans"]

    assert [item["plan_id"] for item in plans] == [
        "academic",
        "starter",
        "enterprise_integration_starter",
        "business",
        "enterprise_pilot",
        "enterprise_core",
        "enterprise_scale",
        "enterprise_strategic",
    ]
    assert plans[0]["monthly_unit_allowance"] == 5_000
    assert plans[0]["price_label"].startswith("$29")


def test_public_catalog_remains_fail_closed() -> None:
    payload = public_commercial_subscription_catalog()

    assert payload["pricing_status"] == "draft_review"
    assert payload["checkout_enabled"] is False
    assert payload["catalog_publication_approved"] is False
    assert payload["offer_purchase_enabled"] is False
    assert payload["quota_enforcement_enabled"] is False
    assert all(plan["checkout_enabled"] is False for plan in payload["plans"])
    assert all(plan["published"] is False for plan in payload["plans"])
    assert all(plan["purchasable"] is False for plan in payload["plans"])


def test_public_catalog_preserves_byok() -> None:
    payload = public_commercial_subscription_catalog()

    assert payload["billing_policy"] == "byok"
    assert payload["provider_cost_included"] is False
    assert all(plan["billing_policy"] == "byok" for plan in payload["plans"])


def test_public_plan_detail_returns_one_listed_plan() -> None:
    from processual_api.billing.commercial_public_catalog import public_commercial_plan_detail

    payload = public_commercial_plan_detail("starter")
    assert payload is not None
    assert payload["plan"]["plan_id"] == "starter"
    assert payload["checkout_enabled"] is False
    assert payload["quota_enforcement_enabled"] is False


def test_public_plan_detail_rejects_unknown_plan() -> None:
    from processual_api.billing.commercial_public_catalog import public_commercial_plan_detail

    assert public_commercial_plan_detail("unknown-plan") is None
