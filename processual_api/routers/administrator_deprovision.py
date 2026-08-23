from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from processual_api.admin_governance.administrator_deprovision_repository import (
    SqlAlchemyAdministratorDeprovisionUnitOfWork,
)
from processual_api.admin_governance.administrator_deprovision_service import (
    AdministratorDeprovisionConflictError,
    AdministratorDeprovisionDeniedError,
    AdministratorDeprovisionService,
)
from processual_api.auth.security import require_platform_admin_step_up
from processual_api.db.session import get_session_factory

router = APIRouter()
platform_admin_deprovision_step_up_dependency = require_platform_admin_step_up()


class AdministratorDeprovisionRequest(BaseModel):
    reason: str = Field(min_length=12, max_length=500)


class AdministratorDeprovisionResponse(BaseModel):
    user_id: uuid.UUID
    status: str
    revoked_permission_count: int
    occurred_at: datetime


def get_administrator_deprovision_service() -> AdministratorDeprovisionService:
    try:
        session_factory = get_session_factory()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Administrator governance authority unavailable.",
        ) from exc
    return AdministratorDeprovisionService(
        unit_of_work_factory=lambda: SqlAlchemyAdministratorDeprovisionUnitOfWork(
            session_factory
        )
    )


@router.post(
    "/administrators/{user_id}/deprovision",
    response_model=AdministratorDeprovisionResponse,
)
async def deprovision_administrator_supervisor(
    user_id: uuid.UUID,
    payload: AdministratorDeprovisionRequest,
    current_user: dict = Depends(platform_admin_deprovision_step_up_dependency),
    service: AdministratorDeprovisionService = Depends(
        get_administrator_deprovision_service
    ),
) -> AdministratorDeprovisionResponse:
    try:
        actor_user_id = uuid.UUID(str(current_user["user_id"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform administrator step-up required.",
        ) from exc

    try:
        receipt = await service.revoke_supervisor_authority(
            actor_user_id=actor_user_id,
            target_user_id=user_id,
            reason=payload.reason,
            recent_step_up=True,
        )
    except AdministratorDeprovisionDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator supervisor deprovision denied.",
        ) from exc
    except AdministratorDeprovisionConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Administrator supervisor authority is not deprovisionable.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Administrator governance authority unavailable.",
        ) from exc

    return AdministratorDeprovisionResponse(
        user_id=receipt.user_id,
        status=receipt.status,
        revoked_permission_count=receipt.revoked_permission_count,
        occurred_at=receipt.occurred_at,
    )


__all__ = [
    "get_administrator_deprovision_service",
    "platform_admin_deprovision_step_up_dependency",
    "router",
]
