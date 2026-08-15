"""Super-Administrator view of complete External Evaluation endpoint coverage."""

from __future__ import annotations

from fastapi import Depends, Query

from processual_api.auth.platform_admin_authority import require_active_platform_admin
from processual_api.auth.security import get_current_user
from processual_api.services.evaluation_coverage_plan import (
    build_evaluation_coverage_plan,
)
from processual_api.services.usage_log_store import (
    summarize_evaluation_endpoint_coverage,
)

from . import settings as settings_module


@settings_module.router.get(
    "/admin/evaluation-grants/coverage-plan",
    response_model=dict,
)
async def evaluation_coverage_plan(
    current_user: dict = Depends(get_current_user),
) -> dict:
    await require_active_platform_admin(current_user)
    return build_evaluation_coverage_plan()


@settings_module.router.get(
    "/admin/evaluation-grants/coverage-status",
    response_model=dict,
)
async def evaluation_coverage_status(
    evaluation_grant_id: str | None = Query(default=None),
    api_key_id: str | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
) -> dict:
    await require_active_platform_admin(current_user)
    return summarize_evaluation_endpoint_coverage(
        evaluation_grant_id=evaluation_grant_id,
        api_key_id=api_key_id,
    )


__all__ = ["evaluation_coverage_plan", "evaluation_coverage_status"]
