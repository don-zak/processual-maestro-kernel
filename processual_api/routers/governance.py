"""Governance status routes and administrator governance reads."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from processual_api.admin_governance.invitation_lifecycle_service import (
    AdministratorInvitationLifecycleConflictError,
    AdministratorInvitationLifecycleDeniedError,
    AdministratorInvitationLifecycleService,
)
from processual_api.admin_governance.invitation_repository import (
    SqlAlchemyAdministratorInvitationUnitOfWork,
)
from processual_api.auth.security import require_platform_admin_step_up
from processual_api.db.session import get_session_factory
from processual_api.schemas.governance import (
    AdministratorAuthorityResponse,
    AdministratorGovernanceResponse,
    AdministratorInvitationCancellationRequest,
    AdministratorInvitationCancellationResponse,
)
from processual_api.services.admin_governance_read import (
    AdministratorGovernanceReadService,
)

router = APIRouter(prefix="/governance", tags=["governance"])
platform_admin_step_up_dependency = require_platform_admin_step_up()


@router.get("/status")
async def governance_status():
    return {
        "mode": "controlled_adaptive",
        "active_policies": ["BalancedPolicy", "FastPolicy"],
        "drift_monitoring": True,
        "certification_level": "controlled_ready",
    }


def get_administrator_governance_read_service() -> AdministratorGovernanceReadService:
    try:
        session_factory = get_session_factory()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Administrator governance authority unavailable.",
        ) from exc

    return AdministratorGovernanceReadService(session_factory=session_factory)


def get_administrator_invitation_lifecycle_service() -> AdministratorInvitationLifecycleService:
    try:
        session_factory = get_session_factory()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Administrator governance authority unavailable.",
        ) from exc

    return AdministratorInvitationLifecycleService(
        unit_of_work_factory=lambda: SqlAlchemyAdministratorInvitationUnitOfWork(
            session_factory
        )
    )


@router.get(
    "/administrators",
    response_model=AdministratorGovernanceResponse,
)
async def list_administrator_governance(
    current_user: dict = Depends(platform_admin_step_up_dependency),
    service: AdministratorGovernanceReadService = Depends(
        get_administrator_governance_read_service
    ),
) -> AdministratorGovernanceResponse:
    del current_user

    try:
        administrators = await service.list_administrators()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Administrator governance authority unavailable.",
        ) from exc

    response_rows = tuple(
        AdministratorAuthorityResponse(
            user_id=row.user_id,
            email=row.email,
            display_name=row.display_name,
            user_status=row.user_status,
            authority=row.authority,
            authority_status=row.authority_status,
            granted_at=row.granted_at,
        )
        for row in administrators
    )
    return AdministratorGovernanceResponse(
        administrators=response_rows,
        count=len(response_rows),
    )


@router.post(
    "/administrator-invitations/{invitation_id}/cancel",
    response_model=AdministratorInvitationCancellationResponse,
)
async def cancel_administrator_invitation(
    invitation_id: uuid.UUID,
    payload: AdministratorInvitationCancellationRequest,
    current_user: dict = Depends(platform_admin_step_up_dependency),
    service: AdministratorInvitationLifecycleService = Depends(
        get_administrator_invitation_lifecycle_service
    ),
) -> AdministratorInvitationCancellationResponse:
    try:
        actor_user_id = uuid.UUID(str(current_user["user_id"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform administrator step-up required.",
        ) from exc

    try:
        receipt = await service.cancel(
            invitation_id=invitation_id,
            actor_user_id=actor_user_id,
            reason=payload.reason,
            recent_step_up=True,
        )
    except AdministratorInvitationLifecycleDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator invitation cancellation denied.",
        ) from exc
    except AdministratorInvitationLifecycleConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Administrator invitation is not cancellable.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Administrator governance authority unavailable.",
        ) from exc

    return AdministratorInvitationCancellationResponse(
        invitation_id=receipt.invitation_id,
        cancelled_by_user_id=receipt.cancelled_by_user_id,
        cancelled_at=receipt.cancelled_at,
        status=receipt.status,
    )


__all__ = [
    "cancel_administrator_invitation",
    "get_administrator_governance_read_service",
    "get_administrator_invitation_lifecycle_service",
    "list_administrator_governance",
    "platform_admin_step_up_dependency",
    "router",
]
