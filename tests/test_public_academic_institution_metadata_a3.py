from processual_api.billing.assessment_plan_fulfillment import assessment_plan_entitlements
from processual_api.billing.public_plan_journey import public_plan_journey_catalog


def test_academic_institution_public_metadata_is_assessment_authoritative() -> None:
    payload = public_plan_journey_catalog()
    by_id = {plan["plan_id"]: plan for plan in payload["plans"]}
    institution = by_id["academic_institution"]

    assert payload["checkout_enabled"] is False
    assert institution["requires_assessment"] is True
    assert institution["assessment_required"] is True
    assert institution["registration_available"] is False
    assert institution["registration_path"] is None
    assert institution["action"] == "request_assessment"

    assert institution["entitlement_source_plan_code"] == "academic"
    assert institution["entitlement_baseline_codes"] == list(
        assessment_plan_entitlements("academic_institution")
    )

    assert institution["quota_source"] == "assessment"
    assert institution["quota_determined_after_assessment"] is True
    assert institution["included_quota_units"] is None

    assert institution["price_sources"] == ["assessment", "contract"]
    assert institution["price_determined_after_assessment"] is True
    assert institution["monthly_price_usd"] is None
    assert institution["annual_price_usd"] is None

    assert institution["activation_mode"] == "assessment"
    assert institution["activation_controlled"] is True


def test_academic_individual_remains_distinct_from_institution_assessment_metadata() -> None:
    payload = public_plan_journey_catalog()
    by_id = {plan["plan_id"]: plan for plan in payload["plans"]}
    individual = by_id["academic_individual"]

    assert individual["requires_assessment"] is False
    assert individual["registration_available"] is True
    assert individual["action"] == "start_registration"
    assert individual["monthly_price_usd"] is not None
    assert individual["included_quota_units"] is not None

    for assessment_only_key in (
        "assessment_required",
        "entitlement_source_plan_code",
        "entitlement_baseline_codes",
        "quota_source",
        "quota_determined_after_assessment",
        "price_sources",
        "price_determined_after_assessment",
        "activation_mode",
        "activation_controlled",
    ):
        assert assessment_only_key not in individual
