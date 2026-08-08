from processual_api.billing.public_plan_journey import (
    PUBLIC_PLAN_ORDER,
    public_plan_journey_catalog,
)


def test_public_plan_journey_has_expected_order() -> None:
    payload = public_plan_journey_catalog()

    assert [plan["plan_id"] for plan in payload["plans"]] == list(PUBLIC_PLAN_ORDER)


def test_public_plan_cards_exclude_internal_plans() -> None:
    payload = public_plan_journey_catalog()
    plan_ids = {plan["plan_id"] for plan in payload["plans"]}

    assert "developer" not in plan_ids
    assert "internal" not in plan_ids
    assert "pilot_starter" not in plan_ids
    assert "enterprise_integration" not in plan_ids
    assert "academic" not in plan_ids


def test_prices_are_public_through_enterprise_pilot() -> None:
    payload = public_plan_journey_catalog()
    by_id = {plan["plan_id"]: plan for plan in payload["plans"]}

    expected_prices = {
        "academic_individual": "29.00",
        "starter": "49.00",
        "business": "519.00",
        "enterprise_pilot": "2790.00",
    }

    for plan_id, expected_price in expected_prices.items():
        assert by_id[plan_id]["monthly_price_usd"] == expected_price
        assert by_id[plan_id]["registration_available"] is True
        assert by_id[plan_id]["action"] == "start_registration"


def test_assessment_plans_do_not_publish_prices_or_direct_registration() -> None:
    payload = public_plan_journey_catalog()
    by_id = {plan["plan_id"]: plan for plan in payload["plans"]}

    for plan_id in (
        "academic_institution",
        "enterprise_integration_starter",
        "enterprise_core",
        "enterprise_scale",
        "enterprise_strategic",
    ):
        assert by_id[plan_id]["monthly_price_usd"] is None
        assert by_id[plan_id]["annual_price_usd"] is None
        assert by_id[plan_id]["requires_assessment"] is True
        assert by_id[plan_id]["registration_available"] is False
        assert by_id[plan_id]["action"] == "request_assessment"


def test_public_plan_journey_contains_nine_plans() -> None:
    payload = public_plan_journey_catalog()

    assert len(payload["plans"]) == 9
