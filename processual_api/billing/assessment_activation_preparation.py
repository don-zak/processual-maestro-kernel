from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from processual_api.billing.assessment_plan_fulfillment import (
    assessment_plan_entitlements,
    get_assessment_plan_fulfillment_template,
)

ASSESSMENT_ACTIVATION_PREPARATION_VERSION: Final = (
    "2026-08-assessment-activation-preparation-v1"
)


class AssessmentActivationPreparationError(ValueError):
    """Assessment outcome is not safe to convert into an activation profile."""


@dataclass(frozen=True, slots=True)
class ApprovedAssessmentOutcome:
    assessment_id: str
    public_plan_id: str
    approval_status: str
    approved_quota_units: int
    approved_entitlement_codes: tuple[str, ...]
    approved_by: str
    approval_reference: str

    def __post_init__(self) -> None:
        if not self.assessment_id.strip():
            raise AssessmentActivationPreparationError("assessment_id is required")
        if not self.public_plan_id.strip():
            raise AssessmentActivationPreparationError("public_plan_id is required")
        if not self.approved_by.strip():
            raise AssessmentActivationPreparationError("approved_by is required")
        if not self.approval_reference.strip():
            raise AssessmentActivationPreparationError("approval_reference is required")


def build_assessment_activation_profile(
    outcome: ApprovedAssessmentOutcome,
) -> dict[str, object]:
    template = get_assessment_plan_fulfillment_template(outcome.public_plan_id)

    if outcome.approval_status.strip().lower() != "approved":
        raise AssessmentActivationPreparationError(
            "assessment must be approved before activation preparation"
        )

    if outcome.approved_quota_units <= 0:
        raise AssessmentActivationPreparationError(
            "approved assessment quota must be positive"
        )

    expected_entitlements = assessment_plan_entitlements(template.public_plan_id)
    if tuple(outcome.approved_entitlement_codes) != tuple(expected_entitlements):
        raise AssessmentActivationPreparationError(
            "approved entitlements do not match the assessment plan template"
        )

    return {
        "version": ASSESSMENT_ACTIVATION_PREPARATION_VERSION,
        "status": "ready_for_subscription_activation",
        "assessment_id": outcome.assessment_id.strip(),
        "public_plan_id": template.public_plan_id,
        "entitlement_source_plan_code": template.entitlement_source_plan_code,
        "approved_quota_units": outcome.approved_quota_units,
        "entitlement_codes": list(expected_entitlements),
        "approval": {
            "status": "approved",
            "approved_by": outcome.approved_by.strip(),
            "approval_reference": outcome.approval_reference.strip(),
        },
        "checkout_required": False,
        "automatic_price_binding": False,
        "production_runtime_connector_approved": False,
    }


__all__ = [
    "ASSESSMENT_ACTIVATION_PREPARATION_VERSION",
    "ApprovedAssessmentOutcome",
    "AssessmentActivationPreparationError",
    "build_assessment_activation_profile",
]
