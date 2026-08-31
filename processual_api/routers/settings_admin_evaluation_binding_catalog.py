"""Read-only prepared binding catalog for External Evaluation administration."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, Request

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
    validate_request_mapping,
)
from processual_api.integrations.sandbox_operational_readiness import (
    SANDBOX_CONTENT_STORAGE_KEY,
    SANDBOX_SECRET_REFERENCE_STORAGE_KEY,
    SandboxContentContract,
    SandboxSecretReference,
    evaluate_sandbox_operational_readiness,
    sandbox_provisioning_fingerprint,
)
from processual_api.services.enterprise_endpoint_sandbox_grants import (
    SandboxGrantError,
    resolve_active_sandbox_execution_grant,
)

from . import settings as settings_module
from .settings_enterprise_endpoint_bindings_runtime import SANDBOX_EVIDENCE_STORAGE_KEY

_BODY_METHODS = frozenset({"POST", "PUT", "PATCH"})


def _owner_user_id(current_user: dict[str, Any]) -> str:
    return str(current_user.get("sub") or current_user.get("user_id") or "default")


def _stored_items(raw: dict[str, Any], key: str) -> list[dict[str, Any]]:
    values = raw.get(key, [])
    if not isinstance(values, list):
        return []
    return [dict(value) for value in values if isinstance(value, dict)]


def _matching_item(raw: dict[str, Any], key: str, binding_id: str) -> dict[str, Any] | None:
    for item in _stored_items(raw, key):
        if str(item.get("binding_id") or "") == binding_id:
            return item
    return None


def _request_mapping(
    raw: dict[str, Any],
    spec: EnterpriseEndpointBindingSpec,
) -> EnterpriseEndpointRequestMappingSpec | None:
    item = _matching_item(raw, REQUEST_MAPPING_STORAGE_KEY, spec.binding_id)
    if item is None:
        return None
    mapping = EnterpriseEndpointRequestMappingSpec(**item)
    validate_request_mapping(spec, mapping)
    return mapping


def _content_contract(raw: dict[str, Any], binding_id: str) -> SandboxContentContract | None:
    item = _matching_item(raw, SANDBOX_CONTENT_STORAGE_KEY, binding_id)
    return SandboxContentContract(**item) if item is not None else None


def _secret_reference(raw: dict[str, Any], binding_id: str) -> SandboxSecretReference | None:
    item = _matching_item(raw, SANDBOX_SECRET_REFERENCE_STORAGE_KEY, binding_id)
    return SandboxSecretReference(**item) if item is not None else None


def _latest_evidence(raw: dict[str, Any], spec: EnterpriseEndpointBindingSpec) -> dict[str, Any] | None:
    for item in reversed(_stored_items(raw, SANDBOX_EVIDENCE_STORAGE_KEY)):
        if (
            str(item.get("binding_id") or "") == spec.binding_id
            and str(item.get("task_id") or "") == spec.task_id
        ):
            return item
    return None


def _binding_catalog_item(raw: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    binding_id = str(item.get("binding_id") or "").strip()
    try:
        spec = EnterpriseEndpointBindingSpec(**item)
        validate_endpoint_binding(spec)
        binding = safe_binding_payload(spec)
        request_mapping = _request_mapping(raw, spec)
        response_mapping_ready = bool(spec.field_mapping)
        request_mapping_ready = spec.method not in _BODY_METHODS or request_mapping is not None
        mapping_ready = response_mapping_ready and request_mapping_ready
        content = _content_contract(raw, spec.binding_id)
        secret_reference = _secret_reference(raw, spec.binding_id)
        evidence = _latest_evidence(raw, spec)
        provisioning_sha256 = (
            sandbox_provisioning_fingerprint(
                binding=spec.model_dump(mode="json"),
                request_mapping=(
                    request_mapping.model_dump(mode="json")
                    if request_mapping is not None
                    else None
                ),
                secret_reference=secret_reference,
                content_contract=content,
            )
            if content is not None and secret_reference is not None
            else None
        )
        readiness = evaluate_sandbox_operational_readiness(
            binding_configured=True,
            mapping_configured=mapping_ready,
            secret_reference=secret_reference,
            content_contract=content,
            live_proof_evidence=evidence,
            expected_provisioning_sha256=provisioning_sha256,
        )
        try:
            active_grant = resolve_active_sandbox_execution_grant(
                raw,
                binding_id=spec.binding_id,
                task_id=spec.task_id,
            )
        except SandboxGrantError:
            active_grant = None
        selectable = bool(readiness["sandbox_ready"] and active_grant is not None)
        return {
            "binding_id": spec.binding_id,
            "task_id": spec.task_id,
            "display_name": spec.display_name,
            "binding": binding,
            "binding_valid": True,
            "mapping_ready": mapping_ready,
            "content_contract_ready": content is not None,
            "secret_reference_ready": secret_reference is not None,
            "sandbox_readiness": readiness,
            "active_sandbox_grant": active_grant,
            "selectable": selectable,
            "production_allowed": False,
            "raw_secret_visible": False,
            "raw_payload_visible": False,
        }
    except (
        ValueError,
        KeyError,
        EndpointBindingError,
        EndpointRequestMappingError,
    ):
        return {
            "binding_id": binding_id,
            "task_id": str(item.get("task_id") or ""),
            "display_name": str(item.get("display_name") or binding_id),
            "binding": None,
            "binding_valid": False,
            "mapping_ready": False,
            "content_contract_ready": False,
            "secret_reference_ready": False,
            "sandbox_readiness": {
                "status": "not_configured",
                "sandbox_ready": False,
                "blocker_codes": ["invalid_endpoint_binding"],
                "production_allowed": False,
                "runtime_connector_approved": False,
            },
            "active_sandbox_grant": None,
            "selectable": False,
            "production_allowed": False,
            "raw_secret_visible": False,
            "raw_payload_visible": False,
        }


@settings_module.router.get(
    "/admin/evaluation-grants/binding-catalog",
    response_model=dict,
)
async def evaluation_binding_catalog(
    request: Request,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    await require_active_platform_admin(current_user, request)
    raw = settings_module._load_raw(_owner_user_id(current_user))
    bindings = [
        _binding_catalog_item(raw, item)
        for item in _stored_items(raw, BINDING_STORAGE_KEY)
    ]
    return {
        "status": "ready",
        "binding_count": len(bindings),
        "bindings": bindings,
        "selection_authority": "admin_evaluation_grant",
        "subscription_required": False,
        "registration_required": False,
        "commercial_quota_required": False,
        "production_allowed": False,
        "raw_secret_visible": False,
        "raw_payload_visible": False,
    }


__all__ = ["evaluation_binding_catalog"]
