"""Server-side discovery qualification for Enterprise endpoint bindings."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, status
from pydantic import BaseModel, Field

from processual_api.auth.security import get_current_user
from processual_api.integrations.endpoint_binding_provenance import (
    EndpointBindingProvenance,
    EndpointBindingProvenanceError,
    provenance_matches_binding,
    qualify_binding_from_discovery,
)
from processual_api.integrations.endpoint_discovery_quality import (
    EndpointDiscoveryError,
    assess_endpoint_discovery,
)

from . import settings as settings_module
from . import settings_enterprise_endpoint_bindings_runtime as binding_runtime
from . import settings_enterprise_integration_runtime as enterprise_runtime

DISCOVERY_PROVENANCE_STORAGE_KEY = "enterprise_endpoint_discovery_provenance_v1"


class EndpointDiscoveryQualificationRequest(BaseModel):
    api_description: dict[str, Any]
    contract_family: str = Field(min_length=1, max_length=80)
    source_reference: str = Field(min_length=1, max_length=1000)
    release_pinned: bool
    external_references_resolved: bool
    operation_id: str = Field(min_length=1, max_length=300)


def _require_enterprise(current_user: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    user_id, raw, capability = enterprise_runtime._client_enterprise_capability(
        current_user=current_user
    )
    enterprise_runtime._require_enterprise_entitlement(capability)
    return user_id, raw


def _stored_provenance(raw: dict[str, Any]) -> list[dict[str, Any]]:
    items = raw.get(DISCOVERY_PROVENANCE_STORAGE_KEY, [])
    return [dict(item) for item in items if isinstance(item, dict)]


def _find_provenance(
    raw: dict[str, Any],
    binding_id: str,
) -> EndpointBindingProvenance | None:
    for item in reversed(_stored_provenance(raw)):
        if str(item.get("binding_id") or "") != binding_id:
            continue
        try:
            return EndpointBindingProvenance(**{
                key: value for key, value in item.items() if key != "binding_id"
            })
        except ValueError:
            return None
    return None


def _safe_projection(
    binding_id: str,
    provenance: EndpointBindingProvenance,
    *,
    matches_binding: bool,
) -> dict[str, Any]:
    return {
        "binding_id": binding_id,
        **provenance.model_dump(),
        "qualification_state": "qualified" if matches_binding else "drifted",
        "provenance_matches_binding": matches_binding,
        "production_allowed": False,
        "runtime_connector_approved": False,
        "raw_secret_visible": False,
    }


@settings_module.router.get(
    "/enterprise-integration/endpoint-bindings/{binding_id}/discovery-qualification",
    response_model=dict,
)
async def get_endpoint_discovery_qualification(
    binding_id: str,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    _, raw = _require_enterprise(current_user)
    spec = binding_runtime._find_binding(raw, binding_id)
    provenance = _find_provenance(raw, binding_id)
    if provenance is None:
        return {
            "binding_id": binding_id,
            "qualification_state": "not_qualified",
            "provenance_matches_binding": False,
            "production_allowed": False,
            "runtime_connector_approved": False,
            "raw_secret_visible": False,
        }
    return _safe_projection(
        binding_id,
        provenance,
        matches_binding=provenance_matches_binding(spec, provenance),
    )


@settings_module.router.post(
    "/enterprise-integration/endpoint-bindings/{binding_id}/discovery-qualification",
    response_model=dict,
)
async def qualify_endpoint_binding_discovery(
    binding_id: str,
    body: EndpointDiscoveryQualificationRequest,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    user_id, raw = _require_enterprise(current_user)
    spec = binding_runtime._find_binding(raw, binding_id)
    try:
        assessment = assess_endpoint_discovery(
            body.api_description,
            contract_family=body.contract_family,
            source_reference=body.source_reference,
            release_pinned=body.release_pinned,
            external_references_resolved=body.external_references_resolved,
        )
        provenance = qualify_binding_from_discovery(
            spec,
            assessment,
            operation_id=body.operation_id,
        )
    except (
        EndpointDiscoveryError,
        EndpointBindingProvenanceError,
        ValueError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    items = [
        item
        for item in _stored_provenance(raw)
        if str(item.get("binding_id") or "") != binding_id
    ]
    items.append({"binding_id": binding_id, **provenance.model_dump()})
    raw[DISCOVERY_PROVENANCE_STORAGE_KEY] = items[-100:]
    settings_module._save_raw(user_id, raw)

    return {
        "status": "discovery_qualified",
        "persisted": True,
        "assessment": {
            "source_reference": assessment["source_reference"],
            "source_sha256": assessment["source_sha256"],
            "title": assessment["title"],
            "version": assessment["version"],
            "dialect": assessment["dialect"],
            "contract_family": assessment["contract_family"],
            "operation_count": assessment["operation_count"],
            "blocker_codes": assessment["blocker_codes"],
            "warning_codes": assessment["warning_codes"],
            "discovery_quality_passed": assessment["discovery_quality_passed"],
            "binding_generation_ready": assessment["binding_generation_ready"],
        },
        "provenance": _safe_projection(
            binding_id,
            provenance,
            matches_binding=True,
        ),
        "production_allowed": False,
        "runtime_connector_approved": False,
        "raw_secret_visible": False,
    }


__all__ = [
    "DISCOVERY_PROVENANCE_STORAGE_KEY",
    "EndpointDiscoveryQualificationRequest",
    "get_endpoint_discovery_qualification",
    "qualify_endpoint_binding_discovery",
]
