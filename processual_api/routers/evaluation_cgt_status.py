"""Customer-safe External Evaluation status enriched with persisted CGT evidence."""

from __future__ import annotations

from typing import Any

from fastapi import Depends

from processual_api.auth.security import get_current_user
from processual_api.services.evaluation_cgt_evidence_postgres import (
    latest_evaluation_cgt_governance,
)

from .evaluation_runtime_scenarios import evaluation_runtime_status_with_scenarios


async def evaluation_runtime_status_with_governance(
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    payload = await evaluation_runtime_status_with_scenarios(current_user)
    owner_id = str(current_user.get("sub") or current_user.get("user_id") or "").strip()
    grant_id = str(current_user.get("evaluation_grant_id") or "").strip()
    api_key_id = str(current_user.get("api_key_id") or "").strip()
    if owner_id and grant_id and api_key_id:
        latest = await latest_evaluation_cgt_governance(
            owner_id=owner_id,
            grant_id=grant_id,
            api_key_id=api_key_id,
        )
        if latest:
            payload["latest_governance"] = latest["governance"]
            payload["fate_vector"] = latest["governance"].get("fate_vector")
            payload["fate_vector_basis"] = latest["governance"].get("fate_vector_basis")
            payload["governance_enforced_before_admission"] = latest[
                "governance_enforced_before_admission"
            ]
            payload["governed_execution_evidence_sha256"] = latest[
                "governed_execution_evidence_sha256"
            ]
            payload["maestro_task_completed"] = latest.get("maestro_task_completed") is True
            payload["maestro_consumption"] = latest.get("maestro_consumption") or None
            payload["maestro_governed_evidence_sha256"] = latest.get(
                "maestro_governed_evidence_sha256"
            )
    payload["governance_layer"] = "cgt"
    payload["governance_can_expand_grant"] = False
    payload["production_allowed"] = False
    return payload


__all__ = ["evaluation_runtime_status_with_governance"]
