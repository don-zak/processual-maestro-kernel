from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from processual_api.admin_governance.administrator_governance_history import (
    AdministratorGovernanceHistoryService,
)
from processual_api.auth.security import require_platform_admin_step_up
from processual_api.db.session import get_session_factory

router = APIRouter()
platform_admin_governance_history_step_up_dependency = require_platform_admin_step_up()


class AdministratorAuthorityHistoryResponse(BaseModel):
    authority: str
    status: str
    granted_by_user_id: uuid.UUID | None
    grant_reason: str
    granted_at: datetime
    revoked_by_user_id: uuid.UUID | None
    revoke_reason: str | None
    revoked_at: datetime | None


class AdministratorPermissionHistoryResponse(BaseModel):
    permission: str
    status: str
    source_invitation_id: uuid.UUID
    granted_by_user_id: uuid.UUID | None
    grant_reason: str
    granted_at: datetime
    revoked_by_user_id: uuid.UUID | None
    revocation_reason: str | None
    revoked_at: datetime | None


class AdministratorGovernanceHistoryResponse(BaseModel):
    user_id: uuid.UUID
    email: str
    display_name: str
    user_status: str
    authorities: tuple[AdministratorAuthorityHistoryResponse, ...]
    permissions: tuple[AdministratorPermissionHistoryResponse, ...]


def get_administrator_governance_history_service() -> AdministratorGovernanceHistoryService:
    try:
        session_factory = get_session_factory()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Administrator governance authority unavailable.",
        ) from exc
    return AdministratorGovernanceHistoryService(session_factory=session_factory)


@router.get(
    "/administrators/{user_id}/authority-history",
    response_model=AdministratorGovernanceHistoryResponse,
)
async def get_administrator_governance_history(
    user_id: uuid.UUID,
    _current_user: dict = Depends(platform_admin_governance_history_step_up_dependency),
    service: AdministratorGovernanceHistoryService = Depends(
        get_administrator_governance_history_service
    ),
) -> AdministratorGovernanceHistoryResponse:
    try:
        history = await service.get_history(user_id=user_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Administrator governance authority unavailable.",
        ) from exc
    if history is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Administrator identity not found.",
        )
    return AdministratorGovernanceHistoryResponse.model_validate(history, from_attributes=True)


__all__ = [
    "get_administrator_governance_history_service",
    "platform_admin_governance_history_step_up_dependency",
    "router",
]
