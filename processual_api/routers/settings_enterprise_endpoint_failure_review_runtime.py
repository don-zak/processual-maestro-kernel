"""Failure review and recovery routes for Enterprise sandbox endpoint runs."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Request, status

from processual_api.auth.security import get_current_user
from processual_api.services.enterprise_endpoint_failure_review import (
    list_safe_sandbox_failures,
    mark_failure_reviewing,
    record_sandbox_failure,
    resolve_failures_after_success,
)
from processual_api.services.supervisor_session_write_guard import (
    SupervisorSessionWriteGuardError,
    require_validated_supervisor_write_session,
)
from processual_api.supervision_rbac import QUALIFICATION_REVIEW_SCOPE

from . import settings as settings_module
from . import settings_enterprise_endpoint_bindings_runtime as endpoint_runtime


def _require_supervisor_review_session(request: Request) -> None:
    try:
        require_validated_supervisor_write_session(
            request,
            {QUALIFICATION_REVIEW_SCOPE},
            guard_name="enterprise_endpoint_failure_review",
        )
    except SupervisorSessionWriteGuardError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc


@settings_module.router.get(
    "/enterprise-integration/sandbox-failures",
    response_model=dict,
)
async def list_enterprise_endpoint_sandbox_failures(
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    _, raw = endpoint_runtime._require_enterprise(current_user)
    failures = list_safe_sandbox_failures(raw)
    return {
        "environment": "sandbox",
        "failure_count": len(failures),
        "open_count": sum(item["status"] == "open" for item in failures),
        "reviewing_count": sum(item["status"] == "reviewing" for item in failures),
        "resolved_count": sum(item["status"] == "resolved" for item in failures),
        "failures": failures,
        "production_allowed": False,
        "runtime_connector_approved": False,
        "raw_secret_visible": False,
        "raw_error_visible": False,
    }


@settings_module.router.post(
    "/enterprise-integration/endpoint-bindings/{binding_id}/reviewed-sandbox-execute",
    response_model=dict,
)
async def execute_enterprise_endpoint_reviewed_sandbox_proof(
    binding_id: str,
    body: endpoint_runtime.EndpointSandboxExecuteRequest,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    user_id, raw = endpoint_runtime._require_enterprise(current_user)
    spec = endpoint_runtime._find_binding(raw, binding_id)
    try:
        result = await endpoint_runtime.execute_enterprise_endpoint_sandbox_proof(
            binding_id,
            body,
            current_user,
        )
    except HTTPException as exc:
        failure = record_sandbox_failure(
            raw,
            binding_id=spec.binding_id,
            task_id=spec.task_id,
            exc=exc,
        )
        settings_module._save_raw(user_id, raw)
        raise HTTPException(
            status_code=exc.status_code,
            detail={
                "message": "Sandbox proof failed and was recorded for review.",
                "failure": failure,
            },
        ) from exc

    refreshed = settings_module._load_raw(user_id)
    resolved = resolve_failures_after_success(
        refreshed,
        binding_id=spec.binding_id,
        task_id=spec.task_id,
        evidence_sha256=str(result.get("evidence_sha256") or ""),
    )
    settings_module._save_raw(user_id, refreshed)
    return {
        **result,
        "failure_review": {
            "resolved_failure_count": resolved,
            "resolution_code": (
                "successful_sandbox_retest" if resolved else "no_open_failure"
            ),
        },
    }


@settings_module.router.post(
    "/admin/integration-tasks/{client_id}/sandbox-failures/{failure_id}/review",
    response_model=dict,
)
async def review_enterprise_endpoint_sandbox_failure(
    client_id: str,
    failure_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    del current_user
    _require_supervisor_review_session(request)
    raw = settings_module._load_raw(client_id)
    try:
        failure = mark_failure_reviewing(raw, failure_id=failure_id)
    except ValueError as exc:
        code = str(exc)
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
                if code == "sandbox_failure_not_found"
                else status.HTTP_409_CONFLICT
            ),
            detail=code,
        ) from exc
    settings_module._save_raw(client_id, raw)
    return {
        "status": "reviewing",
        "failure": failure,
        "production_allowed": False,
        "runtime_connector_approved": False,
    }


__all__ = [
    "execute_enterprise_endpoint_reviewed_sandbox_proof",
    "list_enterprise_endpoint_sandbox_failures",
    "review_enterprise_endpoint_sandbox_failure",
]
