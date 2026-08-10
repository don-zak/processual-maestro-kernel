"""Read-only execution observability route for console surfaces."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Query, status

from processual_api.auth.security import get_current_user
from processual_api.services.execution_observability import execution_observability_snapshot
from processual_api.supervision_rbac import USAGE_READ_SCOPE, require_supervision_scope

from . import settings as settings_module

router = settings_module.router


@settings_module.router.get("/execution-observability/summary", response_model=dict)
async def get_execution_observability_summary(
    limit: int = Query(default=50, ge=1, le=100),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Return canonical execution aggregates for authorized usage supervisors."""
    try:
        require_supervision_scope(current_user, USAGE_READ_SCOPE)
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    return execution_observability_snapshot(limit=limit)


__all__ = ["get_execution_observability_summary", "router"]
