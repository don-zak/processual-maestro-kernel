from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.routing import APIRoute

from processual_api.admin_marketplace.subscription_access import (
    resolve_subscription_access,
)
from processual_api.auth.security import get_current_user
from processual_api.routers.settings import router as settings_router
from processual_api.schemas.settings import SubscriptionInfo

_runtime_router = APIRouter(prefix="/settings", tags=["settings"])


def _customer_ref(current_user: dict) -> str:
    candidate = (
        current_user.get("organization_id")
        or current_user.get("user_id")
        or current_user.get("sub")
    )
    try:
        return str(uuid.UUID(str(candidate)))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=403, detail="Subscription access denied.") from exc


@_runtime_router.get("/subscription", response_model=SubscriptionInfo)
async def get_runtime_subscription(
    current_user: dict = Depends(get_current_user),
) -> SubscriptionInfo:
    customer_ref = _customer_ref(current_user)
    try:
        snapshot = await resolve_subscription_access(customer_ref)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Subscription service is temporarily unavailable.",
        ) from exc

    if snapshot is None:
        return SubscriptionInfo(
            plan="Starter",
            status="inactive",
            stage="expired",
        )

    stage = "expired" if snapshot.access_stage == "terminated" else snapshot.access_stage
    return SubscriptionInfo(
        plan=snapshot.entitlement_profile_ref,
        status=snapshot.access_stage,
        stage=stage,
        renews_at=(
            snapshot.grace_until.isoformat()
            if snapshot.grace_until is not None
            else None
        ),
        suspended_at=(
            snapshot.effective_at.isoformat()
            if snapshot.access_stage in {"suspended", "terminated"}
            else None
        ),
    )


def install_runtime_subscription_route(target_router: APIRouter) -> None:
    target_router.routes[:] = [
        route
        for route in target_router.routes
        if not (
            isinstance(route, APIRoute)
            and route.path == "/settings/subscription"
            and "GET" in route.methods
        )
    ]
    target_router.routes.extend(_runtime_router.routes)


install_runtime_subscription_route(settings_router)
