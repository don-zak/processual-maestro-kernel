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
from processual_api.integrations.integration_task_catalog import get_integration_task
from processual_api.integrations.integration_task_completion import (
    IntegrationTaskCompletionError,
    complete_mapped_read_task,
)
from processual_api.integrations.sandbox_secret_resolution import (
    ReferenceSandboxCredentialResolver,
)
from processual_api.integrations.sandbox_verified_transport import VerifiedPeerSandboxTransport
from processual_api.services.enterprise_endpoint_sandbox_grants import (
    SandboxGrantError,
    resolve_active_sandbox_execution_grant,
)
from processual_api.services.evaluation_grants import evaluation_task_allowed
from processual_api.services.evaluation_idempotency import (
    reserve_evaluation_execution,
    update_evaluation_execution_reservation,
)
from processual_api.services.evaluation_outcome_runtime import (
    evaluate_completed_task_outcome,
)

from . import cgt_governor as runtime_host
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
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=160)


def _evaluation_owner_id(current_user: dict[str, Any]) -> str:
    owner_id = str(current_user.get("sub") or current_user.get("user_id") or "").strip()
    if not owner_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Evaluation credential owner is unavailable.",
        )
    return owner_id


def _require_evaluation_credential(current_user: dict[str, Any]) -> None:
    if (
        current_user.get("auth_method") != "api_key"
        or current_user.get("entitlement_source") != "admin_evaluation_grant"
        or current_user.get("execution_mode") != "evaluation_runtime"
        or current_user.get("real_runtime_execution") is not True
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Governed Evaluation Runtime credential required.",
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


def _completion_from_external_result(
    *,
    task_id: str,
    binding_id: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    """Derive truthful task completion without promoting draft/write handoffs."""

    try:
        return complete_mapped_read_task(
            task_id=task_id,
            binding_id=binding_id,
            canonical_input=dict(result.get("canonical_input") or {}),
            expected_output_slot=str(result.get("output_slot") or ""),
        )
    except IntegrationTaskCompletionError as exc:
        return {
            "maestro_task_completed": False,
            "completion_stage": "downstream_consumer_required",
            "dedicated_downstream_consumer_required": True,
            "completion_reason": str(exc),
            "production_allowed": False,
            "raw_secret_visible": False,
        }


@router.post("/task-execute", response_model=dict)
async def execute_evaluation_runtime_task(
    body: EvaluationRuntimeTaskExecuteRequest,
    current_user: dict = Depends(require_scope("run:evaluation")),
) -> dict[str, Any]:
    """Execute one pre-provisioned external operation for an allowed canonical task.

    Canonical READ completion and Evaluation success are deliberately separate.
    Completed READ tasks receive semantic outcome validation. Non-READ tasks
    require a fail-closed idempotency reservation before the network request so
    a timeout or ambiguous external failure cannot be silently retried into a
    duplicate side effect.
    """

    _require_evaluation_credential(current_user)
    owner_id = _evaluation_owner_id(current_user)
    raw = settings_router._load_raw(owner_id)
    spec = binding_runtime._find_binding(raw, body.binding_id)
    task_id = _authorize_task(
        current_user,
        requested_task_id=body.task_id,
        binding_task_id=spec.task_id,
    )
    task = get_integration_task(task_id)
    non_read_task = str(task.operation_class) != "read"
    if non_read_task and not body.idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Non-READ Evaluation tasks require an idempotency_key before external execution.",
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

    reservation: dict[str, Any] | None = None
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
        if non_read_task:
            reservation = reserve_evaluation_execution(
                raw,
                idempotency_key=str(body.idempotency_key or ""),
                task_id=task_id,
                binding_id=spec.binding_id,
                task_input=body.task_input,
                api_key_id=str(current_user.get("api_key_id") or ""),
                evaluation_grant_id=str(current_user.get("evaluation_grant_id") or ""),
            )
            if reservation["status"] == "conflict":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Idempotency key was already used for a different Evaluation request.",
                )
            if reservation["status"] == "duplicate":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Duplicate non-READ Evaluation execution blocked before network; "
                        f"previous state: {reservation.get('previous_state') or 'unknown'}."
                    ),
                )
            settings_router._save_raw(owner_id, raw)

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
    except HTTPException:
        raise
    except (
        ValueError,
        KeyError,
        EndpointBindingError,
        EndpointRequestMappingError,
        SandboxGrantError,
        SandboxExecutionError,
    ) as exc:
        if reservation and reservation.get("reservation_id"):
            update_evaluation_execution_reservation(
                raw,
                reservation_id=str(reservation["reservation_id"]),
                state="network_or_response_failure_uncertain",
            )
            settings_router._save_raw(owner_id, raw)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    if reservation and reservation.get("reservation_id"):
        update_evaluation_execution_reservation(
            raw,
            reservation_id=str(reservation["reservation_id"]),
            state="external_execution_completed",
            execution_id=str(result.get("execution_id") or ""),
            evidence_sha256=str(result.get("evidence_sha256") or ""),
        )

    completion = _completion_from_external_result(
        task_id=task_id,
        binding_id=spec.binding_id,
        result=result,
    )
    task_completed = completion["maestro_task_completed"] is True
    outcome = evaluate_completed_task_outcome(
        raw=raw,
        binding_id=spec.binding_id,
        task_id=task_id,
        canonical_result=dict(result.get("canonical_input") or {}),
        content_contract=content,
        maestro_task_completed=task_completed,
    )
    outcome_passed = outcome.get("outcome_validation_passed") is True
    evaluation_stage = (
        "outcome_validated"
        if task_completed and outcome_passed
        else "canonical_task_completed"
        if task_completed
        else "external_operation_executed"
    )

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
        "external_evidence_sha256": result.get("evidence_sha256"),
        "task_completion_sha256": completion.get("completion_sha256"),
        "completion_stage": completion.get("completion_stage"),
        "outcome_validation_status": outcome.get("outcome_validation_status"),
        "outcome_validation_passed": outcome_passed,
        "outcome_validation_sha256": outcome.get("outcome_validation_sha256"),
        "expectation_sha256": outcome.get("expectation_sha256"),
        "field_check_count": outcome.get("field_check_count", 0),
        "matched_field_count": outcome.get("matched_field_count", 0),
        "idempotency_required": non_read_task,
        "idempotency_reservation_id": (reservation or {}).get("reservation_id"),
        "idempotency_request_sha256": (reservation or {}).get("request_sha256"),
        "completed_at": result.get("completed_at"),
        "evaluation_stage": evaluation_stage,
        "maestro_task_completed": task_completed,
        "raw_task_input_persisted": False,
        "raw_idempotency_key_persisted": False,
        "raw_expected_values_persisted": False,
        "raw_secret_visible": False,
    }
    _append_evidence(raw, evidence)
    settings_router._save_raw(owner_id, raw)

    return {
        **result,
        **completion,
        **outcome,
        "evaluation_runtime": True,
        "evaluation_grant_id": current_user.get("evaluation_grant_id"),
        "task_authority_enforced": True,
        "evaluation_stage": evaluation_stage,
        "idempotency_required": non_read_task,
        "idempotency_enforced": bool(non_read_task and reservation),
        "next_readiness_stage": (
            "failure_retry_validation"
            if task_completed and outcome_passed
            else "outcome_quality_validation"
            if task_completed
            else "maestro_task_consumption"
        ),
        "raw_task_input_persisted": False,
        "raw_idempotency_key_persisted": False,
        "raw_expected_values_persisted": False,
        "raw_secret_visible": False,
    }


# cgt_governor.router is an already-registered root runtime router with no
# prefix. Hosting this sub-router there preserves the explicit
# /evaluation/runtime/* path without routing Evaluation keys through /settings.
runtime_host.router.include_router(router)


__all__ = [
    "EVALUATION_TASK_EVIDENCE_STORAGE_KEY",
    "EvaluationRuntimeTaskExecuteRequest",
    "execute_evaluation_runtime_task",
    "router",
]
