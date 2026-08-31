"""Narrow Enterprise Integration sandbox authority for evaluation-grant API keys.

Admin-issued evaluation keys are intentionally independent from paid subscription
entitlements.  They may execute only preconfigured sandbox bindings whose
canonical task is present in the key's evaluation allowlist.  Production and
binding-management surfaces remain governed by the normal Enterprise plan path.
"""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, status

from processual_api.auth.security import get_current_user
from processual_api.integrations.enterprise_endpoint_bindings import EndpointBindingError
from processual_api.integrations.enterprise_endpoint_request_mapping import (
    EndpointRequestMappingError,
    build_external_request_body,
)
from processual_api.integrations.enterprise_sandbox_execution import SandboxExecutionError
from processual_api.integrations.integration_task_catalog import get_integration_task
from processual_api.services.enterprise_endpoint_sandbox_grants import SandboxGrantError

from . import settings as settings_module
from . import settings_enterprise_endpoint_bindings_runtime as runtime

_SANDBOX_EXECUTE_PATH = "/settings/enterprise-integration/endpoint-bindings/{binding_id}/sandbox-execute"


def _is_evaluation_identity(current_user: dict[str, Any]) -> bool:
    return bool(
        str(current_user.get("evaluation_grant_id") or "").strip()
        and current_user.get("entitlement_source") == "admin_evaluation_grant"
        and current_user.get("subscription_required") is False
        and current_user.get("task_authority_source") == "integration_task_catalog"
    )


def _require_evaluation_task_authority(
    current_user: dict[str, Any],
    task_id: str,
) -> None:
    normalized_task_id = str(task_id or "").strip().lower()
    allowed_task_ids = {
        str(value or "").strip().lower()
        for value in current_user.get("allowed_task_ids") or []
        if str(value or "").strip()
    }
    if not normalized_task_id or normalized_task_id not in allowed_task_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Evaluation key is not authorized for this integration task.",
        )

    try:
        task = get_integration_task(normalized_task_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Evaluation task authority is invalid.",
        ) from exc

    if not task.sandbox_allowed or task.auto_execute_production:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Integration task is not eligible for evaluation sandbox execution.",
        )

    granted_task_scopes = {
        str(value or "").strip()
        for value in current_user.get("task_scope_ids") or []
        if str(value or "").strip()
    }
    missing_scopes = set(task.required_scope_ids) - granted_task_scopes
    if missing_scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Evaluation key is missing required integration task scope authority.",
        )


def _user_id(current_user: dict[str, Any]) -> str:
    return str(
        current_user.get("user_id")
        or current_user.get("sub")
        or ""
    ).strip()


def _route_matches(route: Any) -> bool:
    methods = getattr(route, "methods", set()) or set()
    return (
        getattr(route, "path", "") == _SANDBOX_EXECUTE_PATH
        and "POST" in methods
    )


runtime.settings_module.router.routes[:] = [
    route
    for route in runtime.settings_module.router.routes
    if not _route_matches(route)
]


@runtime.settings_module.router.post(
    "/enterprise-integration/endpoint-bindings/{binding_id}/sandbox-execute",
    response_model=dict,
)
async def guarded_execute_enterprise_endpoint_sandbox_proof(
    binding_id: str,
    body: runtime.EndpointSandboxExecuteRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    if not _is_evaluation_identity(current_user):
        return await runtime.execute_enterprise_endpoint_sandbox_proof(
            binding_id,
            body,
            current_user,
        )

    user_id = _user_id(current_user)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Evaluation identity is incomplete.",
        )

    raw = settings_module._load_raw(user_id)
    spec = runtime._find_binding(raw, binding_id)
    _require_evaluation_task_authority(current_user, spec.task_id)

    try:
        grant = runtime.resolve_active_sandbox_execution_grant(
            raw,
            binding_id=spec.binding_id,
            task_id=spec.task_id,
        )
        request_mapping = runtime._find_request_mapping(raw, binding_id)
        if spec.method in runtime._BODY_METHODS and request_mapping is None:
            raise EndpointRequestMappingError(
                "sandbox request body mapping is required for this endpoint method"
            )
        request_body = (
            build_external_request_body(spec, request_mapping, body.task_input)
            if request_mapping is not None
            else None
        )
        result = await runtime.execute_sandbox_binding(
            spec,
            task_input=body.task_input,
            request_body=request_body,
            approved_operation_classes=set(grant["approved_operation_classes"]),
            approval_reference=str(grant["grant_id"]),
        )
    except (
        ValueError,
        KeyError,
        EndpointBindingError,
        EndpointRequestMappingError,
        SandboxGrantError,
        SandboxExecutionError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    evidence = {
        key: value
        for key, value in result.items()
        if key != "canonical_input"
    }
    evidence["canonical_output_slot"] = result["output_slot"]
    items = runtime._safe_evidence(raw)
    items.append(evidence)
    raw[runtime.SANDBOX_EVIDENCE_STORAGE_KEY] = items[-50:]
    settings_module._save_raw(user_id, raw)
    return result


__all__ = [
    "_is_evaluation_identity",
    "_require_evaluation_task_authority",
    "guarded_execute_enterprise_endpoint_sandbox_proof",
]
