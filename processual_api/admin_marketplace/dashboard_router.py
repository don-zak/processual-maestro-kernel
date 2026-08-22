from __future__ import annotations

from dataclasses import asdict

from fastapi import Depends, HTTPException

from processual_api.admin_marketplace.dashboard_read_service import (
    AdminMarketplaceDashboardReadService,
)
from processual_api.admin_marketplace.errors import (
    AdminMarketplaceAuthorityDeniedError,
)
from processual_api.admin_marketplace.router import (
    GENERIC_UNAVAILABLE,
    get_admin_marketplace_runtime,
    router,
)
from processual_api.auth.session_router import get_identity_user
from processual_api.db.session import get_session_factory


def get_dashboard_read_service() -> AdminMarketplaceDashboardReadService:
    return AdminMarketplaceDashboardReadService(
        session_factory=get_session_factory(),
    )


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


@router.get("/dashboard", response_model=dict)
async def get_admin_marketplace_dashboard(
    current_user: dict = Depends(get_identity_user),
    runtime=Depends(get_admin_marketplace_runtime),
    service: AdminMarketplaceDashboardReadService = Depends(
        get_dashboard_read_service
    ),
) -> dict[str, object]:
    user_id, session_id = _identity_principal(current_user)
    try:
        authority = await runtime.authority_resolver.resolve(
            user_id=user_id,
            session_id=session_id,
        )
        result = await service.read(authority=authority)
    except AdminMarketplaceAuthorityDeniedError as exc:
        raise HTTPException(
            status_code=403,
            detail="Active platform administrator authority is required.",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=GENERIC_UNAVAILABLE,
        ) from exc
    return asdict(result)


__all__ = [
    "get_admin_marketplace_dashboard",
    "get_dashboard_read_service",
]
