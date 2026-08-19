"""Safe admin read projection for CAMARA QoD qualification state."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, status

from processual_api.auth.security import get_current_user
from processual_api.integrations.camara_qod_semantic_mapping import (
    camara_qod_semantic_mapping_payload,
)
from processual_api.integrations.trusted_endpoint_source_acquisition import (
    CAMARA_QOD_R32_QUALIFICATION_CANDIDATE,
    TrustedEndpointSourceAcquisitionError,
    trusted_github_source_catalog_from_env,
)

from . import settings as settings_module

_ADMIN_READ_SCOPES = {
    "admin:*",
    "admin:integration:qualification:read",
    "admin:integration:qualification:review",
    "admin:integration_readiness:review",
    "admin:clients:review",
}


def _normalized_scopes(current_user: dict[str, Any]) -> set[str]:
    raw = current_user.get("scopes") or current_user.get("permissions") or []
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, (list, tuple, set)):
        return set()
    return {
        str(scope).strip()
        for scope in raw
        if str(scope or "").strip()
    }


def _require_admin_read(current_user: dict[str, Any]) -> None:
    scopes = _normalized_scopes(current_user)
    role = str(current_user.get("role") or "").strip().lower()
    if "*" in scopes or scopes.intersection(_ADMIN_READ_SCOPES):
        return
    if role == "admin" and "admin" in scopes:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Admin qualification read access is required.",
    )


@settings_module.router.get(
    "/admin/integration-center/camara-qod-qualification",
    response_model=dict,
)
async def get_camara_qod_qualification_status(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Return review-safe CAMARA qualification state without runtime authority."""

    _require_admin_read(current_user)
    try:
        catalog = trusted_github_source_catalog_from_env()
    except TrustedEndpointSourceAcquisitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="trusted_source_catalog_invalid",
        ) from exc

    candidate = CAMARA_QOD_R32_QUALIFICATION_CANDIDATE
    enabled = any(
        item.source_identity_id == candidate.source_identity_id
        and item.repository == candidate.repository
        and item.allowed_revisions == candidate.allowed_revisions
        and item.allowed_path_prefixes == candidate.allowed_path_prefixes
        and item.allowed_reference_prefixes == candidate.allowed_reference_prefixes
        for item in catalog
    )
    mapping = camara_qod_semantic_mapping_payload()
    return {
        "status": "reviewed_qualification_contract",
        "source_identity_id": mapping["source_identity_id"],
        "repository": mapping["repository"],
        "source_revision": mapping["source_revision"],
        "source_path": mapping["source_path"],
        "api_version": mapping["api_version"],
        "server_trusted_source_enabled": enabled,
        "semantic_mapping_state": mapping["mapping_state"],
        "callable_operations": mapping["callable_operations"],
        "callback_operations_excluded_from_outbound_binding": mapping[
            "callback_operations_excluded_from_outbound_binding"
        ],
        "existing_network_assurance_reused": False,
        "live_source_acquisition_proven": False,
        "provider_credentials_present": False,
        "provider_network_proof": False,
        "provider_sandbox_proven": False,
        "runtime_task_registered": False,
        "runtime_connector_approved": False,
        "production_allowed": False,
        "raw_secret_visible": False,
    }


__all__ = ["get_camara_qod_qualification_status"]
