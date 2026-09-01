"""Platform-admin provisioning for standalone External Evaluation bindings.

This surface deliberately reuses the hardened Enterprise binding, request-mapping,
content-contract, secret-reference, sandbox-grant, and verified-peer execution
contracts without requiring a commercial Enterprise entitlement. It writes only
sandbox authority into the Evaluation owner's settings store and never enables
production execution.
"""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from processual_api.auth.platform_admin_authority import require_active_platform_admin
from processual_api.auth.security import get_current_user
from processual_api.integrations.enterprise_endpoint_bindings import (
    BINDING_STORAGE_KEY,
    EndpointBindingError,
    EnterpriseEndpointBindingSpec,
    safe_binding_payload,
    validate_endpoint_binding,
)
from processual_api.integrations.enterprise_endpoint_request_mapping import (
    REQUEST_MAPPING_STORAGE_KEY,
    EndpointRequestMappingError,
    EnterpriseEndpointRequestMappingSpec,
    build_external_request_body,
    validate_request_mapping,
)
from processual_api.integrations.enterprise_sandbox_execution import (
    SandboxExecutionError,
    execute_sandbox_binding,
)
from processual_api.integrations.sandbox_operational_readiness import (
    SANDBOX_CONTENT_STORAGE_KEY,
    SANDBOX_SECRET_REFERENCE_STORAGE_KEY,
    SandboxContentContract,
    SandboxSecretReference,
    safe_content_projection,
    safe_secret_reference_projection,
)
from processual_api.integrations.sandbox_secret_resolution import (
    ReferenceSandboxCredentialResolver,
)
from processual_api.integrations.sandbox_verified_transport import VerifiedPeerSandboxTransport
from processual_api.services.enterprise_endpoint_sandbox_grants import (
    SandboxGrantError,
    issue_sandbox_execution_grant,
    resolve_active_sandbox_execution_grant,
    safe_grant_projection,
)

from . import settings as settings_module
from . import settings_enterprise_endpoint_bindings_runtime as binding_runtime
from . import settings_enterprise_sandbox_operational_runtime as sandbox_runtime

_BODY_METHODS = frozenset({"POST", "PUT", "PATCH"})


class EvaluationBindingProvisionRequest(BaseModel):
    binding: EnterpriseEndpointBindingSpec
    request_mapping: EnterpriseEndpointRequestMappingSpec | None = None
    content_contract: SandboxContentContract
    secret_reference: SandboxSecretReference
    ttl_minutes: int = Field(default=30, ge=5, le=120)


def _owner_user_id(current_user: dict[str, Any]) -> str:
    return str(current_user.get("sub") or current_user.get("user_id") or "default")


def _actor(current_user: dict[str, Any]) -> str:
    return str(
        current_user.get("email")
        or current_user.get("sub")
        or current_user.get("user_id")
        or "platform_admin"
    ).strip()


def _stored_items(raw: dict[str, Any], key: str) -> list[dict[str, Any]]:
    values = raw.get(key, [])
    if not isinstance(values, list):
        return []
    return [dict(value) for value in values if isinstance(value, dict)]


def _replace_by_binding(
    raw: dict[str, Any],
    key: str,
    binding_id: str,
    value: dict[str, Any],
) -> None:
    items = _stored_items(raw, key)
    for index, item in enumerate(items):
        if str(item.get("binding_id") or "") == binding_id:
            items[index] = value
            break
    else:
        items.append(value)
    raw[key] = items


def _remove_by_binding(raw: dict[str, Any], key: str, binding_id: str) -> None:
    raw[key] = [
        item
        for item in _stored_items(raw, key)
        if str(item.get("binding_id") or "") != binding_id
    ]


def _validate_binding_ids(
    binding_id: str,
    body: EvaluationBindingProvisionRequest,
) -> None:
    identifiers = {
        "binding": body.binding.binding_id,
        "content contract": body.content_contract.binding_id,
        "secret reference": body.secret_reference.binding_id,
    }
    if body.request_mapping is not None:
        identifiers["request mapping"] = body.request_mapping.binding_id
    for label, value in identifiers.items():
        if value != binding_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Path binding id must match {label} binding id.",
            )


@settings_module.router.put(
    "/admin/evaluation-grants/bindings/{binding_id}/provision",
    response_model=dict,
)
async def provision_evaluation_binding(
    binding_id: str,
    body: EvaluationBindingProvisionRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Prepare one sandbox-only binding for later External Evaluation grants."""

    await require_active_platform_admin(current_user, request)
    _validate_binding_ids(binding_id, body)

    try:
        binding_validation = validate_endpoint_binding(body.binding)
        safe_binding = safe_binding_payload(body.binding)
        if body.binding.method in _BODY_METHODS and body.request_mapping is None:
            raise EndpointRequestMappingError(
                "evaluation request body mapping is required for this binding"
            )
        mapping_validation = (
            validate_request_mapping(body.binding, body.request_mapping)
            if body.request_mapping is not None
            else None
        )
    except (
        ValueError,
        KeyError,
        EndpointBindingError,
        EndpointRequestMappingError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    owner_id = _owner_user_id(current_user)
    raw = settings_module._load_raw(owner_id)

    _replace_by_binding(
        raw,
        BINDING_STORAGE_KEY,
        binding_id,
        body.binding.model_dump(mode="json"),
    )
    if body.request_mapping is not None:
        _replace_by_binding(
            raw,
            REQUEST_MAPPING_STORAGE_KEY,
            binding_id,
            body.request_mapping.model_dump(mode="json"),
        )
    else:
        _remove_by_binding(raw, REQUEST_MAPPING_STORAGE_KEY, binding_id)
    _replace_by_binding(
        raw,
        SANDBOX_CONTENT_STORAGE_KEY,
        binding_id,
        body.content_contract.model_dump(mode="json"),
    )
    _replace_by_binding(
        raw,
        SANDBOX_SECRET_REFERENCE_STORAGE_KEY,
        binding_id,
        body.secret_reference.model_dump(mode="json"),
    )

    try:
        sandbox_grant = issue_sandbox_execution_grant(
            raw,
            spec=body.binding,
            supervisor_id=_actor(current_user),
            ttl_minutes=body.ttl_minutes,
        )
    except (ValueError, KeyError, EndpointBindingError, SandboxGrantError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    settings_module._save_raw(owner_id, raw)
    return {
        "status": "provisioned",
        "persisted": True,
        "binding": safe_binding,
        "binding_validation": binding_validation,
        "request_mapping_configured": body.request_mapping is not None,
        "request_mapping_validation": mapping_validation,
        "content_contract": safe_content_projection(body.content_contract),
        "secret_reference": safe_secret_reference_projection(body.secret_reference),
        "sandbox_grant": safe_grant_projection(sandbox_grant),
        "selection_authority": "admin_evaluation_grant",
        "subscription_required": False,
        "registration_required": False,
        "commercial_quota_required": False,
        "production_allowed": False,
        "runtime_connector_approved": False,
        "raw_secret_visible": False,
        "raw_payload_visible": False,
    }


@settings_module.router.post(
    "/admin/evaluation-grants/bindings/{binding_id}/sandbox-operational-execute",
    response_model=dict,
)
async def execute_evaluation_sandbox_operational_proof(
    binding_id: str,
    body: binding_runtime.EndpointSandboxExecuteRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Run hardened sandbox proof for a standalone Evaluation binding."""

    await require_active_platform_admin(current_user, request)
    owner_id = _owner_user_id(current_user)
    raw = settings_module._load_raw(owner_id)
    spec = binding_runtime._find_binding(raw, binding_id)
    content = sandbox_runtime._content_contract(raw, binding_id)
    secret_reference = sandbox_runtime._secret_reference(raw, binding_id)
    if content is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Sandbox content contract is required before operational execution.",
        )
    if secret_reference is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Customer sandbox secret reference is required before operational execution.",
        )

    try:
        grant = resolve_active_sandbox_execution_grant(
            raw,
            binding_id=spec.binding_id,
            task_id=spec.task_id,
        )
        request_mapping = binding_runtime._find_request_mapping(raw, binding_id)
        if spec.method in _BODY_METHODS and request_mapping is None:
            raise EndpointRequestMappingError(
                "sandbox request body mapping is required for this endpoint method"
            )
        request_body = (
            build_external_request_body(spec, request_mapping, body.task_input)
            if request_mapping is not None
            else None
        )
        provisioning_sha256 = sandbox_runtime._provisioning_sha256(
            spec=spec,
            request_mapping=request_mapping,
            secret_reference=secret_reference,
            content=content,
        )
        resolver = ReferenceSandboxCredentialResolver(secret_reference)
        transport = VerifiedPeerSandboxTransport()
        result = await execute_sandbox_binding(
            spec,
            task_input=body.task_input,
            request_body=request_body,
            approved_operation_classes=set(grant["approved_operation_classes"]),
            approval_reference=str(grant["grant_id"]),
            credential_resolver=resolver,
            transport=transport,
        )
        if not transport.last_verified_peer:
            raise SandboxExecutionError("sandbox_peer_address_unverified")
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

    result = {
        **result,
        "operational_proof": True,
        "peer_address_verified": True,
        "verified_peer_address": transport.last_verified_peer,
        "provisioning_sha256": provisioning_sha256,
        "content_dataset_reference": content.dataset_reference,
        "content_fixture_profile_reference": content.fixture_profile_reference,
        "customer_secret_reference_configured": True,
        "selection_authority": "admin_evaluation_grant",
        "subscription_required": False,
        "registration_required": False,
        "commercial_quota_required": False,
        "production_allowed": False,
        "runtime_connector_approved": False,
        "raw_secret_visible": False,
        "raw_payload_visible": False,
    }
    evidence = {key: value for key, value in result.items() if key != "canonical_input"}
    evidence["canonical_output_slot"] = result["output_slot"]
    items = binding_runtime._safe_evidence(raw)
    items.append(evidence)
    raw[binding_runtime.SANDBOX_EVIDENCE_STORAGE_KEY] = items[-50:]
    settings_module._save_raw(owner_id, raw)
    return result


__all__ = [
    "EvaluationBindingProvisionRequest",
    "execute_evaluation_sandbox_operational_proof",
    "provision_evaluation_binding",
]
