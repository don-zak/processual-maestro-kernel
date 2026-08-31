"""Bounded task execution bridge for governed Evaluation API keys.

This is deliberately a runtime surface, not a provisioning surface. Bindings,
request mappings, customer-scoped secret references, content contracts, and
short-lived execution grants must already exist in the Evaluation owner store.
The Evaluation credential can consume that prepared authority but cannot create
or modify it.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from processual_api.auth.security import require_scope
from processual_api.integrations.enterprise_endpoint_bindings import EndpointBindingError
from processual_api.integrations.enterprise_endpoint_request_mapping import (
    EndpointRequestMappingError,
    build_external_request_body,
)
from processual_api.integrations.enterprise_sandbox_execution import (
    SandboxExecutionError,
    execute_sandbox_binding,
)
from processual_api.integrations.sandbox_secret_resolution import (
    ReferenceSandboxCredentialResolver,
)
from processual_api.integrations.sandbox_verified_transport import VerifiedPeerSandboxTransport
from processual_api.services.enterprise_endpoint_sandbox_grants import (
    SandboxGrantError,
    resolve_active_sandbox_execution_grant,
)
from processual_api.services.evaluation_grants import (
    EVALUATION_EXECUTION_MODE,
    evaluation_task_allowed,
    find_evaluation_grant,
)

from . import settings as settings_router
from . import settings_enterprise_endpoint_bindings_runtime as binding_runtime
from . import settings_enterprise_sandbox_operational_runtime as sandbox_runtime

router = APIRouter(prefix="/evaluation/runtime", tags=["evaluation-runtime"])

EVALUATION_TASK_EVIDENCE_STORAGE_KEY = "evaluation_runtime_task_evidence_v1"
_BODY_METHODS = frozenset({"POST", "PUT", "PATCH"})


class EvaluationRuntimeTaskExecuteRequest(BaseModel):
    task_id: str = Field(min_length=1, max_length=160)
    binding_id: str = Field(min_length=1, max_length=160)
    task_input: dict[str, Any] = Field(default_factory=dict)


def _evaluation_owner_id(current_user: dict[str, Any]) -> str:
    owner_id = str(current_user.get("sub") or current_user.get("user_id") or "").strip()
    if not owner_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Evaluation credential owner is unavailable.",
        )
    return owner_id


def _require_evaluation_credential(
    current_user: dict[str, Any], raw: dict[str, Any]
) -> None:
    if (
        current_user.get("auth_method") != "api_key"
        or current_user.get("entitlement_source") != "admin_evaluation_grant"
        or current_user.get("subscription_required") is not False
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Governed Evaluation Runtime credential required.",
        )
    grant = find_evaluation_grant(raw, str(current_user.get("evaluation_grant_id") or ""))
    if (
        grant is None
        or grant.get("execution_mode") != EVALUATION_EXECUTION_MODE
        or grant.get("real_runtime_execution") is not True
        or grant.get("production_allowed") is not False
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Evaluation runtime authority is unavailable.",
        )


def _authorize_task(
    current_user: dict[str, Any],
    *,
    requested_task_id: str,
    binding_task_id: str,
) -> str:
    requested = str(requested_task_id or "").strip().lower()
    bound = str(binding_task_id or "").strip().lower()
    if not requested or requested != bound:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Evaluation task does not match the prepared endpoint binding.",
        )
    if not evaluation_task_allowed(current_user, requested):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Evaluation grant does not allow this canonical task.",
        )
    return requested


def _append_evidence(raw: dict[str, Any], evidence: dict[str, Any]) -> None:
    items = raw.get(EVALUATION_TASK_EVIDENCE_STORAGE_KEY, [])
    if not isinstance(items, list):
        items = []
    items.append(evidence)
    raw[EVALUATION_TASK_EVIDENCE_STORAGE_KEY] = items[-100:]


@router.post("/task-execute", response_model=dict)
async def execute_evaluation_runtime_task(
    body: EvaluationRuntimeTaskExecuteRequest,
    current_user: dict = Depends(require_scope("run:evaluation")),
) -> dict[str, Any]:
    """Execute one prepared external operation under evaluation-only authority."""

    owner_id = _evaluation_owner_id(current_user)
    raw = settings_router._load_raw(owner_id)
    _require_evaluation_credential(current_user, raw)
    spec = binding_runtime._find_binding(raw, body.binding_id)
    task_id = _authorize_task(
        current_user,
        requested_task_id=body.task_id,
        binding_task_id=spec.task_id,
    )

    content = sandbox_runtime._content_contract(raw, spec.binding_id)
    secret_reference = sandbox_runtime._secret_reference(raw, spec.binding_id)
    if content is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Prepared evaluation content contract is required.",
        )
    if secret_reference is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Prepared evaluation secret reference is required.",
        )

    try:
        execution_grant = resolve_active_sandbox_execution_grant(
            raw,
            binding_id=spec.binding_id,
            task_id=task_id,
        )
        request_mapping = binding_runtime._find_request_mapping(raw, spec.binding_id)
        if spec.method in _BODY_METHODS and request_mapping is None:
            raise EndpointRequestMappingError(
                "evaluation request body mapping is required for this binding"
            )
        request_body = (
            build_external_request_body(spec, request_mapping, body.task_input)
            if request_mapping is not None
            else None
        )
        resolver = ReferenceSandboxCredentialResolver(secret_reference)
        transport = VerifiedPeerSandboxTransport()
        result = await execute_sandbox_binding(
            spec,
            task_input=body.task_input,
            request_body=request_body,
            approved_operation_classes=set(
                execution_grant["approved_operation_classes"]
            ),
            approval_reference=str(execution_grant["grant_id"]),
            credential_resolver=resolver,
            transport=transport,
        )
        if not transport.last_verified_peer:
            raise SandboxExecutionError("evaluation_peer_address_unverified")
    except (
        ValueError,
        KeyError,
        EndpointBindingError,
        EndpointRequestMappingError,
        SandboxGrantError,
        SandboxExecutionError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    evidence = {
        "execution_id": result.get("execution_id"),
        "evaluation_grant_id": current_user.get("evaluation_grant_id"),
        "api_key_id": current_user.get("api_key_id"),
        "binding_id": spec.binding_id,
        "task_id": task_id,
        "adapter_contract_id": spec.adapter_contract_id,
        "operation_class": result.get("operation_class"),
        "http_status": result.get("http_status"),
        "network_request_executed": result.get("network_request_executed") is True,
        "mapping_valid": result.get("mapping_valid") is True,
        "ready_for_task_consumption": result.get("ready_for_task_consumption") is True,
        "response_sha256": result.get("response_sha256"),
        "task_injection_sha256": result.get("task_injection_sha256"),
        "evidence_sha256": result.get("evidence_sha256"),
        "completed_at": result.get("completed_at"),
        "evaluation_stage": "external_operation_executed",
        "maestro_task_completed": False,
        "raw_task_input_persisted": False,
        "raw_secret_visible": False,
    }
    _append_evidence(raw, evidence)
    settings_router._save_raw(owner_id, raw)

    return {
        **result,
        "evaluation_runtime": True,
        "evaluation_grant_id": current_user.get("evaluation_grant_id"),
        "task_authority_enforced": True,
        "subscription_required": False,
        "commercial_quota_required": False,
        "production_allowed": False,
        "evaluation_stage": "external_operation_executed",
        "maestro_task_completed": False,
        "next_readiness_stage": "maestro_task_consumption",
        "raw_task_input_persisted": False,
        "raw_secret_visible": False,
    }


__all__ = [
    "EVALUATION_TASK_EVIDENCE_STORAGE_KEY",
    "EvaluationRuntimeTaskExecuteRequest",
    "execute_evaluation_runtime_task",
    "router",
]
