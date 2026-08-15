"""Super-Administrator view of complete External Evaluation endpoint coverage."""

from __future__ import annotations

from fastapi import Depends

from processual_api.auth.platform_admin_authority import require_active_platform_admin
from processual_api.auth.security import get_current_user
from processual_api.services.evaluation_coverage_plan import (
    build_evaluation_coverage_plan,
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


__all__ = ["evaluation_coverage_plan"]
