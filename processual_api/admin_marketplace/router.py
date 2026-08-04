from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from processual_api.admin_marketplace.eligibility_service import (
    AdminMarketplaceEligibilityState,
)
from processual_api.admin_marketplace.errors import (
    AdminMarketplaceAuthorityDeniedError,
)
from processual_api.admin_marketplace.runtime import (
    AdminMarketplaceRuntime,
    AdminMarketplaceRuntimeUnavailableError,
    build_admin_marketplace_runtime,
)
from processual_api.auth.session_router import get_identity_user

GENERIC_UNAVAILABLE = "Admin Marketplace is temporarily unavailable."

router = APIRouter(
    prefix="/admin-marketplace",
    tags=["admin-marketplace"],
)


class AdminMarketplaceEligibilityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_ref: str
    state: AdminMarketplaceEligibilityState
    visible: bool
    country_code: str | None
    maestro_direct_status: str | None
    admin_review_required: bool
    reason_code: str


async def get_admin_marketplace_runtime() -> AdminMarketplaceRuntime:
    try:
        return await build_admin_marketplace_runtime()
    except AdminMarketplaceRuntimeUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail=GENERIC_UNAVAILABLE,
        ) from exc


def _identity_principal(current_user: dict) -> tuple[str, str]:
    try:
        user_id = str(current_user["user_id"]).strip()
        session_id = str(current_user["session_id"]).strip()
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=401,
            detail="Invalid identity session.",
        ) from exc

    if not user_id or not session_id:
        raise HTTPException(
            status_code=401,
            detail="Invalid identity session.",
        )

    return user_id, session_id


@router.get(
    "/eligibility/{customer_ref}",
    response_model=AdminMarketplaceEligibilityResponse,
)
async def get_admin_marketplace_eligibility(
    customer_ref: str,
    current_user: dict = Depends(get_identity_user),
    runtime: AdminMarketplaceRuntime = Depends(
        get_admin_marketplace_runtime,
    ),
) -> AdminMarketplaceEligibilityResponse:
    user_id, session_id = _identity_principal(current_user)

    try:
        authority = await runtime.authority_resolver.resolve(
            user_id=user_id,
            session_id=session_id,
        )
        result = await runtime.eligibility_service.evaluate(
            authority=authority,
            customer_ref=customer_ref,
        )
    except AdminMarketplaceAuthorityDeniedError as exc:
        raise HTTPException(
            status_code=403,
            detail="Active platform administrator authority is required.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid Admin Marketplace eligibility request.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=GENERIC_UNAVAILABLE,
        ) from exc

    return AdminMarketplaceEligibilityResponse(
        customer_ref=result.customer_ref,
        state=result.state,
        visible=result.visible,
        country_code=result.country_code,
        maestro_direct_status=result.maestro_direct_status,
        admin_review_required=result.admin_review_required,
        reason_code=result.reason_code,
    )


__all__ = [
    "AdminMarketplaceEligibilityResponse",
    "GENERIC_UNAVAILABLE",
    "get_admin_marketplace_eligibility",
    "get_admin_marketplace_runtime",
    "router",
]
