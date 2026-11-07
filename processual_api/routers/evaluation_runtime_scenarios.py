from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, status

from processual_api.auth.security import get_current_user
from processual_api.services.evaluation_authority_postgres import (
    EvaluationAuthorityError,
    load_evaluation_authority_state,
)
from processual_api.services.evaluation_grants import find_evaluation_grant
from processual_api.services.evaluation_scenarios import customer_evaluation_scenarios

from .evaluation_runtime import evaluation_runtime_status


async def evaluation_runtime_status_with_scenarios(
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Enrich customer-safe status with scenarios derived from sealed grant authority."""

    payload = await evaluation_runtime_status(current_user)
    owner_id = str(current_user.get("sub") or current_user.get("user_id") or "").strip()
    grant_id = str(current_user.get("evaluation_grant_id") or "").strip()
    if not owner_id or not grant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Governed Evaluation credential required.",
        )
    try:
        raw = await load_evaluation_authority_state(owner_id)
    except EvaluationAuthorityError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Evaluation scenario authority is temporarily unavailable.",
        ) from exc
    grant = find_evaluation_grant(raw, grant_id)
    if grant is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Evaluation grant is unavailable.",
        )

    scenarios = customer_evaluation_scenarios(raw, grant)
    return {
        **payload,
        "guided_scenarios": scenarios,
        "guided_scenario_count": len(scenarios),
        "scenario_catalog_source": "sealed_evaluation_grant",
        "scenario_status_reads_consume_quota": False,
        "raw_scenario_input_persisted": False,
        "production_allowed": False,
    }


__all__ = ["evaluation_runtime_status_with_scenarios"]
