"""Governance status routes and administrator governance reads."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from processual_api.admin_governance.administrator_lifecycle_service import (
    AdministratorLifecycleConflictError,
    AdministratorLifecycleDeniedError,
    AdministratorLifecycleService,
)
from processual_api.admin_governance.invitation_lifecycle_service import (
    AdministratorInvitationLifecycleConflictError,
    AdministratorInvitationLifecycleDeniedError,
    AdministratorInvitationLifecycleService,
)
from processual_api.admin_governance.invitation_repository import (
    SqlAlchemyAdministratorInvitationUnitOfWork,
)
from processual_api.admin_governance.models import AdministratorPermissionGrant
from processual_api.admin_governance.permission_authority import (
    AdministratorGovernanceAuthorityContext,
)
from processual_api.auth.models import IdentityPlatformAuthority
from processual_api.auth.security import require_platform_admin_step_up, require_recent_mfa
from processual_api.db.session import get_session_factory
from processual_api.schemas.governance import (
    AdministratorAuthorityResponse,
    AdministratorGovernanceResponse,
    AdministratorInvitationCancellationRequest,
    AdministratorInvitationCancellationResponse,
    AdministratorLifecycleRequest,
    AdministratorLifecycleResponse,
)
from processual_api.services.admin_governance_read import (
    AdministratorGovernanceReadService,
)

router = APIRouter(prefix="/governance", tags=["governance"])
platform_admin_step_up_dependency = require_platform_admin_step_up()
delegated_governance_step_up_dependency = require_recent_mfa()


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


def get_administrator_lifecycle_service() -> AdministratorLifecycleService:
    try:
        session_factory = get_session_factory()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Administrator governance authority unavailable.",
        ) from exc

    return AdministratorLifecycleService(
        unit_of_work_factory=lambda: SqlAlchemyAdministratorInvitationUnitOfWork(
            session_factory
        )
    )


async def get_delegated_governance_authority_context(
    current_user: dict = Depends(delegated_governance_step_up_dependency),
) -> AdministratorGovernanceAuthorityContext:
    try:
        user_id = uuid.UUID(str(current_user["user_id"]))
        session_id = str(current_user["session_id"])
        session_factory = get_session_factory()
        async with session_factory() as db_session:
            authorities = tuple(
                (
                    await db_session.scalars(
                        select(IdentityPlatformAuthority.authority).where(
                            IdentityPlatformAuthority.user_id == user_id,
                            IdentityPlatformAuthority.status == "active",
                        )
                    )
                ).all()
            )
            permissions = tuple(
                (
                    await db_session.scalars(
                        select(AdministratorPermissionGrant.permission).where(
                            AdministratorPermissionGrant.user_id == user_id,
                            AdministratorPermissionGrant.status == "active",
                        )
                    )
                ).all()
            )
    except HTTPException:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Delegated governance step-up required.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Administrator governance authority unavailable.",
        ) from exc

    return AdministratorGovernanceAuthorityContext(
        user_id=str(user_id),
        session_id=session_id,
        identity_active=True,
        platform_authorities=frozenset(authorities),
        active_permissions=frozenset(permissions),
        recent_mfa_step_up=True,
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


@router.post(
    "/administrators/{user_id}/freeze",
    response_model=AdministratorLifecycleResponse,
)
async def freeze_administrator(
    user_id: uuid.UUID,
    payload: AdministratorLifecycleRequest,
    authority_context: AdministratorGovernanceAuthorityContext = Depends(
        get_delegated_governance_authority_context
    ),
    service: AdministratorLifecycleService = Depends(get_administrator_lifecycle_service),
) -> AdministratorLifecycleResponse:
    try:
        receipt = await service.freeze(
            target_user_id=user_id,
            authority_context=authority_context,
            reason=payload.reason,
        )
    except AdministratorLifecycleDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator freeze denied.",
        ) from exc
    except AdministratorLifecycleConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Administrator is not freezable.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Administrator governance authority unavailable.",
        ) from exc

    return AdministratorLifecycleResponse(
        user_id=receipt.user_id,
        status=receipt.status,
        occurred_at=receipt.occurred_at,
    )


__all__ = [
    "cancel_administrator_invitation",
    "delegated_governance_step_up_dependency",
    "freeze_administrator",
    "get_administrator_governance_read_service",
    "get_administrator_invitation_lifecycle_service",
    "get_administrator_lifecycle_service",
    "get_delegated_governance_authority_context",
    "list_administrator_governance",
    "platform_admin_step_up_dependency",
    "router",
]
