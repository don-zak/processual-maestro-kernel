"""Bounded task execution bridge for governed External Evaluation API keys.

All Evaluation execution authority is loaded from the shared PostgreSQL
snapshot sealed when the platform administrator creates the grant. No runtime
authority decision depends on replica-local settings files.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from processual_api.auth.security import get_current_user, require_scope
from processual_api.integrations.enterprise_endpoint_bindings import EndpointBindingError
from processual_api.integrations.enterprise_endpoint_request_mapping import (
    EndpointRequestMappingError,
    build_external_request_body,
)
from processual_api.integrations.enterprise_sandbox_execution import (
    SandboxExecutionError,
    execute_sandbox_binding,
)
from processual_api.integrations.integration_task_catalog import get_integration_task
from processual_api.integrations.sandbox_secret_resolution import (
    ReferenceSandboxCredentialResolver,
)
from processual_api.integrations.sandbox_verified_transport import VerifiedPeerSandboxTransport
from processual_api.services.evaluation_authority_postgres import (
    EvaluationAuthorityError,
    evaluation_key_runtime_status,
    load_evaluation_authority_state,
)
from processual_api.services.evaluation_grants import (
    EVALUATION_EXECUTION_MODE,
    evaluation_binding_allowed,
    evaluation_task_allowed,
    find_evaluation_grant,
    refresh_evaluation_grant_status,
)
from processual_api.services.evaluation_runtime_delivery_postgres import (
    EvaluationDeliveryError,
    EvaluationIdempotencyConflictError,
    EvaluationQuotaExceededError,
    EvaluationReplayBlockedError,
    claim_evaluation_execution,
    complete_evaluation_execution,
    evaluation_request_fingerprint,
    fail_evaluation_execution,
    get_evaluation_execution_status,
    latest_evaluation_execution_status,
)

from . import settings_enterprise_endpoint_bindings_runtime as binding_runtime
from . import settings_enterprise_sandbox_operational_runtime as sandbox_runtime

logger = logging.getLogger("processual_api.routers.evaluation_runtime")
router = APIRouter(prefix="/evaluation/runtime", tags=["evaluation-runtime"])

EVALUATION_TASK_EVIDENCE_STORAGE_KEY = "evaluation_runtime_task_evidence_v1"
_BODY_METHODS = frozenset({"POST", "PUT", "PATCH"})
_SAFE_REPLAY_RESULT_KEYS = frozenset(
    {
        "status",
        "execution_id",
        "environment",
        "binding_id",
        "task_id",
        "adapter_contract_id",
        "operation_class",
        "required_scope_ids",
        "output_slot",
        "canonical_input_sha256",
        "task_injection_schema_version",
        "task_injection_sha256",
        "ready_for_task_consumption",
        "request_body_sha256",
        "request_body_included_in_evidence",
        "http_status",
        "content_type",
        "destination_host",
        "resolved_address_count",
        "response_sha256",
        "approval_reference",
        "credential_source",
        "credential_material_included",
        "raw_response_included",
        "redirects_followed",
        "mapping_valid",
        "network_request_executed",
        "evidence_sha256",
        "completed_at",
        "production_allowed",
        "review_required",
        "applied",
        "production_mutation_performed",
        "runtime_connector_approved",
        "raw_secret_visible",
        "evaluation_runtime",
        "evaluation_grant_id",
        "task_authority_enforced",
        "subscription_required",
        "commercial_quota_required",
        "evaluation_stage",
        "maestro_task_completed",
        "next_readiness_stage",
        "raw_task_input_persisted",
        "quota",
        "execution_status",
    }
)


class EvaluationRuntimeTaskExecuteRequest(BaseModel):
    task_id: str = Field(min_length=1, max_length=160)
    binding_id: str = Field(min_length=1, max_length=160)
    idempotency_key: str = Field(min_length=8, max_length=200)
    task_input: dict[str, Any] = Field(default_factory=dict)

    @field_validator("idempotency_key")
    @classmethod
    def _normalize_idempotency_key(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 8:
            raise ValueError(
                "idempotency_key must contain at least 8 non-whitespace characters"
            )
        return normalized


def _evaluation_owner_id(current_user: dict[str, Any]) -> str:
    owner_id = str(current_user.get("sub") or current_user.get("user_id") or "").strip()
    if not owner_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Evaluation credential owner is unavailable.",
        )
    return owner_id


def _evaluation_identity(current_user: dict[str, Any]) -> tuple[str, str, str]:
    if (
        current_user.get("auth_method") != "api_key"
        or current_user.get("entitlement_source") != "admin_evaluation_grant"
        or current_user.get("subscription_required") is not False
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Governed Evaluation credential required.",
        )
    owner_id = _evaluation_owner_id(current_user)
    grant_id = str(current_user.get("evaluation_grant_id") or "").strip()
    api_key_id = str(current_user.get("api_key_id") or "").strip()
    if not grant_id or not api_key_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Governed Evaluation credential required.",
        )
    return owner_id, grant_id, api_key_id


def _require_evaluation_credential(
    current_user: dict[str, Any], raw: dict[str, Any]
) -> None:
    _evaluation_identity(current_user)
    grant = find_evaluation_grant(
        raw,
        str(current_user.get("evaluation_grant_id") or ""),
    )
    if grant is not None:
        refresh_evaluation_grant_status(grant)
    if (
        grant is None
        or grant.get("status") != "active"
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


def _prepared_runtime_operation_classes(
    raw: dict[str, Any],
    *,
    spec: Any,
    request_mapping: Any,
    content: Any,
    secret_reference: Any,
) -> set[str]:
    """Require persisted matching live proof, not a transient supervisor TTL grant."""

    evidence = next(
        (
            item
            for item in reversed(binding_runtime._safe_evidence(raw))
            if str(item.get("binding_id") or "") == spec.binding_id
            and str(item.get("task_id") or "") == spec.task_id
        ),
        None,
    )
    if evidence is None:
        raise ValueError("persisted matching sandbox proof is required for Evaluation runtime")

    expected_provisioning_sha256 = sandbox_runtime._provisioning_sha256(
        spec=spec,
        request_mapping=request_mapping,
        secret_reference=secret_reference,
        content=content,
    )
    proof_valid = (
        evidence.get("operational_proof") is True
        and evidence.get("peer_address_verified") is True
        and evidence.get("network_request_executed") is True
        and evidence.get("mapping_valid") is True
        and evidence.get("ready_for_task_consumption") is True
        and evidence.get("production_allowed") is False
        and str(evidence.get("provisioning_sha256") or "")
        == expected_provisioning_sha256
    )
    if not proof_valid:
        raise ValueError("prepared Evaluation binding proof is stale or incomplete")

    task = get_integration_task(spec.task_id)
    if not task.sandbox_allowed or task.auto_execute_production:
        raise ValueError("Evaluation runtime task is not sandbox eligible")
    return {str(task.operation_class)}


def _safe_replay_response(response: dict[str, Any]) -> dict[str, Any]:
    safe = {key: value for key, value in response.items() if key in _SAFE_REPLAY_RESULT_KEYS}
    safe["canonical_input_included"] = False
    safe["raw_response_included"] = False
    safe["raw_task_input_persisted"] = False
    safe["raw_secret_visible"] = False
    return safe


def _delivery_http_error(exc: EvaluationDeliveryError) -> HTTPException:
    if isinstance(exc, EvaluationQuotaExceededError):
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Evaluation execution quota is exhausted.",
        )
    if isinstance(exc, EvaluationIdempotencyConflictError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotency key was already used with a different evaluation request.",
        )
    if isinstance(exc, EvaluationReplayBlockedError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A prior execution with this idempotency key has an unresolved or failed "
                "network outcome; automatic replay is blocked to prevent duplicate side effects."
            ),
        )
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Evaluation execution delivery ledger is unavailable.",
    )


async def _customer_status_snapshot(current_user: dict[str, Any]) -> dict[str, Any]:
    owner_id, grant_id, api_key_id = _evaluation_identity(current_user)
    try:
        credential = await evaluation_key_runtime_status(owner_id, grant_id, api_key_id)
        latest = await latest_evaluation_execution_status(owner_id, grant_id, api_key_id)
    except (EvaluationAuthorityError, EvaluationDeliveryError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Evaluation status is temporarily unavailable.",
        ) from exc
    return {
        **credential,
        "latest_execution": latest,
        "status_endpoint_consumes_quota": False,
        "raw_secret_visible": False,
        "production_allowed": False,
    }


async def _decorate_execution_with_status(
    response: dict[str, Any],
    current_user: dict[str, Any],
    *,
    execution_id: str,
) -> None:
    """Attach fresh quota and the receipt for this exact admitted execution."""

    owner_id, grant_id, api_key_id = _evaluation_identity(current_user)
    try:
        credential = await evaluation_key_runtime_status(owner_id, grant_id, api_key_id)
        receipt = await get_evaluation_execution_status(
            owner_id,
            grant_id,
            api_key_id,
            execution_id,
        )
    except (EvaluationAuthorityError, EvaluationDeliveryError):
        return
    response["quota"] = credential["quota"]
    response["execution_status"] = receipt


@router.get("/status", response_model=dict)
async def evaluation_runtime_status(
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Customer-facing credential, quota, and latest-execution status."""
    return await _customer_status_snapshot(current_user)


@router.get("/executions/{execution_id}", response_model=dict)
async def evaluation_runtime_execution_status(
    execution_id: str,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    owner_id, grant_id, api_key_id = _evaluation_identity(current_user)
    try:
        receipt = await get_evaluation_execution_status(
            owner_id,
            grant_id,
            api_key_id,
            execution_id,
        )
    except EvaluationDeliveryError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Evaluation execution status is temporarily unavailable.",
        ) from exc
    if receipt is None:
        raise HTTPException(status_code=404, detail="Evaluation execution not found.")
    return {
        "execution": receipt,
        "status_endpoint_consumes_quota": False,
        "raw_secret_visible": False,
        "production_allowed": False,
    }


@router.post("/task-execute", response_model=dict)
async def execute_evaluation_runtime_task(
    body: EvaluationRuntimeTaskExecuteRequest,
    current_user: dict = Depends(require_scope("run:evaluation")),
) -> dict[str, Any]:
    owner_id = _evaluation_owner_id(current_user)
    try:
        raw = await load_evaluation_authority_state(owner_id)
    except EvaluationAuthorityError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Shared Evaluation runtime authority is unavailable.",
        ) from exc

    _require_evaluation_credential(current_user, raw)
    if not evaluation_binding_allowed(current_user, body.binding_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Evaluation grant does not allow this prepared binding.",
        )
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

    grant_id = str(current_user.get("evaluation_grant_id") or "")
    api_key_id = str(current_user.get("api_key_id") or "")
    try:
        request_mapping = binding_runtime._find_request_mapping(raw, spec.binding_id)
        if spec.method in _BODY_METHODS and request_mapping is None:
            raise EndpointRequestMappingError(
                "evaluation request body mapping is required for this binding"
            )
        approved_operation_classes = _prepared_runtime_operation_classes(
            raw,
            spec=spec,
            request_mapping=request_mapping,
            content=content,
            secret_reference=secret_reference,
        )
        request_body = (
            build_external_request_body(spec, request_mapping, body.task_input)
            if request_mapping is not None
            else None
        )
    except (
        ValueError,
        KeyError,
        EndpointBindingError,
        EndpointRequestMappingError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    request_fingerprint = evaluation_request_fingerprint(
        grant_id=grant_id,
        api_key_id=api_key_id,
        task_id=task_id,
        binding_id=spec.binding_id,
        task_input=body.task_input,
    )
    try:
        claim = await claim_evaluation_execution(
            owner_id=owner_id,
            grant_id=grant_id,
            api_key_id=api_key_id,
            idempotency_key=body.idempotency_key,
            request_fingerprint=request_fingerprint,
            task_id=task_id,
            binding_id=spec.binding_id,
        )
    except EvaluationDeliveryError as exc:
        raise _delivery_http_error(exc) from exc

    record_id = str(claim["record"]["record_id"])
    if claim["status"] == "replay":
        replay_response = dict(claim["response"])
        replay_response["idempotent_replay"] = True
        await _decorate_execution_with_status(
            replay_response,
            current_user,
            execution_id=record_id,
        )
        return replay_response

    try:
        resolver = ReferenceSandboxCredentialResolver(secret_reference)
        transport = VerifiedPeerSandboxTransport()
        result = await execute_sandbox_binding(
            spec,
            task_input=body.task_input,
            request_body=request_body,
            approved_operation_classes=approved_operation_classes,
            approval_reference=grant_id,
            credential_resolver=resolver,
            transport=transport,
        )
        if not transport.last_verified_peer:
            raise SandboxExecutionError("evaluation_peer_address_unverified")
    except (ValueError, KeyError, SandboxExecutionError) as exc:
        try:
            await fail_evaluation_execution(
                owner_id=owner_id,
                record_id=record_id,
                failure_code=type(exc).__name__,
            )
        except EvaluationDeliveryError:
            logger.exception("Failed to persist evaluation execution failure state")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    evidence = {
        "execution_id": result.get("execution_id"),
        "evaluation_grant_id": grant_id,
        "api_key_id": api_key_id,
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
        "review_required": result.get("review_required"),
        "applied": result.get("applied"),
        "production_mutation_performed": result.get("production_mutation_performed"),
        "production_allowed": False,
        "evaluation_stage": "external_operation_executed",
        "maestro_task_completed": False,
        "raw_task_input_persisted": False,
        "raw_secret_visible": False,
    }
    response = {
        **result,
        "evaluation_runtime": True,
        "evaluation_grant_id": grant_id,
        "task_authority_enforced": True,
        "subscription_required": False,
        "commercial_quota_required": False,
        "production_allowed": False,
        "evaluation_stage": "external_operation_executed",
        "maestro_task_completed": False,
        "next_readiness_stage": "maestro_task_consumption",
        "raw_task_input_persisted": False,
        "raw_secret_visible": False,
        "idempotent_replay": False,
    }
    try:
        await complete_evaluation_execution(
            owner_id=owner_id,
            record_id=record_id,
            evidence=evidence,
            replay_response=_safe_replay_response(response),
        )
    except EvaluationDeliveryError as exc:
        logger.exception("External execution completed but durable evidence commit failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "External execution outcome could not be durably finalized; replay is blocked "
                "for this idempotency key pending operator reconciliation."
            ),
        ) from exc

    await _decorate_execution_with_status(
        response,
        current_user,
        execution_id=record_id,
    )
    return response


__all__ = [
    "EVALUATION_TASK_EVIDENCE_STORAGE_KEY",
    "EvaluationRuntimeTaskExecuteRequest",
    "evaluation_runtime_execution_status",
    "evaluation_runtime_status",
    "execute_evaluation_runtime_task",
    "router",
]
