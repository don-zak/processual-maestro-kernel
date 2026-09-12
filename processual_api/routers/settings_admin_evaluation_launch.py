"""Platform-admin issuance for External Evaluation workspace launch tickets."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from fastapi import Depends, HTTPException, Request, status

from processual_api.auth.platform_admin_authority import require_active_platform_admin
from processual_api.auth.security import get_current_user
from processual_api.services.evaluation_launch_gate import (
    EvaluationLaunchGateError,
    issue_evaluation_launch_ticket,
)

from . import settings as settings_module


async def _require_platform_admin(
    request: Request,
    current_user: dict[str, Any],
) -> None:
    await require_active_platform_admin(current_user, request)


def _owner_user_id(current_user: dict[str, Any]) -> str:
    return str(current_user.get("sub") or current_user.get("user_id") or "default")


@settings_module.router.post(
    "/admin/evaluation-grants/{grant_id}/issue-launch",
    response_model=dict,
    status_code=201,
)
async def issue_evaluation_workspace_launch(
    grant_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Issue one one-time launch ticket without granting execution authority."""

    await _require_platform_admin(request, current_user)
    owner_user_id = _owner_user_id(current_user)
    try:
        issued = await issue_evaluation_launch_ticket(
            owner_user_id=owner_user_id,
            grant_id=grant_id,
        )
    except EvaluationLaunchGateError as exc:
        detail = str(exc)
        if detail in {"evaluation_launch_grant_not_found"}:
            raise HTTPException(status_code=404, detail="Evaluation grant not found.") from exc
        if detail in {
            "evaluation_launch_grant_inactive",
            "evaluation_launch_grant_unsafe",
            "evaluation_launch_grant_authority_invalid",
        }:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Evaluation grant is not eligible for workspace launch.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Evaluation workspace launch authority is unavailable.",
        ) from exc

    token = str(issued.pop("launch_ticket"))
    launch_path = "/console/evaluation.html?" + urlencode({"launch": token})
    return {
        "status": "issued",
        "grant_id": grant_id,
        "launch_path": launch_path,
        "launch_ticket_expires_in_seconds": issued["expires_in_seconds"],
        "workspace_session_seconds": issued["workspace_session_seconds"],
        "one_time_launch": True,
        "requires_zaxam_iframe": True,
        "execution_api_key_required": True,
        "execution_authority_replaced": False,
        "production_allowed": False,
    }


__all__ = ["issue_evaluation_workspace_launch"]
