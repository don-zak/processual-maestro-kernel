"""Read-only execution observability routes for console surfaces."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from processual_api.auth.security import get_current_user
from processual_api.services.execution_observability import execution_observability_snapshot

router = APIRouter(prefix="/execution-observability", tags=["execution-observability"])


@router.get("/summary", response_model=dict)
async def get_execution_observability_summary(
    limit: int = Query(default=50, ge=1, le=100),
    _user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Return canonical execution aggregates and traceable recent records."""
    return execution_observability_snapshot(limit=limit)


__all__ = ["router"]
