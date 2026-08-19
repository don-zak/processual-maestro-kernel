"""Safe admin read projection for CAMARA QoD qualification state."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, status

from processual_api.auth.security import get_current_user
from processual_api.integrations.camara_qod_external_sandbox_qualification import (
    camara_qod_external_sandbox_qualification_payload,
)
from processual_api.integrations.camara_qod_governance_approval import (
    camara_qod_governance_approval_payload,
)
from processual_api.integrations.camara_qod_runtime_registration import (
    camara_qod_runtime_registration_payload,
)
from processual_api.integrations.camara_qod_semantic_mapping import (
    camara_qod_semantic_mapping_payload,
)
from processual_api.integrations.camara_qod_telefonica_compatibility import (
    camara_qod_telefonica_compatibility_payload,
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
    """Return review-safe CAMARA qualification state without connector authority."""

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
        and item.contract_family == candidate.contract_family
        and item.allowed_revisions == candidate.allowed_revisions
        and item.allowed_path_prefixes == candidate.allowed_path_prefixes
        and item.allowed_reference_prefixes == candidate.allowed_reference_prefixes
        and item.policy_version == candidate.policy_version
        for item in catalog
    )
    mapping = camara_qod_semantic_mapping_payload()
    governance_candidate = mapping["governance_candidate"]
    governance_approval = camara_qod_governance_approval_payload()
    runtime_registration = camara_qod_runtime_registration_payload()
    external_sandbox = camara_qod_external_sandbox_qualification_payload()
    telefonica_compatibility = camara_qod_telefonica_compatibility_payload()

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
        "governance_candidate_state": governance_candidate["candidate_state"],
        "governance_candidate_valid": governance_candidate[
            "governance_candidate_valid"
        ],
        "governance_blocker_codes": governance_candidate[
            "governance_blocker_codes"
        ],
        "candidate_task_ids": governance_candidate["candidate_task_ids"],
        "candidate_entitlement_ids": governance_candidate[
            "candidate_entitlement_ids"
        ],
        "candidate_quota_meters": governance_candidate["candidate_quota_meters"],
        "governance_decision": governance_approval["governance_decision"],
        "governance_approved": governance_approval["governance_approved"],
        "approved_governance_version": governance_approval[
            "approved_governance_version"
        ],
        "approved_contract_blob_sha": governance_approval[
            "approved_contract_blob_sha"
        ],
        "existing_network_assurance_reused": False,
        # Local isolated live-source evidence is retained outside this server
        # projection and must not be inferred from code or CI presence.
        "live_source_acquisition_proven": False,
        "provider_credentials_present": False,
        "provider_network_proof": False,
        "provider_sandbox_proven": False,
        "runtime_task_registered": runtime_registration[
            "runtime_task_registered"
        ],
        "registered_task_ids": runtime_registration["registered_task_ids"],
        "registered_entitlement_ids": runtime_registration[
            "registered_entitlement_ids"
        ],
        "registered_quota_meters": runtime_registration[
            "registered_quota_meters"
        ],
        "runtime_default_deny": runtime_registration["default_deny"],
        "runtime_connector_approved": False,
        "production_allowed": False,
        "raw_secret_visible": False,
        # External interoperability evidence is explicitly projected as a
        # separate non-authoritative object. Its own payload remains fail-closed
        # and cannot upgrade the governed provider/runtime/production gates.
        "external_sandbox_evidence": external_sandbox,
        "telefonica_compatibility": telefonica_compatibility,
    }


__all__ = ["get_camara_qod_qualification_status"]
