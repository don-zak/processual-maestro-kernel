import pytest

from processual_api.billing.assessment_plan_fulfillment import (
    assessment_plan_entitlements,
    assessment_plan_fulfillment_payload,
    get_assessment_plan_fulfillment_template,
)


def test_academic_institution_has_explicit_entitlement_template() -> None:
    template = get_assessment_plan_fulfillment_template("academic_institution")

    assert template.public_plan_id == "academic_institution"
    assert template.entitlement_source_plan_code == "academic"
    assert template.quota_binding_mode == "assessment_required"
    assert template.price_binding_mode == "assessment_required"
    assert template.activation_requires_assessment is True


def test_academic_institution_inherits_academic_runtime_entitlements_only() -> None:
    assert assessment_plan_entitlements("academic_institution") == (
        "maestro_execution",
        "byok_provider_connection",
        "standard_support",
        "academic_use",
    )


def test_academic_institution_never_receives_automatic_price_or_quota() -> None:
    payload = assessment_plan_fulfillment_payload("academic_institution")

    assert payload["automatic_quota_units"] is None
    assert payload["automatic_monthly_price_usd"] is None
    assert payload["automatic_annual_price_usd"] is None
    assert payload["activation_requires_assessment"] is True


def test_unknown_assessment_plan_fails_closed() -> None:
    with pytest.raises(KeyError):
        get_assessment_plan_fulfillment_template("unknown_assessment_plan")
