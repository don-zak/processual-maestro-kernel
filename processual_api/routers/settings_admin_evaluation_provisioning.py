"""Grant-scoped provisioning for governed external Evaluation runtime owners."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Request, status

from processual_api.auth.platform_admin_authority import require_active_platform_admin
from processual_api.auth.security import get_current_user
from processual_api.integrations.enterprise_endpoint_bindings import (
    BINDING_STORAGE_KEY,
    EndpointBindingError,
    EnterpriseEndpointBindingSpec,
    safe_binding_payload,
)
from processual_api.integrations.enterprise_endpoint_request_mapping import (
    REQUEST_MAPPING_STORAGE_KEY,
    EndpointRequestMappingError,
    EnterpriseEndpointRequestMappingSpec,
    validate_request_mapping,
)
from processual_api.integrations.sandbox_operational_readiness import (
    SANDBOX_CONTENT_STORAGE_KEY,
    SANDBOX_SECRET_REFERENCE_STORAGE_KEY,
    SandboxContentContract,
    SandboxSecretReference,
    safe_content_projection,
    safe_secret_reference_projection,
)
from processual_api.services.enterprise_endpoint_sandbox_grants import (
    SandboxGrantError,
    issue_sandbox_execution_grant,
)
from processual_api.services.evaluation_grants import (
    EVALUATION_GRANTS_STORAGE_KEY,
    find_evaluation_grant,
    refresh_evaluation_grant_status,
)

from . import settings as settings_module
from . import settings_enterprise_endpoint_bindings_runtime as binding_runtime


def _admin_owner_id(current_user: dict[str, Any]) -> str:
    return str(
        current_user.get("sub")
        or current_user.get("user_id")
        or "default"
    ).strip()


def _evaluation_owner_id(grant: dict[str, Any]) -> str:
    owner_id = str(grant.get("user_id") or grant.get("client_id") or "").strip()
    if not owner_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Evaluation grant owner is unavailable.",
        )
    return owner_id


async def _active_grant_context(
    grant_id: str,
    current_user: dict[str, Any],
) -> tuple[dict[str, Any], str, dict[str, Any]]:
    await require_active_platform_admin(current_user)
    admin_owner_id = _admin_owner_id(current_user)
    admin_raw = settings_module._load_raw(admin_owner_id)
    grant = find_evaluation_grant(admin_raw, grant_id)
    if grant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation grant not found.",
        )

    before = str(grant.get("status") or "")
    refresh_evaluation_grant_status(grant)
    if before != str(grant.get("status") or ""):
        admin_raw[EVALUATION_GRANTS_STORAGE_KEY] = list(
            admin_raw.get(EVALUATION_GRANTS_STORAGE_KEY) or []
        )
        settings_module._save_raw(admin_owner_id, admin_raw)
    if str(grant.get("status") or "") != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Evaluation grant is not active.",
        )

    owner_id = _evaluation_owner_id(grant)
    return grant, owner_id, settings_module._load_raw(owner_id)


def _replace_by_binding(
    raw: dict[str, Any],
    storage_key: str,
    binding_id: str,
    value: dict[str, Any],
) -> None:
    items = raw.get(storage_key, [])
    if not isinstance(items, list):
        items = []
    replacement = dict(value)
    for index, item in enumerate(items):
        if isinstance(item, dict) and str(item.get("binding_id") or "") == binding_id:
            items[index] = replacement
            break
    else:
        items.append(replacement)
    raw[storage_key] = items


def _binding_for_grant(
    raw: dict[str, Any],
    grant: dict[str, Any],
    binding_id: str,
) -> EnterpriseEndpointBindingSpec:
    spec = binding_runtime._find_binding(raw, binding_id)
    allowed_tasks = {
        str(task_id or "").strip().lower()
        for task_id in grant.get("allowed_task_ids", [])
    }
    if spec.task_id not in allowed_tasks:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Endpoint binding task is outside the Evaluation grant authority.",
        )
    return spec


def _validated_binding_for_grant(
    grant: dict[str, Any],
    body: EnterpriseEndpointBindingSpec,
) -> dict[str, Any]:
    allowed_tasks = {
        str(task_id or "").strip().lower()
        for task_id in grant.get("allowed_task_ids", [])
    }
    if body.task_id not in allowed_tasks:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Endpoint binding task is outside the Evaluation grant authority.",
        )
    try:
        safe = safe_binding_payload(body)
    except (ValueError, KeyError, EndpointBindingError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    grant_scopes = {
        str(scope or "").strip().lower()
        for scope in (
            list(grant.get("allowed_scopes") or [])
            + list(grant.get("task_scope_ids") or [])
        )
    }
    binding_scopes = {
        str(scope or "").strip().lower()
        for scope in safe["required_scope_ids"]
    }
    if not binding_scopes.issubset(grant_scopes):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Endpoint binding requests scopes outside the Evaluation grant authority.",
        )
    return safe


@settings_module.router.put(
    "/admin/evaluation-grants/{grant_id}/endpoint-bindings/{binding_id}",
    response_model=dict,
)
async def save_evaluation_endpoint_binding(
    grant_id: str,
    binding_id: str,
    body: EnterpriseEndpointBindingSpec,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    grant, owner_id, raw = await _active_grant_context(grant_id, current_user)
    if body.binding_id != binding_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path binding id must match payload binding id.",
        )
    safe = _validated_binding_for_grant(grant, body)
    _replace_by_binding(raw, BINDING_STORAGE_KEY, binding_id, body.model_dump())
    settings_module._save_raw(owner_id, raw)
    return {
        "status": "saved",
        "persisted": True,
        "evaluation_grant_id": grant_id,
        "evaluation_owner_id": owner_id,
        "binding": safe,
        "production_allowed": False,
        "runtime_connector_approved": False,
    }


@settings_module.router.put(
    "/admin/evaluation-grants/{grant_id}/endpoint-bindings/{binding_id}/request-mapping",
    response_model=dict,
)
async def save_evaluation_endpoint_request_mapping(
    grant_id: str,
    binding_id: str,
    body: EnterpriseEndpointRequestMappingSpec,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    grant, owner_id, raw = await _active_grant_context(grant_id, current_user)
    binding = _binding_for_grant(raw, grant, binding_id)
    if body.binding_id != binding_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path binding id must match request mapping binding id.",
        )
    try:
        validation = validate_request_mapping(binding, body)
    except (ValueError, KeyError, EndpointBindingError, EndpointRequestMappingError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    _replace_by_binding(
        raw,
        REQUEST_MAPPING_STORAGE_KEY,
        binding_id,
        body.model_dump(),
    )
    settings_module._save_raw(owner_id, raw)
    return {
        "status": "saved",
        "persisted": True,
        "evaluation_grant_id": grant_id,
        "evaluation_owner_id": owner_id,
        "request_mapping": body.model_dump(),
        "validation": validation,
        "production_allowed": False,
        "runtime_connector_approved": False,
    }


@settings_module.router.put(
    "/admin/evaluation-grants/{grant_id}/endpoint-bindings/{binding_id}/sandbox-secret-reference",
    response_model=dict,
)
async def save_evaluation_sandbox_secret_reference(
    grant_id: str,
    binding_id: str,
    body: SandboxSecretReference,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    grant, owner_id, raw = await _active_grant_context(grant_id, current_user)
    _binding_for_grant(raw, grant, binding_id)
    if body.binding_id != binding_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path binding id must match sandbox secret reference binding id.",
        )
    _replace_by_binding(
        raw,
        SANDBOX_SECRET_REFERENCE_STORAGE_KEY,
        binding_id,
        body.model_dump(),
    )
    settings_module._save_raw(owner_id, raw)
    return {
        "status": "saved",
        "persisted": True,
        "evaluation_grant_id": grant_id,
        "evaluation_owner_id": owner_id,
        "secret_reference": safe_secret_reference_projection(body),
        "raw_secret_visible": False,
        "production_allowed": False,
        "runtime_connector_approved": False,
    }


@settings_module.router.put(
    "/admin/evaluation-grants/{grant_id}/endpoint-bindings/{binding_id}/sandbox-content-contract",
    response_model=dict,
)
async def save_evaluation_sandbox_content_contract(
    grant_id: str,
    binding_id: str,
    body: SandboxContentContract,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    grant, owner_id, raw = await _active_grant_context(grant_id, current_user)
    _binding_for_grant(raw, grant, binding_id)
    if body.binding_id != binding_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path binding id must match sandbox content contract binding id.",
        )
    _replace_by_binding(
        raw,
        SANDBOX_CONTENT_STORAGE_KEY,
        binding_id,
        body.model_dump(),
    )
    settings_module._save_raw(owner_id, raw)
    return {
        "status": "saved",
        "persisted": True,
        "evaluation_grant_id": grant_id,
        "evaluation_owner_id": owner_id,
        "content_contract": safe_content_projection(body),
        "raw_payload_visible": False,
        "production_allowed": False,
        "runtime_connector_approved": False,
    }


@settings_module.router.post(
    "/admin/evaluation-grants/{grant_id}/endpoint-bindings/{binding_id}/sandbox-grant",
    response_model=dict,
)
async def grant_evaluation_endpoint_sandbox_execution(
    grant_id: str,
    binding_id: str,
    body: binding_runtime.EndpointSandboxGrantRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    grant, owner_id, raw = await _active_grant_context(grant_id, current_user)
    session = binding_runtime._require_supervisor_approval_session(request)
    spec = _binding_for_grant(raw, grant, binding_id)
    try:
        sandbox_grant = issue_sandbox_execution_grant(
            raw,
            spec=spec,
            supervisor_id=binding_runtime._supervisor_actor(current_user),
            ttl_minutes=body.ttl_minutes,
        )
    except (ValueError, KeyError, EndpointBindingError, SandboxGrantError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    settings_module._save_raw(owner_id, raw)
    return {
        "status": "sandbox_execution_granted",
        "evaluation_grant_id": grant_id,
        "evaluation_owner_id": owner_id,
        "grant": sandbox_grant,
        "supervisor_session_key_id": str(session.get("key_id") or ""),
        "production_allowed": False,
        "runtime_connector_approved": False,
    }


__all__ = [
    "grant_evaluation_endpoint_sandbox_execution",
    "save_evaluation_endpoint_binding",
    "save_evaluation_endpoint_request_mapping",
    "save_evaluation_sandbox_content_contract",
    "save_evaluation_sandbox_secret_reference",
]
