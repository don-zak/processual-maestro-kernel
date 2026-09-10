"""Quota-governed External Evaluation grant creation.

This adapter keeps the existing validated grant creation path authoritative while
normalizing the API-key quota policy before the grant is sealed into shared
PostgreSQL authority.
"""

from __future__ import annotations

from typing import Any

from fastapi import Depends, Request
from pydantic import Field

from processual_api.auth.security import get_current_user
from processual_api.services.evaluation_authority_postgres import (
    load_evaluation_authority_state,
    save_evaluation_authority_state,
)
from processual_api.services.evaluation_grants import find_evaluation_grant
from processual_api.services.evaluation_key_quota_policy import (
    CRM_EVALUATION_KEY_QUOTA,
    INTEGRATION_EVALUATION_KEY_QUOTA,
    evaluation_key_quota,
    normalized_evaluation_key_type,
)

from .settings_admin_evaluation_grants import (
    EvaluationGrantCreate,
    create_evaluation_grant,
)


class QuotaGovernedEvaluationGrantCreate(EvaluationGrantCreate):
    evaluation_type: str | None = Field(
        default=None,
        pattern="^(crm|standard|integration)$",
    )


async def create_quota_governed_evaluation_grant(
    body: QuotaGovernedEvaluationGrantCreate,
    request: Request,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
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
        max_requests=quota,
        expires_in_days=body.expires_in_days,
    )
    result = await create_evaluation_grant(
        body=canonical,
        request=request,
        current_user=current_user,
    )

    # The Evaluation type is grant authority, not presentation metadata. Persist
    # it into the shared PostgreSQL-backed grant snapshot before returning.
    owner_id = str(current_user.get("sub") or current_user.get("user_id") or "default")
    raw = await load_evaluation_authority_state(owner_id)
    created = dict(result.get("grant") or {})
    grant_id = str(created.get("grant_id") or "")
    grant = find_evaluation_grant(raw, grant_id)
    if grant is not None:
        grant["evaluation_type"] = resolved_type
        grant["max_requests"] = quota
        grant["quota_unit"] = "admitted_execution"
        grant["quota_policy"] = "integration_equals_2x_crm"
        await save_evaluation_authority_state(owner_id, raw)

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
