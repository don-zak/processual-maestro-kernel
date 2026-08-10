from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from processual_api.billing.plan_fulfillment_catalog import (
    get_plan_fulfillment_spec,
)

ASSESSMENT_PLAN_FULFILLMENT_VERSION: Final = "2026-08-assessment-plan-fulfillment-v1"


@dataclass(frozen=True, slots=True)
class AssessmentPlanFulfillmentTemplate:
    public_plan_id: str
    entitlement_source_plan_code: str
    quota_binding_mode: str
    price_binding_mode: str
    activation_requires_assessment: bool = True

    def __post_init__(self) -> None:
        if self.quota_binding_mode != "assessment_required":
            raise ValueError("assessment plans must not receive automatic quota binding")
        if self.price_binding_mode != "assessment_required":
            raise ValueError("assessment plans must not receive automatic price binding")
        if not self.activation_requires_assessment:
            raise ValueError("assessment plan activation must require assessment")
        get_plan_fulfillment_spec(self.entitlement_source_plan_code)


_TEMPLATES = {
    "academic_institution": AssessmentPlanFulfillmentTemplate(
        public_plan_id="academic_institution",
        entitlement_source_plan_code="academic",
        quota_binding_mode="assessment_required",
        price_binding_mode="assessment_required",
    ),
}

ASSESSMENT_PLAN_FULFILLMENT_TEMPLATES: Final = MappingProxyType(_TEMPLATES)


def get_assessment_plan_fulfillment_template(
    public_plan_id: str | None,
) -> AssessmentPlanFulfillmentTemplate:
    normalized = str(public_plan_id or "").strip().lower().replace("-", "_")
    try:
        return ASSESSMENT_PLAN_FULFILLMENT_TEMPLATES[normalized]
    except KeyError as exc:
        raise KeyError(
            f"unknown assessment fulfillment plan: {normalized or '(blank)'}"
        ) from exc


def assessment_plan_entitlements(public_plan_id: str | None) -> tuple[str, ...]:
    template = get_assessment_plan_fulfillment_template(public_plan_id)
    source = get_plan_fulfillment_spec(template.entitlement_source_plan_code)
    return source.entitlement_codes


def assessment_plan_fulfillment_payload(public_plan_id: str | None) -> dict[str, object]:
    template = get_assessment_plan_fulfillment_template(public_plan_id)
    return {
        "version": ASSESSMENT_PLAN_FULFILLMENT_VERSION,
        "public_plan_id": template.public_plan_id,
        "entitlement_source_plan_code": template.entitlement_source_plan_code,
        "entitlement_codes": list(assessment_plan_entitlements(public_plan_id)),
        "quota_binding_mode": template.quota_binding_mode,
        "price_binding_mode": template.price_binding_mode,
        "activation_requires_assessment": template.activation_requires_assessment,
        "automatic_quota_units": None,
        "automatic_monthly_price_usd": None,
        "automatic_annual_price_usd": None,
    }


__all__ = [
    "ASSESSMENT_PLAN_FULFILLMENT_TEMPLATES",
    "ASSESSMENT_PLAN_FULFILLMENT_VERSION",
    "AssessmentPlanFulfillmentTemplate",
    "assessment_plan_entitlements",
    "assessment_plan_fulfillment_payload",
    "get_assessment_plan_fulfillment_template",
]
