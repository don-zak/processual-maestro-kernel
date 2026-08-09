import pytest

from processual_api.billing.assessment_activation_preparation import (
    ApprovedAssessmentOutcome,
    AssessmentActivationPreparationError,
    build_assessment_activation_profile,
)
from processual_api.billing.assessment_plan_fulfillment import (
    assessment_plan_entitlements,
)


def _approved_outcome(**overrides):
    values = {
        "assessment_id": "assessment_academic_001",
        "customer_ref": "Institution-ACME",
        "public_plan_id": "academic_institution",
        "approval_status": "approved",
        "approved_quota_units": 125_000,
        "approved_entitlement_codes": assessment_plan_entitlements(
            "academic_institution"
        ),
        "approved_by": "commercial-reviewer",
        "approval_reference": "approval-2026-08-001",
    }
    values.update(overrides)
    return ApprovedAssessmentOutcome(**values)


def test_approved_academic_institution_builds_activation_profile() -> None:
    profile = build_assessment_activation_profile(_approved_outcome())

    assert profile["status"] == "ready_for_subscription_activation"
    assert profile["customer_ref"] == "institution-acme"
    assert profile["public_plan_id"] == "academic_institution"
    assert profile["entitlement_source_plan_code"] == "academic"
    assert profile["approved_quota_units"] == 125_000
    assert profile["entitlement_codes"] == list(
        assessment_plan_entitlements("academic_institution")
    )
    binding_hash = profile["assessment_binding_hash"]
    assert isinstance(binding_hash, str)
    assert len(binding_hash) == 64
    int(binding_hash, 16)
    assert profile["quota_profile_ref"] == f"assessment_quota_{binding_hash[:24]}"
    assert profile["checkout_required"] is False
    assert profile["automatic_price_binding"] is False
    assert profile["production_runtime_connector_approved"] is False


def test_assessment_binding_is_deterministic_for_replay() -> None:
    first = build_assessment_activation_profile(_approved_outcome())
    second = build_assessment_activation_profile(_approved_outcome())

    assert first["assessment_binding_hash"] == second["assessment_binding_hash"]
    assert first["quota_profile_ref"] == second["quota_profile_ref"]


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("customer_ref", "Institution-Other"),
        ("approved_quota_units", 200_000),
        ("approval_reference", "approval-2026-08-002"),
    ],
)
def test_assessment_binding_changes_when_authoritative_decision_changes(
    field: str,
    replacement: object,
) -> None:
    baseline = build_assessment_activation_profile(_approved_outcome())
    changed = build_assessment_activation_profile(
        _approved_outcome(**{field: replacement})
    )

    assert baseline["assessment_binding_hash"] != changed["assessment_binding_hash"]
    assert baseline["quota_profile_ref"] != changed["quota_profile_ref"]


@pytest.mark.parametrize("approval_status", ["pending", "rejected", "revision_requested", ""])
def test_activation_profile_requires_explicit_approval(approval_status: str) -> None:
    with pytest.raises(AssessmentActivationPreparationError):
        build_assessment_activation_profile(
            _approved_outcome(approval_status=approval_status)
        )


@pytest.mark.parametrize("quota", [0, -1, -100])
def test_activation_profile_requires_positive_agreed_quota(quota: int) -> None:
    with pytest.raises(AssessmentActivationPreparationError):
        build_assessment_activation_profile(
            _approved_outcome(approved_quota_units=quota)
        )


def test_activation_profile_rejects_entitlement_expansion() -> None:
    entitlements = assessment_plan_entitlements("academic_institution") + (
        "advanced_integration",
    )

    with pytest.raises(AssessmentActivationPreparationError):
        build_assessment_activation_profile(
            _approved_outcome(approved_entitlement_codes=entitlements)
        )


def test_activation_profile_rejects_entitlement_reduction() -> None:
    entitlements = assessment_plan_entitlements("academic_institution")[:-1]

    with pytest.raises(AssessmentActivationPreparationError):
        build_assessment_activation_profile(
            _approved_outcome(approved_entitlement_codes=entitlements)
        )


def test_unknown_assessment_plan_fails_closed() -> None:
    with pytest.raises(KeyError):
        build_assessment_activation_profile(
            _approved_outcome(public_plan_id="unknown_assessment_plan")
        )


@pytest.mark.parametrize(
    "field",
    ["assessment_id", "customer_ref", "public_plan_id", "approved_by", "approval_reference"],
)
def test_required_assessment_identifiers_cannot_be_blank(field: str) -> None:
    with pytest.raises(AssessmentActivationPreparationError):
        _approved_outcome(**{field: " "})
