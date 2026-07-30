"""Public-safe adapter from the governed Group 2 catalog to the legacy UI shape."""

from __future__ import annotations

from typing import Any, Final

from processual_api.billing.commercial_catalog_contracts import (
    build_catalog_contract_bundle,
)

PUBLIC_COMMERCIAL_CATALOG_VERSION: Final = "2026-07-group2-public-catalog-ui-v1"


def _title(plan_code: str) -> str:
    return {
        "academic": "Academic",
        "starter": "Starter",
        "enterprise_integration_starter": ("Enterprise Integration Starter"),
        "business": "Business",
        "enterprise_pilot": "Enterprise Pilot",
        "enterprise_core": "Enterprise Core",
        "enterprise_scale": "Enterprise Scale",
        "enterprise_strategic": "Enterprise Strategic",
    }[plan_code]


def _description(plan_code: str) -> str:
    return {
        "academic": ("For students, researchers, and academic projects needing governed Maestro usage."),
        "starter": ("For individuals and small teams beginning regular Maestro use."),
        "enterprise_integration_starter": ("For controlled evaluation of advanced enterprise integrations."),
        "business": ("For operational teams requiring higher monthly capacity."),
        "enterprise_pilot": ("A controlled enterprise pilot for larger institutional workloads."),
        "enterprise_core": ("Core enterprise capacity for sustained institutional operation."),
        "enterprise_scale": ("High-volume enterprise capacity for large deployments."),
        "enterprise_strategic": ("Strategic capacity for the largest governed deployments."),
    }[plan_code]


def _audience(plan_code: str) -> list[str]:
    return {
        "academic": ["students", "researchers", "academic_projects"],
        "starter": ["individuals", "small_teams"],
        "enterprise_integration_starter": [
            "integration_teams",
            "enterprise_evaluation",
        ],
        "business": ["business_teams", "operations"],
        "enterprise_pilot": ["enterprise_pilot", "institutions"],
        "enterprise_core": ["enterprise", "institutions"],
        "enterprise_scale": ["large_enterprise", "high_volume"],
        "enterprise_strategic": [
            "strategic_enterprise",
            "largest_deployments",
        ],
    }[plan_code]


def public_commercial_subscription_catalog() -> dict[str, Any]:
    """Expose selected prices for review while all activation remains disabled."""

    bundle = build_catalog_contract_bundle()
    plans = []

    for item in bundle["plans"]:
        code = str(item["plan_code"])
        monthly = str(item["monthly_price_usd"])
        annual = str(item["annual_price_usd"])
        overage = str(item["overage_per_1000_usd"])
        units = int(item["included_maestro_units"])

        plans.append(
            {
                "plan_id": code,
                "display_name": _title(code),
                "description": _description(code),
                "audience": _audience(code),
                "commercially_listed": True,
                "pricing_status": "draft_review",
                "price_label": f"${monthly} / month",
                "monthly_price_usd": monthly,
                "annual_price_usd": annual,
                "overage_price_per_1000_units_usd": overage,
                "monthly_unit_allowance": units,
                "billing_policy": "byok",
                "provider_cost_included": False,
                "provider_cost_note": ("AI provider usage is not included. Customers use BYOK."),
                "checkout_enabled": False,
                "published": False,
                "purchasable": False,
                "features": [
                    f"{units:,} Maestro units per month",
                    "Unused units roll over while the subscription is active",
                    "BYOK-only provider access",
                    "Governed entitlement ledger",
                ],
            }
        )

    return {
        "catalog_version": PUBLIC_COMMERCIAL_CATALOG_VERSION,
        "pricing_version": bundle["contract_version"],
        "pricing_status": bundle["status"],
        "billing_policy": "byok",
        "provider_cost_included": False,
        "provider_cost_note": ("AI provider usage is outside the Maestro subscription."),
        "checkout_enabled": False,
        "catalog_publication_approved": False,
        "offer_purchase_enabled": False,
        "quota_enforcement_enabled": False,
        "plans": plans,
    }


__all__ = [
    "PUBLIC_COMMERCIAL_CATALOG_VERSION",
    "public_commercial_subscription_catalog",
]
