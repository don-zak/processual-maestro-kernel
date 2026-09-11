"""Quota-governed External Evaluation grant creation.

This adapter keeps the existing validated grant creation path authoritative while
normalizing the API-key quota policy before the grant is sealed into shared
PostgreSQL authority.
"""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Request, status
from pydantic import Field

from processual_api.auth.security import get_current_user
from processual_api.services.evaluation_grants import EVALUATION_TASK_EXECUTE_ENDPOINT
from processual_api.services.evaluation_key_quota_policy import (
    CRM_EVALUATION_KEY_QUOTA,
    INTEGRATION_EVALUATION_KEY_QUOTA,
    evaluation_key_quota,
    normalized_evaluation_key_type,
)

from .settings_admin_evaluation_binding_catalog import evaluation_binding_catalog
from .settings_admin_evaluation_grants import (
    EvaluationGrantCreate,
    create_evaluation_grant,
)


class QuotaGovernedEvaluationGrantCreate(EvaluationGrantCreate):
    evaluation_type: str | None = Field(
        default=None,
        pattern="^(crm|standard|integration)$",
    )


def _normalized_endpoint(value: Any) -> tuple[str, str]:
    if isinstance(value, dict):
        return (
            str(value.get("method") or "").strip().upper(),
            str(value.get("path") or "").strip(),
        )
    return (
        str(getattr(value, "method", "") or "").strip().upper(),
        str(getattr(value, "path", "") or "").strip(),
    )


async def _require_selectable_runtime_bindings(
    body: QuotaGovernedEvaluationGrantCreate,
    request: Request,
    current_user: dict[str, Any],
) -> None:
    endpoints = {_normalized_endpoint(value) for value in body.allowed_endpoints}
    if EVALUATION_TASK_EXECUTE_ENDPOINT not in endpoints:
        return

    catalog = await evaluation_binding_catalog(
        request=request,
        current_user=current_user,
    )
    items = {
        str(item.get("binding_id") or "").strip(): item
        for item in catalog.get("bindings") or []
        if isinstance(item, dict) and str(item.get("binding_id") or "").strip()
    }
    task_ids = {
        str(task_id or "").strip().lower()
        for task_id in body.allowed_task_ids
        if str(task_id or "").strip()
    }

    for raw_binding_id in body.allowed_binding_ids:
        binding_id = str(raw_binding_id or "").strip()
        item = items.get(binding_id)
        if item is None or item.get("selectable") is not True:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Evaluation runtime binding must be sandbox-ready with a current "
                    f"live proof and active sandbox grant: {binding_id}"
                ),
            )
        binding_task = str(item.get("task_id") or "").strip().lower()
        if binding_task not in task_ids:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Evaluation runtime binding task is outside the grant task envelope: "
                    f"{binding_id}"
                ),
            )


async def create_quota_governed_evaluation_grant(
    body: QuotaGovernedEvaluationGrantCreate,
    request: Request,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    await _require_selectable_runtime_bindings(body, request, current_user)
    resolved_type = normalized_evaluation_key_type(
        body.evaluation_type,
        allowed_binding_ids=list(body.allowed_binding_ids),
        allowed_endpoints=list(body.allowed_endpoints),
    )
    quota = evaluation_key_quota(resolved_type)
    canonical = EvaluationGrantCreate(
        client_id=body.client_id,
        user_id=body.user_id,
        issued_to=body.issued_to,
        purpose=body.purpose,
        allowed_task_ids=list(body.allowed_task_ids),
        allowed_binding_ids=list(body.allowed_binding_ids),
        allowed_endpoints=list(body.allowed_endpoints),
        allowed_scopes=list(body.allowed_scopes),
        evaluation_type=resolved_type,
        max_requests=quota,
        expires_in_days=body.expires_in_days,
    )
    result = await create_evaluation_grant(
        body=canonical,
        request=request,
        current_user=current_user,
    )

    created = dict(result.get("grant") or {})
    created["evaluation_type"] = resolved_type
    created["max_requests"] = quota
    created["quota_unit"] = "admitted_execution"
    created["crm_key_quota"] = CRM_EVALUATION_KEY_QUOTA
    created["integration_key_quota"] = INTEGRATION_EVALUATION_KEY_QUOTA
    created["quota_policy"] = "integration_equals_2x_crm"
    result["grant"] = created
    return result


__all__ = [
    "QuotaGovernedEvaluationGrantCreate",
    "create_quota_governed_evaluation_grant",
]
