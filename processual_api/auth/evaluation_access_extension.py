"""Install fail-closed endpoint authority for External Evaluation API keys.

The core authentication dependency remains authoritative for credential validity,
expiry, revocation, and the evaluation-specific request cap. This extension adds
the endpoint envelope from the persisted evaluation grant before any protected
runtime handler is entered.
"""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Request, status

from processual_api.auth import security as security_module
from processual_api.services import api_key_store
from processual_api.services.evaluation_grants import (
    EVALUATION_EXECUTION_MODE,
    evaluation_endpoint_allowed,
    find_evaluation_grant,
    safe_evaluation_grant,
)

_original_get_current_user = security_module.get_current_user


def _owner_raw(current_user: dict[str, Any]) -> dict[str, Any]:
    owner_id = str(current_user.get("sub") or current_user.get("user_id") or "").strip()
    if not owner_id:
        return {}
    path = api_key_store._DATA_DIR / f"settings_{owner_id}.json"
    return api_key_store._safe_load_json(path)


async def get_current_evaluation_guarded_user(
    request: Request,
    current_user: dict[str, Any] = Depends(_original_get_current_user),
) -> dict[str, Any]:
    if current_user.get("entitlement_source") != "admin_evaluation_grant":
        return current_user

    raw = _owner_raw(current_user)
    grant = find_evaluation_grant(
        raw,
        str(current_user.get("evaluation_grant_id") or ""),
    )
    if grant is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Evaluation grant authority is unavailable.",
        )

    enriched = dict(current_user)
    enriched.update(
        {
            "category": "pilot_client",
            "allowed_endpoints": list(grant.get("allowed_endpoints") or []),
            "endpoint_authority_source": str(
                grant.get("endpoint_authority_source")
                or "canonical_runtime_access_policy"
            ),
            "execution_mode": str(
                grant.get("execution_mode") or EVALUATION_EXECUTION_MODE
            ),
            "real_runtime_execution": grant.get("real_runtime_execution") is True,
            "evaluation_access": True,
            "evaluation_access_policy": safe_evaluation_grant(grant),
            "subscription_required": False,
            "commercial_quota_required": False,
            "production_allowed": False,
        }
    )

    if not evaluation_endpoint_allowed(
        enriched,
        method=request.method,
        path=request.url.path,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Evaluation API key is not allowed for this endpoint.",
        )
    return enriched


def install_evaluation_access_authentication() -> None:
    security_module.get_current_user = get_current_evaluation_guarded_user


install_evaluation_access_authentication()


__all__ = [
    "get_current_evaluation_guarded_user",
    "install_evaluation_access_authentication",
]
