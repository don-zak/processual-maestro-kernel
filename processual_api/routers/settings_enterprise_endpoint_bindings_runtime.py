"""Settings runtime for governed Enterprise endpoint/task bindings."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, status
from pydantic import BaseModel, Field

from processual_api.auth.security import get_current_user
from processual_api.integrations.enterprise_endpoint_bindings import (
    BINDING_STORAGE_KEY,
    EndpointBindingError,
    EnterpriseEndpointBindingSpec,
    build_request_preview,
    map_response_to_task_input,
    safe_binding_payload,
)
from processual_api.integrations.integration_task_catalog import task_catalog_payload

from . import settings as settings_module
from . import settings_enterprise_integration_runtime as enterprise_runtime


class EndpointMappingPreviewRequest(BaseModel):
    response_payload: Any


class EndpointRequestPreviewRequest(BaseModel):
    task_input: dict[str, Any] = Field(default_factory=dict)


def _user_id(current_user: dict[str, Any]) -> str:
    return str(
        current_user.get("user_id")
        or current_user.get("sub")
        or "default"
    )


def _require_enterprise(current_user: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    user_id, raw, capability = enterprise_runtime._client_enterprise_capability(
        current_user=current_user
    )
    enterprise_runtime._require_enterprise_entitlement(capability)
    return user_id, raw


def _stored_bindings(raw: dict[str, Any]) -> list[dict[str, Any]]:
    items = raw.get(BINDING_STORAGE_KEY, [])
    return [dict(item) for item in items if isinstance(item, dict)]


def _safe_stored_bindings(raw: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for item in _stored_bindings(raw):
        try:
            results.append(
                safe_binding_payload(EnterpriseEndpointBindingSpec(**item))
            )
        except (ValueError, KeyError, EndpointBindingError):
            continue
    return results


def _find_binding(raw: dict[str, Any], binding_id: str) -> EnterpriseEndpointBindingSpec:
    for item in _stored_bindings(raw):
        if str(item.get("binding_id") or "") == binding_id:
            try:
                return EnterpriseEndpointBindingSpec(**item)
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Stored endpoint binding is invalid.",
                ) from exc
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Endpoint binding not found.",
    )


@settings_module.router.get(
    "/enterprise-integration/task-catalog",
    response_model=dict,
)
async def get_enterprise_task_catalog(
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    _require_enterprise(current_user)
    return task_catalog_payload()


@settings_module.router.get(
    "/enterprise-integration/endpoint-bindings",
    response_model=dict,
)
async def list_enterprise_endpoint_bindings(
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    _, raw = _require_enterprise(current_user)
    bindings = _safe_stored_bindings(raw)
    return {
        "status": "ready",
        "environment": "sandbox",
        "binding_count": len(bindings),
        "bindings": bindings,
        "production_allowed": False,
        "runtime_connector_approved": False,
        "raw_secret_visible": False,
    }


@settings_module.router.put(
    "/enterprise-integration/endpoint-bindings/{binding_id}",
    response_model=dict,
)
async def save_enterprise_endpoint_binding(
    binding_id: str,
    body: EnterpriseEndpointBindingSpec,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    user_id, raw = _require_enterprise(current_user)
    if body.binding_id != binding_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path binding id must match payload binding id.",
        )
    try:
        safe = safe_binding_payload(body)
    except (ValueError, KeyError, EndpointBindingError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    items = _stored_bindings(raw)
    replacement = body.model_dump()
    replaced = False
    for index, item in enumerate(items):
        if str(item.get("binding_id") or "") == binding_id:
            items[index] = replacement
            replaced = True
            break
    if not replaced:
        items.append(replacement)
    raw[BINDING_STORAGE_KEY] = items
    settings_module._save_raw(user_id, raw)
    return {
        "status": "saved",
        "persisted": True,
        "binding": safe,
        "production_allowed": False,
        "runtime_connector_approved": False,
    }


@settings_module.router.delete(
    "/enterprise-integration/endpoint-bindings/{binding_id}",
    response_model=dict,
)
async def delete_enterprise_endpoint_binding(
    binding_id: str,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    user_id, raw = _require_enterprise(current_user)
    items = _stored_bindings(raw)
    retained = [
        item for item in items
        if str(item.get("binding_id") or "") != binding_id
    ]
    if len(retained) == len(items):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Endpoint binding not found.",
        )
    raw[BINDING_STORAGE_KEY] = retained
    settings_module._save_raw(user_id, raw)
    return {
        "status": "deleted",
        "binding_id": binding_id,
        "production_allowed": False,
        "runtime_connector_approved": False,
    }


@settings_module.router.post(
    "/enterprise-integration/endpoint-bindings/{binding_id}/request-preview",
    response_model=dict,
)
async def preview_enterprise_endpoint_request(
    binding_id: str,
    body: EndpointRequestPreviewRequest,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    _, raw = _require_enterprise(current_user)
    spec = _find_binding(raw, binding_id)
    try:
        return build_request_preview(spec, body.task_input)
    except (ValueError, KeyError, EndpointBindingError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@settings_module.router.post(
    "/enterprise-integration/endpoint-bindings/{binding_id}/mapping-preview",
    response_model=dict,
)
async def preview_enterprise_endpoint_mapping(
    binding_id: str,
    body: EndpointMappingPreviewRequest,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    _, raw = _require_enterprise(current_user)
    spec = _find_binding(raw, binding_id)
    try:
        return map_response_to_task_input(spec, body.response_payload)
    except (ValueError, KeyError, EndpointBindingError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


__all__ = [
    "EndpointMappingPreviewRequest",
    "EndpointRequestPreviewRequest",
    "delete_enterprise_endpoint_binding",
    "get_enterprise_task_catalog",
    "list_enterprise_endpoint_bindings",
    "preview_enterprise_endpoint_mapping",
    "preview_enterprise_endpoint_request",
    "save_enterprise_endpoint_binding",
]
