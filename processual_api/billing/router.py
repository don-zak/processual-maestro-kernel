"""Billing routes backed by authoritative commercial services."""

from __future__ import annotations

import os
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from processual_api.admin_marketplace.lemon_squeezy_secure_webhook_router import (
    install_secure_lemon_squeezy_webhook_route,
)
from processual_api.admin_marketplace.subscription_access import (
    resolve_subscription_access,
)
from processual_api.auth.security import get_current_user
from processual_api.auth.session_router import get_identity_user
from processual_api.billing.direct_checkout_router import (
    router as direct_checkout_router,
)
from processual_api.billing.offer_pricebook import public_offer_pricebook
from processual_api.billing.public_plan_journey import public_plan_journey_catalog
from processual_api.billing.subscription_catalog import public_subscription_catalog
from processual_api.billing.subscription_preparation import (
    build_subscription_preparation,
)
from processual_api.billing.subscription_preparation_repository import (
    SqlAlchemySubscriptionPreparationRepository,
)
from processual_api.billing.unit_cost_assumptions import (
    get_unit_cost_assumptions as build_unit_cost_assumptions,
)
from processual_api.db.session import get_session_factory

router = APIRouter(prefix="/billing", tags=["billing"])
router.routes.extend(direct_checkout_router.routes)

_VARIANTS = {
    "starter": os.environ.get("LS_VARIANT_STARTER", ""),
    "starter_yearly": os.environ.get("LS_VARIANT_STARTER_YEARLY", ""),
    "professional": os.environ.get("LS_VARIANT_PROFESSIONAL", ""),
    "professional_yearly": os.environ.get("LS_VARIANT_PROFESSIONAL_YEARLY", ""),
    "enterprise": os.environ.get("LS_VARIANT_ENTERPRISE", ""),
    "enterprise_yearly": os.environ.get("LS_VARIANT_ENTERPRISE_YEARLY", ""),
}


def _required_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise HTTPException(status_code=503, detail="Billing service is temporarily unavailable.")
    return value


def _identity_customer_ref(current_user: dict) -> str:
    candidate = current_user.get("organization_id") or current_user.get("user_id") or current_user.get("sub")
    try:
        return str(uuid.UUID(str(candidate)))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=403, detail="Billing access denied.") from exc


@router.post("/checkout", response_model=dict)
async def create_checkout(
    body: dict,
    current_user: dict = Depends(get_current_user),
) -> dict[str, object]:
    api_key = _required_environment("LEMONSQUEEZY_API_KEY")
    store_id = _required_environment("LEMONSQUEEZY_STORE_ID")
    success_url = _required_environment("LEMONSQUEEZY_CHECKOUT_SUCCESS_URL")
    cancel_url = _required_environment("LEMONSQUEEZY_CHECKOUT_CANCEL_URL")

    variant_id = str(body.get("variant_id") or "").strip()
    if not variant_id:
        plan = str(body.get("plan") or "professional").strip().lower()
        billing_period = str(body.get("billing") or "monthly").strip().lower()
        variant_key = f"{plan}_yearly" if billing_period == "yearly" else plan
        variant_id = _VARIANTS.get(variant_key, "").strip()
    if not variant_id.isdigit() or not store_id.isdigit():
        raise HTTPException(status_code=400, detail="Invalid checkout request.")

    customer_ref = _identity_customer_ref(current_user)
    email = str(body.get("email") or "").strip()

    try:
        import httpx

        attributes: dict[str, Any] = {
            "store_id": int(store_id),
            "variant_id": int(variant_id),
            "success_url": success_url,
            "cancel_url": cancel_url,
            "custom_data": {"customer_ref": customer_ref},
        }
        if email:
            attributes["customer_email"] = email
        payload = {"data": {"type": "checkouts", "attributes": attributes}}
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                "https://api.lemonsqueezy.com/v1/checkouts",
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Accept": "application/json",
                    "Content-Type": "application/vnd.api+json",
                },
            )
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Billing service is temporarily unavailable.") from exc

    if response.status_code not in {200, 201}:
        raise HTTPException(status_code=502, detail="Payment provider request failed.")
    data = response.json().get("data", {})
    return {
        "url": data.get("attributes", {}).get("url", ""),
        "checkout_id": data.get("id", ""),
    }


@router.get("/portal", response_model=dict)
async def customer_portal(
    current_user: dict = Depends(get_identity_user),
) -> dict[str, object]:
    customer_ref = _identity_customer_ref(current_user)
    try:
        snapshot = await resolve_subscription_access(customer_ref)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Billing service is temporarily unavailable.") from exc
    if snapshot is None:
        raise HTTPException(status_code=404, detail="No active subscription found.")
    raise HTTPException(
        status_code=409,
        detail="Customer portal is unavailable until provider binding is verified.",
    )


@router.get("/subscription-preparation", response_model=dict)
async def get_subscription_preparation(
    current_user: dict = Depends(get_identity_user),
) -> dict[str, object]:
    try:
        user_id = uuid.UUID(str(current_user["user_id"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid identity session.") from exc

    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            return await build_subscription_preparation(
                repository=SqlAlchemySubscriptionPreparationRepository(session),
                user_id=user_id,
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Subscription preparation is unavailable.",
        ) from exc


@router.get("/subscription", response_model=dict)
async def get_billing_subscription(
    current_user: dict = Depends(get_current_user),
) -> dict[str, object]:
    customer_ref = _identity_customer_ref(current_user)
    try:
        snapshot = await resolve_subscription_access(customer_ref)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Billing service is temporarily unavailable.") from exc
    if snapshot is None:
        return {
            "plan": None,
            "status": "inactive",
            "billing_provider": "lemonsqueezy",
            "has_subscription": False,
        }
    return {
        "subscription_id": str(snapshot.subscription_id),
        "plan": snapshot.entitlement_profile_ref,
        "status": snapshot.access_stage,
        "renews_at": snapshot.grace_until,
        "billing_provider": "lemonsqueezy",
        "has_subscription": True,
    }


@router.get("/public-plan-journey")
async def get_public_plan_journey() -> dict[str, object]:
    return public_plan_journey_catalog()


@router.get("/pricing-catalog")
async def get_pricing_catalog() -> dict[str, object]:
    return public_subscription_catalog()


@router.get("/offer-pricebook")
async def get_offer_pricebook() -> dict[str, object]:
    return public_offer_pricebook()


@router.get("/unit-cost-assumptions")
async def get_unit_cost_assumptions() -> dict[str, object]:
    return build_unit_cost_assumptions()


install_secure_lemon_squeezy_webhook_route(router)
