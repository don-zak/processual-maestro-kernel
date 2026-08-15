"""Super-Administrator view of complete External Evaluation endpoint coverage."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Query

from processual_api.auth.platform_admin_authority import require_active_platform_admin
from processual_api.auth.security import get_current_user
from processual_api.services.evaluation_coverage_plan import (
    build_evaluation_coverage_plan,
)
from processual_api.services.evaluation_quality_assessment import (
    assess_evaluation_campaign_quality,
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
    client_id: str | None = Query(default=None),
    evaluation_grant_id: str | None = Query(default=None),
    api_key_id: str | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
) -> dict:
    await require_active_platform_admin(current_user)
    return summarize_evaluation_endpoint_coverage(
        client_id=client_id,
        evaluation_grant_id=evaluation_grant_id,
        api_key_id=api_key_id,
    )


@settings_module.router.get(
    "/admin/evaluation-grants/quality-status",
    response_model=dict,
)
async def evaluation_quality_status(
    client_id: str = Query(min_length=1, max_length=160),
    min_successes_per_endpoint: int = Query(default=3, ge=1, le=100),
    max_failure_rate: float = Query(default=0.0, ge=0.0, le=1.0),
    max_p95_latency_ms: float | None = Query(default=None, gt=0),
    current_user: dict = Depends(get_current_user),
) -> dict:
    await require_active_platform_admin(current_user)
    try:
        return assess_evaluation_campaign_quality(
            client_id=client_id,
            min_successes_per_endpoint=min_successes_per_endpoint,
            max_failure_rate=max_failure_rate,
            max_p95_latency_ms=max_p95_latency_ms,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


__all__ = [
    "evaluation_coverage_plan",
    "evaluation_coverage_status",
    "evaluation_quality_status",
]
