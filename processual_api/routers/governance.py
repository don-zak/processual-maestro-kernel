"""Governance status routes and administrator governance lifecycle."""

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
from processual_api.admin_governance.invitation_runtime import (
    AdministratorInvitationRuntimeUnavailableError,
    build_administrator_invitation_service,
)
from processual_api.admin_governance.invitation_service import (
    AdministratorInvitationCommand,
    AdministratorInvitationConflictError,
    AdministratorInvitationDeniedError,
    AdministratorInvitationService,
)
from processual_api.admin_governance.models import AdministratorPermissionGrant
from processual_api.admin_governance.permission_authority import (
    AdministratorGovernanceAction,
    AdministratorGovernanceAuthorityContext,
    evaluate_administrator_governance_authority,
)
from processual_api.auth.models import IdentityPlatformAuthority
from processual_api.auth.security import require_platform_admin_step_up, require_recent_mfa
from processual_api.db.session import get_session_factory
from processual_api.schemas.governance import (
    AdministratorActivityListResponse,
    AdministratorActivityResponse,
    AdministratorAuthorityResponse,
    AdministratorGovernanceResponse,
    AdministratorInvitationCancellationRequest,
    AdministratorInvitationCancellationResponse,
    AdministratorInvitationIssueRequest,
    AdministratorInvitationIssueResponse,
    AdministratorLifecycleRequest,
    AdministratorLifecycleResponse,
    AdministratorSessionListResponse,
    AdministratorSessionResponse,
    AdministratorSessionRevocationResponse,
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


def _authority_unavailable(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Administrator governance authority unavailable.",
    )


def _authorize_governance_read(
    *,
    context: AdministratorGovernanceAuthorityContext,
    action: AdministratorGovernanceAction,
) -> None:
    if "platform_admin" in context.platform_authorities:
        return
    decision = evaluate_administrator_governance_authority(
        context=context,
        action=action,
    )
    if not decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator governance read denied.",
        )


def get_administrator_governance_read_service() -> AdministratorGovernanceReadService:
    try:
        session_factory = get_session_factory()
    except RuntimeError as exc:
        raise _authority_unavailable(exc) from exc
    return AdministratorGovernanceReadService(session_factory=session_factory)


def get_administrator_invitation_service() -> AdministratorInvitationService:
    try:
        return build_administrator_invitation_service()
    except AdministratorInvitationRuntimeUnavailableError as exc:
        raise _authority_unavailable(exc) from exc


def get_administrator_invitation_lifecycle_service() -> AdministratorInvitationLifecycleService:
    try:
        session_factory = get_session_factory()
    except RuntimeError as exc:
        raise _authority_unavailable(exc) from exc
    return AdministratorInvitationLifecycleService(
        unit_of_work_factory=lambda: SqlAlchemyAdministratorInvitationUnitOfWork(
            session_factory
        )
    )


def get_administrator_lifecycle_service() -> AdministratorLifecycleService:
    try:
        session_factory = get_session_factory()
    except RuntimeError as exc:
        raise _authority_unavailable(exc) from exc
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
        raise _authority_unavailable(exc) from exc

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
        raise _authority_unavailable(exc) from exc
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


@router.get(
    "/activity",
    response_model=AdministratorActivityListResponse,
)
async def list_administrator_governance_activity(
    limit: int = 50,
    authority_context: AdministratorGovernanceAuthorityContext = Depends(
        get_delegated_governance_authority_context
    ),
    service: AdministratorGovernanceReadService = Depends(
        get_administrator_governance_read_service
    ),
) -> AdministratorActivityListResponse:
    _authorize_governance_read(
        context=authority_context,
        action=AdministratorGovernanceAction.VIEW_ACTIVITY,
    )
    try:
        rows = await service.list_activity(limit=limit)
    except Exception as exc:
        raise _authority_unavailable(exc) from exc
    events = tuple(
        AdministratorActivityResponse(
            event_id=row.event_id,
            event_type=row.event_type,
            actor_user_id=row.actor_user_id,
            subject_user_id=row.subject_user_id,
            invitation_id=row.invitation_id,
            permission=row.permission,
            reason=row.reason,
            occurred_at=row.occurred_at,
        )
        for row in rows
    )
    return AdministratorActivityListResponse(events=events, count=len(events))


@router.get(
    "/administrators/{user_id}/sessions",
    response_model=AdministratorSessionListResponse,
)
async def list_administrator_sessions(
    user_id: uuid.UUID,
    authority_context: AdministratorGovernanceAuthorityContext = Depends(
        get_delegated_governance_authority_context
    ),
    service: AdministratorGovernanceReadService = Depends(
        get_administrator_governance_read_service
    ),
) -> AdministratorSessionListResponse:
    _authorize_governance_read(
        context=authority_context,
        action=AdministratorGovernanceAction.VIEW_SESSIONS,
    )
    try:
        rows = await service.list_sessions(user_id=user_id)
    except Exception as exc:
        raise _authority_unavailable(exc) from exc
    sessions = tuple(
        AdministratorSessionResponse(
            session_id=row.session_id,
            user_id=row.user_id,
            authenticated_at=row.authenticated_at,
            mfa_satisfied_at=row.mfa_satisfied_at,
            last_seen_at=row.last_seen_at,
            expires_at=row.expires_at,
            revoked_at=row.revoked_at,
            revoke_reason=row.revoke_reason,
        )
        for row in rows
    )
    return AdministratorSessionListResponse(sessions=sessions, count=len(sessions))


@router.post(
    "/administrator-invitations",
    response_model=AdministratorInvitationIssueResponse,
    status_code=status.HTTP_201_CREATED,
)
async def issue_administrator_invitation(
    payload: AdministratorInvitationIssueRequest,
    current_user: dict = Depends(platform_admin_step_up_dependency),
    service: AdministratorInvitationService = Depends(get_administrator_invitation_service),
) -> AdministratorInvitationIssueResponse:
    try:
        actor_user_id = uuid.UUID(str(current_user["user_id"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform administrator step-up required.",
        ) from exc
    try:
        receipt = await service.issue(
            actor_user_id=actor_user_id,
            command=AdministratorInvitationCommand(
                email=payload.email,
                supervision_level=payload.supervision_level,
                reason=payload.reason,
                expires_in_hours=payload.expires_in_hours,
            ),
            recent_step_up=True,
        )
    except AdministratorInvitationDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator invitation issuance denied.",
        ) from exc
    except AdministratorInvitationConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Administrator invitation cannot be issued.",
        ) from exc
    except Exception as exc:
        raise _authority_unavailable(exc) from exc
    return AdministratorInvitationIssueResponse(
        invitation_id=receipt.invitation_id,
        delivery_outbox_id=receipt.delivery_outbox_id,
        email_normalized=receipt.email_normalized,
        supervision_level=receipt.supervision_level,
        expires_at=receipt.expires_at,
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
        raise _authority_unavailable(exc) from exc
    return AdministratorInvitationCancellationResponse(
        invitation_id=receipt.invitation_id,
        cancelled_by_user_id=receipt.cancelled_by_user_id,
        cancelled_at=receipt.cancelled_at,
        status=receipt.status,
    )


async def _lifecycle_response(coro, *, denied_detail: str, conflict_detail: str):
    try:
        receipt = await coro
    except AdministratorLifecycleDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=denied_detail,
        ) from exc
    except AdministratorLifecycleConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=conflict_detail,
        ) from exc
    except Exception as exc:
        raise _authority_unavailable(exc) from exc
    return receipt


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
    receipt = await _lifecycle_response(
        service.freeze(
            target_user_id=user_id,
            authority_context=authority_context,
            reason=payload.reason,
        ),
        denied_detail="Administrator freeze denied.",
        conflict_detail="Administrator is not freezable.",
    )
    return AdministratorLifecycleResponse(
        user_id=receipt.user_id,
        status=receipt.status,
        occurred_at=receipt.occurred_at,
    )


@router.post(
    "/administrators/{user_id}/restore",
    response_model=AdministratorLifecycleResponse,
)
async def restore_administrator(
    user_id: uuid.UUID,
    payload: AdministratorLifecycleRequest,
    authority_context: AdministratorGovernanceAuthorityContext = Depends(
        get_delegated_governance_authority_context
    ),
    service: AdministratorLifecycleService = Depends(get_administrator_lifecycle_service),
) -> AdministratorLifecycleResponse:
    receipt = await _lifecycle_response(
        service.restore(
            target_user_id=user_id,
            authority_context=authority_context,
            reason=payload.reason,
        ),
        denied_detail="Administrator restore denied.",
        conflict_detail="Administrator is not restorable.",
    )
    return AdministratorLifecycleResponse(
        user_id=receipt.user_id,
        status=receipt.status,
        occurred_at=receipt.occurred_at,
    )


@router.post(
    "/administrators/{user_id}/sessions/{session_id}/revoke",
    response_model=AdministratorSessionRevocationResponse,
)
async def revoke_administrator_session(
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    payload: AdministratorLifecycleRequest,
    authority_context: AdministratorGovernanceAuthorityContext = Depends(
        get_delegated_governance_authority_context
    ),
    service: AdministratorLifecycleService = Depends(get_administrator_lifecycle_service),
) -> AdministratorSessionRevocationResponse:
    receipt = await _lifecycle_response(
        service.revoke_session(
            target_user_id=user_id,
            session_id=session_id,
            authority_context=authority_context,
            reason=payload.reason,
        ),
        denied_detail="Administrator session revocation denied.",
        conflict_detail="Administrator session is not revocable.",
    )
    return AdministratorSessionRevocationResponse(
        user_id=receipt.user_id,
        session_id=receipt.session_id,
        revoked_at=receipt.revoked_at,
    )


__all__ = [
    "cancel_administrator_invitation",
    "delegated_governance_step_up_dependency",
    "freeze_administrator",
    "get_administrator_governance_read_service",
    "get_administrator_invitation_lifecycle_service",
    "get_administrator_invitation_service",
    "get_administrator_lifecycle_service",
    "get_delegated_governance_authority_context",
    "issue_administrator_invitation",
    "list_administrator_governance",
    "list_administrator_governance_activity",
    "list_administrator_sessions",
    "platform_admin_step_up_dependency",
    "restore_administrator",
    "revoke_administrator_session",
    "router",
]
