"""Settings routes for customer sandbox operational provisioning and readiness."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, status

from processual_api.auth.security import get_current_user
from processual_api.integrations.enterprise_endpoint_bindings import EndpointBindingError
from processual_api.integrations.enterprise_endpoint_request_mapping import (
    EndpointRequestMappingError,
    build_external_request_body,
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
    evaluate_sandbox_operational_readiness,
    safe_content_projection,
    safe_secret_reference_projection,
    sandbox_provisioning_fingerprint,
)
from processual_api.integrations.sandbox_secret_resolution import (
    ReferenceSandboxCredentialResolver,
)
from processual_api.integrations.sandbox_verified_transport import VerifiedPeerSandboxTransport
from processual_api.services.enterprise_endpoint_sandbox_grants import (
    SandboxGrantError,
    resolve_active_sandbox_execution_grant,
)

from . import settings as settings_module
from . import settings_enterprise_endpoint_bindings_runtime as binding_runtime

_BODY_METHODS = frozenset({"POST", "PUT", "PATCH"})


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


def _content_contract(raw: dict[str, Any], binding_id: str) -> SandboxContentContract | None:
    for item in _stored_items(raw, SANDBOX_CONTENT_STORAGE_KEY):
        if str(item.get("binding_id") or "") != binding_id:
            continue
        try:
            return SandboxContentContract(**item)
        except ValueError:
            return None
    return None


def _secret_reference(raw: dict[str, Any], binding_id: str) -> SandboxSecretReference | None:
    for item in _stored_items(raw, SANDBOX_SECRET_REFERENCE_STORAGE_KEY):
        if str(item.get("binding_id") or "") != binding_id:
            continue
        try:
            return SandboxSecretReference(**item)
        except ValueError:
            return None
    return None


def _latest_binding_evidence(
    raw: dict[str, Any],
    binding_id: str,
    task_id: str,
) -> dict[str, Any] | None:
    for item in reversed(binding_runtime._safe_evidence(raw)):
        if (
            str(item.get("binding_id") or "") == binding_id
            and str(item.get("task_id") or "") == task_id
        ):
            return item
    return None


def _provisioning_sha256(
    *,
    spec: Any,
    request_mapping: Any,
    secret_reference: SandboxSecretReference,
    content: SandboxContentContract,
) -> str:
    return sandbox_provisioning_fingerprint(
        binding=spec.model_dump(mode="json"),
        request_mapping=(
            request_mapping.model_dump(mode="json")
            if request_mapping is not None
            else None
        ),
        secret_reference=secret_reference,
        content_contract=content,
    )


@settings_module.router.put(
    "/enterprise-integration/endpoint-bindings/{binding_id}/sandbox-secret-reference",
    response_model=dict,
)
async def save_enterprise_sandbox_secret_reference(
    binding_id: str,
    body: SandboxSecretReference,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    user_id, raw = binding_runtime._require_enterprise(current_user)
    binding_runtime._find_binding(raw, binding_id)
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
    settings_module._save_raw(user_id, raw)
    return {
        "status": "saved",
        "persisted": True,
        "secret_reference": safe_secret_reference_projection(body),
        "raw_secret_visible": False,
        "production_allowed": False,
        "runtime_connector_approved": False,
    }


@settings_module.router.put(
    "/enterprise-integration/endpoint-bindings/{binding_id}/sandbox-content-contract",
    response_model=dict,
)
async def save_enterprise_sandbox_content_contract(
    binding_id: str,
    body: SandboxContentContract,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    user_id, raw = binding_runtime._require_enterprise(current_user)
    binding_runtime._find_binding(raw, binding_id)
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
    settings_module._save_raw(user_id, raw)
    return {
        "status": "saved",
        "persisted": True,
        "content_contract": safe_content_projection(body),
        "raw_payload_visible": False,
        "production_allowed": False,
        "runtime_connector_approved": False,
    }


@settings_module.router.get(
    "/enterprise-integration/endpoint-bindings/{binding_id}/sandbox-readiness",
    response_model=dict,
)
async def get_enterprise_sandbox_operational_readiness(
    binding_id: str,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    _, raw = binding_runtime._require_enterprise(current_user)
    spec = binding_runtime._find_binding(raw, binding_id)
    request_mapping = binding_runtime._find_request_mapping(raw, binding_id)
    response_mapping_ready = bool(spec.field_mapping)
    request_mapping_ready = spec.method not in _BODY_METHODS or request_mapping is not None
    content = _content_contract(raw, binding_id)
    secret_reference = _secret_reference(raw, binding_id)
    evidence = _latest_binding_evidence(raw, binding_id, spec.task_id)
    expected_provisioning_sha256 = (
        _provisioning_sha256(
            spec=spec,
            request_mapping=request_mapping,
            secret_reference=secret_reference,
            content=content,
        )
        if content is not None and secret_reference is not None
        else None
    )
    readiness = evaluate_sandbox_operational_readiness(
        binding_configured=True,
        mapping_configured=response_mapping_ready and request_mapping_ready,
        secret_reference=secret_reference,
        content_contract=content,
        live_proof_evidence=evidence,
        expected_provisioning_sha256=expected_provisioning_sha256,
    )
    return {
        "binding_id": binding_id,
        "environment": "sandbox",
        **readiness,
        "content_contract": safe_content_projection(content) if content else None,
        "secret_reference": (
            safe_secret_reference_projection(secret_reference)
            if secret_reference
            else None
        ),
        "latest_evidence_sha256": str((evidence or {}).get("evidence_sha256") or "") or None,
        "raw_secret_visible": False,
        "raw_payload_visible": False,
    }


@settings_module.router.post(
    "/enterprise-integration/endpoint-bindings/{binding_id}/sandbox-operational-execute",
    response_model=dict,
)
async def execute_enterprise_sandbox_operational_proof(
    binding_id: str,
    body: binding_runtime.EndpointSandboxExecuteRequest,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Execute the hardened sandbox path after explicit provisioning is complete."""

    user_id, raw = binding_runtime._require_enterprise(current_user)
    spec = binding_runtime._find_binding(raw, binding_id)
    content = _content_contract(raw, binding_id)
    secret_reference = _secret_reference(raw, binding_id)
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
        provisioning_sha256 = _provisioning_sha256(
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
    }
    evidence = {
        key: value
        for key, value in result.items()
        if key != "canonical_input"
    }
    evidence["canonical_output_slot"] = result["output_slot"]
    items = binding_runtime._safe_evidence(raw)
    items.append(evidence)
    raw[binding_runtime.SANDBOX_EVIDENCE_STORAGE_KEY] = items[-50:]
    settings_module._save_raw(user_id, raw)
    return result


__all__ = [
    "execute_enterprise_sandbox_operational_proof",
    "get_enterprise_sandbox_operational_readiness",
    "save_enterprise_sandbox_content_contract",
    "save_enterprise_sandbox_secret_reference",
]
