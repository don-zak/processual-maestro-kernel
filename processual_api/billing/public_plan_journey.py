from __future__ import annotations

from decimal import Decimal
from typing import Any, Final

from processual_api.billing.maestro_group1_selected_pricing import (
    SELECTED_MONTHLY_PRICES,
)

PUBLIC_PLAN_ORDER: Final[tuple[str, ...]] = (
    "academic",
    "starter",
    "business",
    "enterprise_integration_starter",
    "enterprise_pilot",
    "enterprise_core",
    "enterprise_scale",
    "enterprise_strategic",
)

PUBLIC_PRICE_CEILING_PLAN: Final[str] = "enterprise_pilot"

PUBLIC_PLAN_NAMES: Final[dict[str, str]] = {
    "academic": "Academic",
    "starter": "Starter",
    "business": "Business",
    "enterprise_integration_starter": "Enterprise Integration Starter",
    "enterprise_pilot": "Enterprise Pilot",
    "enterprise_core": "Enterprise Core",
    "enterprise_scale": "Enterprise Scale",
    "enterprise_strategic": "Enterprise Strategic",
}

PUBLIC_PLAN_DESCRIPTIONS: Final[dict[str, str]] = {
    "academic": ("For academic and research workloads using Maestro."),
    "starter": ("For individuals and small teams starting with Maestro."),
    "business": ("For teams requiring higher operational capacity."),
    "enterprise_integration_starter": ("For organizations beginning a governed integration evaluation."),
    "enterprise_pilot": ("For controlled enterprise pilots with supervised onboarding."),
    "enterprise_core": ("For approved enterprise deployments requiring a tailored assessment."),
    "enterprise_scale": ("For larger enterprise rollouts requiring capacity and governance review."),
    "enterprise_strategic": ("For strategic deployments with custom operating and support requirements."),
}


def _validate_catalog_configuration() -> None:
    configured_plans = set(PUBLIC_PLAN_ORDER)
    priced_plans = set(SELECTED_MONTHLY_PRICES)

    missing_prices = configured_plans - priced_plans
    if missing_prices:
        raise RuntimeError(f"Public plan journey contains plans without selected prices: {sorted(missing_prices)}")

    missing_names = configured_plans - set(PUBLIC_PLAN_NAMES)
    if missing_names:
        raise RuntimeError(f"Public plan journey contains plans without display names: {sorted(missing_names)}")

    missing_descriptions = configured_plans - set(PUBLIC_PLAN_DESCRIPTIONS)
    if missing_descriptions:
        raise RuntimeError(f"Public plan journey contains plans without descriptions: {sorted(missing_descriptions)}")


def _public_price(plan_id: str) -> Decimal | None:
    plan_index = PUBLIC_PLAN_ORDER.index(plan_id)
    ceiling_index = PUBLIC_PLAN_ORDER.index(PUBLIC_PRICE_CEILING_PLAN)

    if plan_index > ceiling_index:
        return None

    return SELECTED_MONTHLY_PRICES[plan_id]


def resolve_direct_registration_plan(plan_id: str | None) -> str | None:
    """Resolve a server-owned public plan for direct registration.

    Missing plans preserve the legacy registration journey. Unknown plans and
    assessment-only plans fail closed. Client-supplied prices are never used.
    """
    if plan_id is None:
        return None

    normalized = plan_id.strip().lower()
    if not normalized:
        return None

    if normalized not in PUBLIC_PLAN_ORDER:
        raise ValueError("Plan is not available for direct registration.")

    if _public_price(normalized) is None:
        raise ValueError("Plan requires a commercial assessment.")

    return normalized


def public_plan_journey_catalog() -> dict[str, Any]:
    _validate_catalog_configuration()

    plans: list[dict[str, Any]] = []

    for position, plan_id in enumerate(PUBLIC_PLAN_ORDER, start=1):
        monthly_price = _public_price(plan_id)
        requires_assessment = monthly_price is None

        plans.append(
            {
                "plan_id": plan_id,
                "display_name": PUBLIC_PLAN_NAMES[plan_id],
                "description": PUBLIC_PLAN_DESCRIPTIONS[plan_id],
                "position": position,
                "monthly_price_usd": (str(monthly_price) if monthly_price is not None else None),
                "price_visibility": ("public" if monthly_price is not None else "assessment"),
                "requires_assessment": requires_assessment,
                "registration_available": not requires_assessment,
                "action": ("start_registration" if not requires_assessment else "request_assessment"),
            }
        )

    return {
        "version": "2026-08-plan-led-registration-v1",
        "currency": "USD",
        "billing_period": "monthly",
        "provider_cost_included": False,
        "checkout_enabled": False,
        "public_price_ceiling_plan": PUBLIC_PRICE_CEILING_PLAN,
        "plans": plans,
    }


__all__ = [
    "PUBLIC_PLAN_ORDER",
    "PUBLIC_PRICE_CEILING_PLAN",
    "public_plan_journey_catalog",
    "resolve_direct_registration_plan",
]
