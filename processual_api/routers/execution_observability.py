"""Read-only execution observability route for console surfaces."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, Query

from processual_api.auth.security import get_current_user
from processual_api.services.execution_observability import execution_observability_snapshot

from . import settings as settings_module

router = settings_module.router


@settings_module.router.get("/execution-observability/summary", response_model=dict)
async def get_execution_observability_summary(
    limit: int = Query(default=50, ge=1, le=100),
    _user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Return canonical execution aggregates and traceable recent records."""
    return execution_observability_snapshot(limit=limit)


__all__ = ["get_execution_observability_summary", "router"]
