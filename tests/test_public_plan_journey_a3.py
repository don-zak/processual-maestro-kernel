from processual_api.billing.public_plan_journey import (
    PUBLIC_PLAN_ORDER,
    RETIRED_PUBLIC_ENTERPRISE_PLAN_IDS,
    public_plan_journey_catalog,
    resolve_direct_registration_plan,
)


def test_public_plan_journey_has_expected_order() -> None:
    payload = public_plan_journey_catalog()

    assert [plan["plan_id"] for plan in payload["plans"]] == list(PUBLIC_PLAN_ORDER)
    assert list(PUBLIC_PLAN_ORDER) == [
        "academic_individual",
        "academic_institution",
        "starter",
        "business",
        "enterprise_integration_starter",
        "enterprise_deployment",
    ]


def test_retired_enterprise_tiers_never_return_to_public_catalog() -> None:
    payload = public_plan_journey_catalog()
    plan_ids = {plan["plan_id"] for plan in payload["plans"]}

    assert plan_ids.isdisjoint(RETIRED_PUBLIC_ENTERPRISE_PLAN_IDS)
    assert "developer" not in plan_ids
    assert "internal" not in plan_ids
    assert "pilot_starter" not in plan_ids
    assert "enterprise_integration" not in plan_ids
    assert "academic" not in plan_ids


def test_only_fixed_public_subscription_plans_publish_prices() -> None:
    payload = public_plan_journey_catalog()
    by_id = {plan["plan_id"]: plan for plan in payload["plans"]}

    expected_prices = {
        "academic_individual": "29.00",
        "starter": "49.00",
        "business": "519.00",
    }

    for plan_id, expected_price in expected_prices.items():
        assert by_id[plan_id]["monthly_price_usd"] == expected_price
        assert by_id[plan_id]["registration_available"] is True
        assert by_id[plan_id]["action"] == "start_registration"


def test_assessment_plans_publish_neither_price_nor_direct_registration() -> None:
    payload = public_plan_journey_catalog()
    by_id = {plan["plan_id"]: plan for plan in payload["plans"]}

    for plan_id in (
        "academic_institution",
        "enterprise_integration_starter",
        "enterprise_deployment",
    ):
        assert by_id[plan_id]["monthly_price_usd"] is None
        assert by_id[plan_id]["annual_price_usd"] is None
        assert by_id[plan_id]["requires_assessment"] is True
        assert by_id[plan_id]["registration_available"] is False
        assert by_id[plan_id]["action"] == "request_assessment"


def test_enterprise_trial_absorbs_pilot_and_is_one_month_requirements_based() -> None:
    payload = public_plan_journey_catalog()
    by_id = {plan["plan_id"]: plan for plan in payload["plans"]}
    trial = by_id["enterprise_integration_starter"]

    assert trial["display_name"] == "Enterprise Integration Trial"
    assert trial["commercial_model"] == "requirements_based_evaluation"
    assert trial["trial"]["duration_days"] == 30
    assert trial["trial"]["termination_policy"] == "30_days_or_agreed_quota_exhausted"
    assert trial["included_quota_units"] is None
    assert trial["fixed_public_price"] is False
    assert trial["quota_source"] == "approved_customer_scope"


def test_enterprise_deployment_is_requirements_based_not_a_fixed_tier() -> None:
    payload = public_plan_journey_catalog()
    by_id = {plan["plan_id"]: plan for plan in payload["plans"]}
    deployment = by_id["enterprise_deployment"]

    assert deployment["display_name"] == "Enterprise Deployment"
    assert deployment["commercial_model"] == "requirements_based_contract"
    assert deployment["included_quota_units"] is None
    assert deployment["monthly_price_usd"] is None
    assert deployment["annual_price_usd"] is None
    assert deployment["fixed_public_price"] is False


def test_retired_enterprise_ids_fail_closed_for_direct_registration() -> None:
    for plan_id in RETIRED_PUBLIC_ENTERPRISE_PLAN_IDS:
        try:
            resolve_direct_registration_plan(plan_id)
        except ValueError as exc:
            assert "retired from the public commercial journey" in str(exc)
        else:
            raise AssertionError(f"retired enterprise plan unexpectedly resolved: {plan_id}")


def test_public_plan_journey_contains_six_current_offers() -> None:
    payload = public_plan_journey_catalog()

    assert len(payload["plans"]) == 6
