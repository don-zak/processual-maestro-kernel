from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Final

from processual_api.billing.assessment_plan_fulfillment import (
    assessment_plan_fulfillment_payload,
)
from processual_api.billing.commercial_catalog_contracts import build_catalog_plan_contracts
from processual_api.billing.commercial_quota_top_up_contracts import build_top_up_policies
from processual_api.billing.maestro_group1_selected_pricing import (
    DEFAULT_YEARLY_DISCOUNT_PERCENT,
    SELECTED_MONTHLY_PRICES,
)

ANNUAL_DISCOUNT_PERCENT: Final[Decimal] = DEFAULT_YEARLY_DISCOUNT_PERCENT
ANNUAL_MULTIPLIER: Final[Decimal] = Decimal("1") - (
    ANNUAL_DISCOUNT_PERCENT / Decimal("100")
)

PUBLIC_PLAN_ORDER: Final[tuple[str, ...]] = (
    "academic_individual",
    "academic_institution",
    "starter",
    "business",
    "enterprise_integration_starter",
    "enterprise_pilot",
    "enterprise_core",
    "enterprise_scale",
    "enterprise_strategic",
)

PUBLIC_PRICE_CEILING_PLAN: Final[str] = "enterprise_pilot"

LEGACY_DIRECT_PLAN_ALIASES: Final[dict[str, str]] = {
    "academic": "academic_individual",
}

PLAN_SOURCE_IDS: Final[dict[str, str | None]] = {
    "academic_individual": "academic",
    "academic_institution": None,
    "starter": "starter",
    "business": "business",
    "enterprise_integration_starter": "enterprise_integration_starter",
    "enterprise_pilot": "enterprise_pilot",
    "enterprise_core": "enterprise_core",
    "enterprise_scale": "enterprise_scale",
    "enterprise_strategic": "enterprise_strategic",
}

PLAN_DEFINITIONS: Final[dict[str, dict[str, Any]]] = {
    "academic_individual": {
        "display_name": "Academic Individual",
        "audience": "Students, independent researchers, and individual educators",
        "description": "A focused academic plan for personal research, teaching, and learning workflows.",
        "account_type": "individual",
        "requires_assessment": False,
        "features": [
            "Governed academic and research workflows",
            "Audit visibility and usage reporting",
            "Unlimited members within the included quota",
            "Bring your own provider keys",
        ],
        "trial": {
            "duration_days": 14,
            "success_criteria": [
                "Complete account and email verification.",
                "Connect an approved BYOK provider.",
                "Create and run at least one representative workflow.",
                "Confirm that governance and audit results are visible.",
            ],
        },
    },
    "academic_institution": {
        "display_name": "Academic Institution",
        "audience": "Universities, institutes, laboratories, and educational organizations",
        "description": "An institutional academic offer with shared capacity and organization governance.",
        "account_type": "organization",
        "requires_assessment": True,
        "features": [
            "Shared institutional quota",
            "Unlimited authorized members within the agreed quota",
            "Organization administration and governance controls",
            "Institutional BYOK and onboarding review",
        ],
        "trial": {
            "duration_days": None,
            "success_criteria": [
                "Confirm the institution and authorized administrator.",
                "Define representative educational or research workflows.",
                "Validate institutional BYOK, privacy, and governance requirements.",
                "Agree the evaluation quota and acceptance criteria.",
            ],
        },
    },
    "starter": {
        "display_name": "Starter",
        "audience": "Individuals and small operating teams",
        "description": "For users beginning governed Maestro workflows with a clear included quota.",
        "account_type": "individual",
        "requires_assessment": False,
        "features": [
            "Governed workflow execution",
            "Usage and audit reporting",
            "Unlimited members within the included quota",
            "Bring your own provider keys",
        ],
        "trial": {
            "duration_days": 14,
            "success_criteria": [
                "Complete verification and BYOK setup.",
                "Run a representative workflow successfully.",
                "Confirm usage and governance reporting.",
            ],
        },
    },
    "business": {
        "display_name": "Business",
        "audience": "Organizations requiring higher operational capacity",
        "description": "A higher-capacity plan for governed business workflows and shared operations.",
        "account_type": "organization",
        "requires_assessment": False,
        "features": [
            "Higher shared Maestro quota",
            "Organization administration",
            "Operational reporting and governance",
            "Unlimited members within the included quota",
        ],
        "trial": {
            "duration_days": 30,
            "success_criteria": [
                "Configure organization ownership and BYOK.",
                "Run representative business workflows.",
                "Validate stability, reporting, and governance outcomes.",
            ],
        },
    },
    "enterprise_integration_starter": {
        "display_name": "Enterprise Integration Trial",
        "audience": "Organizations evaluating a governed enterprise integration",
        "description": (
            "A contract-scoped enterprise integration trial tailored to the customer's "
            "requirements and acceptance specification."
        ),
        "account_type": "organization",
        "requires_assessment": True,
        "features": [
            "Customer-specific integration scope",
            "Agreed acceptance specification and success criteria",
            "Governed sandbox evaluation",
            "BYOK, security, and operational readiness review",
        ],
        "trial": {
            "duration_days": 30,
            "termination_policy": "30_days_or_agreed_quota_exhausted",
            "success_criteria": [
                "Approve the integration scope and customer requirements.",
                "Agree the trial quota and acceptance specification.",
                "Run the approved integration scenarios.",
                "Complete security, governance, and operational readiness review.",
            ],
        },
    },
    "enterprise_pilot": {
        "display_name": "Enterprise Pilot",
        "audience": "Organizations running a supervised enterprise pilot",
        "description": "A supervised pilot for validating enterprise operations before deployment.",
        "account_type": "organization",
        "requires_assessment": False,
        "features": [
            "Supervised enterprise pilot",
            "Governance and security review",
            "Acceptance criteria and stabilization planning",
            "Unlimited members within the included quota",
        ],
        "trial": {
            "duration_days": 30,
            "success_criteria": [
                "Complete security, integration, and BYOK review.",
                "Execute the agreed pilot workload.",
                "Meet reliability, governance, and acceptance criteria.",
            ],
        },
    },
    "enterprise_core": {
        "display_name": "Enterprise Core",
        "audience": "Approved enterprise deployments",
        "description": "A tailored enterprise deployment requiring commercial and operating assessment.",
        "account_type": "organization",
        "requires_assessment": True,
        "features": ["Tailored capacity", "Enterprise governance", "Deployment assessment", "BYOK"],
        "trial": {"duration_days": None, "success_criteria": ["Agree deployment and acceptance criteria."]},
    },
    "enterprise_scale": {
        "display_name": "Enterprise Scale",
        "audience": "Larger enterprise rollouts",
        "description": "A scaled deployment requiring capacity, governance, and support review.",
        "account_type": "organization",
        "requires_assessment": True,
        "features": ["Scaled capacity", "Advanced governance", "Operational review", "BYOK"],
        "trial": {"duration_days": None, "success_criteria": ["Agree scale, reliability, and governance criteria."]},
    },
    "enterprise_strategic": {
        "display_name": "Enterprise Strategic",
        "audience": "Strategic deployments with custom operating requirements",
        "description": "A strategic deployment with custom capacity, integration, and support terms.",
        "account_type": "organization",
        "requires_assessment": True,
        "features": ["Strategic capacity", "Custom operating model", "Integration review", "BYOK"],
        "trial": {"duration_days": None, "success_criteria": ["Agree strategic operating and acceptance criteria."]},
    },
}


def _money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _source_plan_id(plan_id: str) -> str | None:
    return PLAN_SOURCE_IDS[plan_id]


def _monthly_price(plan_id: str) -> Decimal | None:
    source_id = _source_plan_id(plan_id)
    if source_id is None:
        return None
    if PLAN_DEFINITIONS[plan_id]["requires_assessment"]:
        return None
    return SELECTED_MONTHLY_PRICES[source_id]


def _annual_price(monthly_price: Decimal | None) -> Decimal | None:
    if monthly_price is None:
        return None
    return monthly_price * Decimal("12") * ANNUAL_MULTIPLIER


def _included_quota(plan_id: str) -> int | None:
    if PLAN_DEFINITIONS[plan_id]["requires_assessment"]:
        return None

    source_id = _source_plan_id(plan_id)
    if source_id is None:
        return None

    catalog = {plan.plan_code: plan for plan in build_catalog_plan_contracts()}
    contract = catalog.get(source_id)
    return None if contract is None else contract.included_maestro_units


def _assessment_public_metadata(plan_id: str) -> dict[str, object]:
    if plan_id != "academic_institution":
        return {}

    fulfillment = assessment_plan_fulfillment_payload(plan_id)
    return {
        "assessment_required": True,
        "entitlement_source_plan_code": fulfillment["entitlement_source_plan_code"],
        "entitlement_baseline_codes": list(fulfillment["entitlement_codes"]),
        "quota_source": "assessment",
        "quota_determined_after_assessment": True,
        "price_sources": ["assessment", "contract"],
        "price_determined_after_assessment": True,
        "activation_mode": "assessment",
        "activation_controlled": True,
    }


def resolve_direct_registration_plan(plan_id: str | None) -> str | None:
    if plan_id is None:
        return None

    normalized = plan_id.strip().lower()
    if not normalized:
        return None

    normalized = LEGACY_DIRECT_PLAN_ALIASES.get(normalized, normalized)

    if normalized not in PUBLIC_PLAN_ORDER:
        raise ValueError("Plan is not available for direct registration.")

    if PLAN_DEFINITIONS[normalized]["requires_assessment"]:
        raise ValueError("Plan requires a commercial assessment.")

    return normalized


def _quota_add_ons(plan_id: str) -> list[dict[str, Any]]:
    if plan_id == "enterprise_integration_starter":
        return []

    source_id = _source_plan_id(plan_id)
    if source_id is None or PLAN_DEFINITIONS[plan_id]["requires_assessment"]:
        return []

    policies = {policy.plan_code: policy for policy in build_top_up_policies()}
    policy = policies.get(source_id)
    if policy is None:
        return []

    return [
        {
            "package_id": f"{plan_id}_quota_bundle",
            "display_name": "Additional Maestro quota",
            "units": policy.bundle_units,
            "price_usd": _money(policy.price_per_bundle_usd),
            "billing_model": "on_demand",
            "recurring": False,
            "annual_discount_percent": 0,
            "minimum_quantity": policy.minimum_bundle_count,
            "maximum_quantity": policy.maximum_bundle_count,
            "rollover_policy": policy.rollover_policy.value,
            "purchase_enabled": policy.purchase_enabled,
            "requires_active_subscription": True,
        }
    ]


def public_plan_journey_catalog() -> dict[str, Any]:
    plans: list[dict[str, Any]] = []

    for position, plan_id in enumerate(PUBLIC_PLAN_ORDER, start=1):
        definition = PLAN_DEFINITIONS[plan_id]
        monthly_price = _monthly_price(plan_id)
        annual_price = _annual_price(monthly_price)
        requires_assessment = bool(definition["requires_assessment"])
        account_type = str(definition["account_type"])

        if requires_assessment:
            action = "request_assessment"
            registration_path = None
        else:
            action = "start_registration"
            registration_path = f"/register/{account_type}"

        plan_payload = {
            "plan_id": plan_id,
            "display_name": definition["display_name"],
            "audience": definition["audience"],
            "description": definition["description"],
            "position": position,
            "account_type": account_type,
            "member_policy": "unlimited_within_quota",
            "included_quota_units": _included_quota(plan_id),
            "monthly_price_usd": _money(monthly_price) if monthly_price is not None else None,
            "annual_price_usd": _money(annual_price) if annual_price is not None else None,
            "annual_discount_percent": (
                int(ANNUAL_DISCOUNT_PERCENT)
                if monthly_price is not None
                else None
            ),
            "price_visibility": "public" if monthly_price is not None else "assessment",
            "requires_assessment": requires_assessment,
            "registration_available": not requires_assessment,
            "registration_path": registration_path,
            "action": action,
            "features": list(definition["features"]),
            "byok": {
                "required": True,
                "provider_cost_included": False,
                "summary": (
                    "Connect and pay your selected providers directly. Maestro covers "
                    "governance, orchestration, monitoring, and the included Maestro quota."
                ),
                "excluded_costs": [
                    "AI model and API provider charges",
                    "Telecom and external service charges",
                    "Customer-side storage and custom integration work",
                ],
            },
            "quota_add_ons": _quota_add_ons(plan_id),
            "quota_add_ons_policy": {
                "purchase_model": "on_demand",
                "recurring": False,
                "annual_discount_applies": False,
                "status": "awaiting_approved_public_package_prices",
            },
            "trial": definition["trial"],
        }
        plan_payload.update(_assessment_public_metadata(plan_id))
        plans.append(plan_payload)

    return {
        "version": "2026-08-commercial-plan-pages-v1",
        "currency": "USD",
        "billing_periods": ["monthly", "annual"],
        "annual_discount_percent": int(ANNUAL_DISCOUNT_PERCENT),
        "annual_discount_scope": "base_plan_only",
        "provider_cost_included": False,
        "checkout_enabled": False,
        "public_price_ceiling_plan": PUBLIC_PRICE_CEILING_PLAN,
        "plans": plans,
    }


__all__ = [
    "ANNUAL_DISCOUNT_PERCENT",
    "PUBLIC_PLAN_ORDER",
    "PUBLIC_PRICE_CEILING_PLAN",
    "public_plan_journey_catalog",
    "resolve_direct_registration_plan",
]
