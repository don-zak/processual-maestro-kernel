from __future__ import annotations

from fastapi import Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from processual_api.admin_marketplace.authority import (
    AdminMarketplaceAction,
    require_admin_marketplace_authority,
)
from processual_api.admin_marketplace.errors import AdminMarketplaceAuthorityDeniedError
from processual_api.admin_marketplace.local_tunisia_top_up_router import _uow_factory
from processual_api.admin_marketplace.router import (
    _identity_principal,
    get_admin_marketplace_runtime,
    router,
)
from processual_api.admin_marketplace.runtime import AdminMarketplaceRuntime
from processual_api.admin_marketplace.top_up_production_readiness import (
    evaluate_top_up_production_readiness,
    require_top_up_production_readiness,
)
from processual_api.admin_marketplace.top_up_recovery_scan import (
    scan_top_up_recovery_candidates,
)
from processual_api.auth.session_router import get_identity_user
from processual_api.settings import settings


def _enforce_production_readiness_on_import() -> None:
    if not settings.is_production:
        return
    readiness = evaluate_top_up_production_readiness()
    if not (
        readiness.lemon_purchase_enabled
        or readiness.local_purchase_enabled
        or readiness.local_admin_enabled
    ):
        return
    require_top_up_production_readiness()


_enforce_production_readiness_on_import()


class TopUpOperationsStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    activation_safe: bool
    lemon_purchase_enabled: bool
    local_purchase_enabled: bool
    local_admin_enabled: bool
    blockers: tuple[str, ...]
    recovery_candidate_count: int
    recovery_kinds: dict[str, int]


@router.get(
    "/top-ups/operations/status",
    response_model=TopUpOperationsStatusResponse,
)
async def top_up_operations_status(
    current_user: dict = Depends(get_identity_user),
    runtime: AdminMarketplaceRuntime = Depends(get_admin_marketplace_runtime),
) -> TopUpOperationsStatusResponse:
    try:
        user_id, session_id = _identity_principal(current_user)
        authority = await runtime.authority_resolver.resolve(
            user_id=user_id,
            session_id=session_id,
        )
        require_admin_marketplace_authority(
            context=authority,
            action=AdminMarketplaceAction.VIEW_AUDIT,
        )
        readiness = evaluate_top_up_production_readiness()
        recovery = await scan_top_up_recovery_candidates(
            unit_of_work_factory=_uow_factory,
            limit=200,
        )
    except AdminMarketplaceAuthorityDeniedError as exc:
        raise HTTPException(
            status_code=403,
            detail="Top-up operations status requires platform administrator authority.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Top-up operations status is temporarily unavailable.",
        ) from exc

    kinds: dict[str, int] = {}
    for candidate in recovery.candidates:
        kinds[candidate.kind] = kinds.get(candidate.kind, 0) + 1

    return TopUpOperationsStatusResponse(
        activation_safe=readiness.activation_safe,
        lemon_purchase_enabled=readiness.lemon_purchase_enabled,
        local_purchase_enabled=readiness.local_purchase_enabled,
        local_admin_enabled=readiness.local_admin_enabled,
        blockers=readiness.blockers,
        recovery_candidate_count=recovery.count,
        recovery_kinds=kinds,
    )


__all__ = ["TopUpOperationsStatusResponse"]
