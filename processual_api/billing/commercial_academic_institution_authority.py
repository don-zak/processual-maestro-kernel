"""Commercial authority for Academic Institution assessment activation.

This module binds the public Academic Institution journey to the existing
assessment fulfillment contract and the central commercial state machine. It
never fabricates checkout, payment, price, quota, or entitlement authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from processual_api.billing.assessment_plan_fulfillment import (
    assessment_plan_entitlements,
    get_assessment_plan_fulfillment_template,
)
from processual_api.billing.commercial_state_machine import (
    CommercialAggregate,
    CommercialTransition,
    validate_commercial_transition,
)

ACADEMIC_INSTITUTION_AUTHORITY_VERSION: Final = (
    "2026-08-b2-academic-institution-authority-v1"
)
ACADEMIC_INSTITUTION_RUNTIME_ACTIVATION_ENABLED: Final = False
ACADEMIC_INSTITUTION_PUBLIC_PLAN_ID: Final = "academic_institution"


@dataclass(frozen=True, slots=True)
class AcademicInstitutionActivationAuthority:
    public_plan_id: str
    current_state: str
    next_state: str
    assessment_reference: str
    actor_reference: str
    approved_quota_units: int | None = None
    approved_price_reference: str | None = None

    def __post_init__(self) -> None:
        normalized_plan = self.public_plan_id.strip().lower().replace("-", "_")
        if normalized_plan != ACADEMIC_INSTITUTION_PUBLIC_PLAN_ID:
            raise ValueError("academic institution authority only accepts academic_institution")
        if not self.assessment_reference.strip():
            raise ValueError("assessment_reference must not be blank")
        if not self.actor_reference.strip():
            raise ValueError("actor_reference must not be blank")
        if self.approved_quota_units is not None and self.approved_quota_units <= 0:
            raise ValueError("approved_quota_units must be positive")
        if self.approved_price_reference is not None and not self.approved_price_reference.strip():
            raise ValueError("approved_price_reference must not be blank")

        template = get_assessment_plan_fulfillment_template(normalized_plan)
        if template.quota_binding_mode != "assessment_required":
            raise ValueError("academic institution quota must remain assessment-bound")
        if template.price_binding_mode != "assessment_required":
            raise ValueError("academic institution price must remain assessment-bound")
        if not template.activation_requires_assessment:
            raise ValueError("academic institution activation must require assessment")

        validate_commercial_transition(
            CommercialTransition(
                aggregate=CommercialAggregate.ASSESSMENT_ACTIVATION,
                current_state=self.current_state,
                next_state=self.next_state,
                operation="academic_institution_assessment",
            )
        )

        if self.next_state.strip().lower() == "activated":
            if self.approved_quota_units is None:
                raise ValueError("activation requires assessment-approved quota")
            if self.approved_price_reference is None:
                raise ValueError("activation requires assessment-approved price reference")

    @property
    def entitlement_codes(self) -> tuple[str, ...]:
        return assessment_plan_entitlements(self.public_plan_id)


def build_academic_institution_authority_status() -> dict[str, object]:
    template = get_assessment_plan_fulfillment_template(
        ACADEMIC_INSTITUTION_PUBLIC_PLAN_ID
    )
    return {
        "version": ACADEMIC_INSTITUTION_AUTHORITY_VERSION,
        "public_plan_id": ACADEMIC_INSTITUTION_PUBLIC_PLAN_ID,
        "runtime_activation_enabled": ACADEMIC_INSTITUTION_RUNTIME_ACTIVATION_ENABLED,
        "activation_requires_assessment": template.activation_requires_assessment,
        "quota_binding_mode": template.quota_binding_mode,
        "price_binding_mode": template.price_binding_mode,
        "automatic_quota_allowed": False,
        "automatic_price_allowed": False,
        "checkout_authority_created": False,
        "payment_authority_created": False,
    }


__all__ = [
    "ACADEMIC_INSTITUTION_AUTHORITY_VERSION",
    "ACADEMIC_INSTITUTION_PUBLIC_PLAN_ID",
    "ACADEMIC_INSTITUTION_RUNTIME_ACTIVATION_ENABLED",
    "AcademicInstitutionActivationAuthority",
    "build_academic_institution_authority_status",
]
