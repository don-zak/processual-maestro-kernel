"""Governed endpoint bindings for Enterprise Integration.

Bindings describe how a customer API response maps into a canonical Maestro
integration task. They deliberately store credential references instead of
secret material and keep production/runtime approval false.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator, model_validator

from processual_api.integrations.adapter_contracts import get_adapter_contract
from processual_api.integrations.credential_profiles import get_credential_profile
from processual_api.integrations.integration_task_catalog import get_integration_task
from processual_api.integrations.scope_catalog import get_integration_scope

BINDING_STORAGE_KEY = "enterprise_endpoint_bindings_v1"
ALLOWED_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}
FORBIDDEN_HEADER_NAMES = {
    "authorization",
    "cookie",
    "proxy-authorization",
    "x-api-key",
    "api-key",
}
_SECRET_MARKERS = (
    "bearer ",
    "basic ",
    "token",
    "secret",
    "password",
    "private_key",
)
_SAFE_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,120}$")
_SAFE_PARAMETER = re.compile(r"^[A-Za-z0-9_.:-]{1,120}$")


class EndpointBindingError(ValueError):
    """An endpoint binding violates a declared Maestro integration contract."""


class EnterpriseEndpointBindingSpec(BaseModel):
    binding_id: str = Field(min_length=1, max_length=120)
    display_name: str = Field(min_length=1, max_length=160)
    adapter_contract_id: str = Field(min_length=1, max_length=120)
    task_id: str = Field(min_length=1, max_length=160)
    credential_profile_id: str = Field(min_length=1, max_length=160)
    environment: str = "sandbox"
    base_url: str = Field(min_length=1, max_length=500)
    method: str = "GET"
    path: str = Field(min_length=1, max_length=500)
    required_scope_ids: list[str] = Field(default_factory=list)
    path_parameters: dict[str, str] = Field(default_factory=dict)
    query_parameters: dict[str, str] = Field(default_factory=dict)
    request_headers: dict[str, str] = Field(default_factory=dict)
    response_format: str = "json"
    response_data_path: str = "$"
    field_mapping: dict[str, str] = Field(default_factory=dict)
    success_codes: list[int] = Field(default_factory=lambda: [200])
    timeout_seconds: int = Field(default=15, ge=1, le=60)

    @field_validator("binding_id")
    @classmethod
    def _safe_binding_id(cls, value: str) -> str:
        value = value.strip()
        if not _SAFE_ID.fullmatch(value):
            raise ValueError("binding_id must use safe identifier characters")
        return value

    @field_validator("adapter_contract_id", "task_id", "credential_profile_id")
    @classmethod
    def _normalize_identifier(cls, value: str) -> str:
        return value.strip().lower().replace("-", "_")

    @field_validator("environment")
    @classmethod
    def _sandbox_only(cls, value: str) -> str:
        if value.strip().lower() != "sandbox":
            raise ValueError("endpoint bindings are sandbox-only until qualification")
        return "sandbox"

    @field_validator("base_url")
    @classmethod
    def _safe_base_url(cls, value: str) -> str:
        candidate = value.strip()
        parsed = urlparse(candidate)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("base_url must be an absolute HTTPS URL")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("base_url may not contain credentials, query, or fragment")
        hostname = parsed.hostname.lower().rstrip(".")
        if hostname in {"localhost", "localhost.localdomain"}:
            raise ValueError("localhost endpoints are not allowed")
        if hostname.endswith((".localhost", ".local", ".internal")):
            raise ValueError("private/local endpoint hostnames are not allowed")
        if hostname in {"169.254.169.254", "metadata.google.internal"}:
            raise ValueError("cloud metadata endpoints are not allowed")
        return candidate.rstrip("/")

    @field_validator("method")
    @classmethod
    def _method(cls, value: str) -> str:
        method = value.strip().upper()
        if method not in ALLOWED_METHODS:
            raise ValueError("unsupported HTTP method")
        return method

    @field_validator("path")
    @classmethod
    def _path(cls, value: str) -> str:
        path = value.strip()
        if not path.startswith("/") or path.startswith("//"):
            raise ValueError("path must be an absolute API path")
        if "://" in path:
            raise ValueError("path may not override the configured base URL")
        return path

    @field_validator("response_format")
    @classmethod
    def _json_only(cls, value: str) -> str:
        if value.strip().lower() != "json":
            raise ValueError("only JSON response mapping is currently supported")
        return "json"

    @field_validator("success_codes")
    @classmethod
    def _success_codes(cls, values: list[int]) -> list[int]:
        unique = sorted(set(values))
        if not unique or any(code < 200 or code >= 400 for code in unique):
            raise ValueError("success_codes must contain only 2xx/3xx status codes")
        return unique

    @model_validator(mode="after")
    def _no_secret_material(self) -> EnterpriseEndpointBindingSpec:
        for key, value in self.request_headers.items():
            normalized_key = key.strip().lower()
            normalized_value = str(value).strip().lower()
            if normalized_key in FORBIDDEN_HEADER_NAMES:
                raise ValueError(
                    "authentication headers must come from credential bindings, not endpoint settings"
                )
            if any(marker in normalized_value for marker in _SECRET_MARKERS):
                raise ValueError("request headers may not contain secret material")
        for mapping in (self.path_parameters, self.query_parameters):
            for name, source in mapping.items():
                if not _SAFE_PARAMETER.fullmatch(str(name).strip()):
                    raise ValueError("endpoint parameter names must be safe identifiers")
                if not str(source).startswith("$task."):
                    raise ValueError(
                        "endpoint parameters must bind to canonical $task.<field> inputs"
                    )
        return self


def validate_endpoint_binding(
    spec: EnterpriseEndpointBindingSpec,
) -> dict[str, Any]:
    contract = get_adapter_contract(spec.adapter_contract_id)
    task = get_integration_task(spec.task_id)
    profile = get_credential_profile(spec.credential_profile_id)

    if task.adapter_contract_id != contract.contract_id:
        raise EndpointBindingError(
            "task is not declared for the selected adapter contract"
        )
    if contract.contract_id not in profile.adapter_contract_ids:
        raise EndpointBindingError(
            "credential profile does not support the selected adapter contract"
        )

    requested_scopes = tuple(
        sorted({str(scope).strip().lower() for scope in spec.required_scope_ids})
    )
    if not requested_scopes:
        requested_scopes = task.required_scope_ids

    contract_scopes = set(contract.all_scopes)
    unknown = set(requested_scopes) - contract_scopes
    if unknown:
        raise EndpointBindingError(
            "binding requests scopes outside adapter contract: "
            + ", ".join(sorted(unknown))
        )
    missing_task_scopes = set(task.required_scope_ids) - set(requested_scopes)
    if missing_task_scopes:
        raise EndpointBindingError(
            "binding omits task-required scopes: "
            + ", ".join(sorted(missing_task_scopes))
        )
    for scope_id in requested_scopes:
        get_integration_scope(scope_id)

    missing_fields = set(task.required_input_fields) - set(spec.field_mapping)
    if missing_fields:
        raise EndpointBindingError(
            "binding omits canonical task fields: "
            + ", ".join(sorted(missing_fields))
        )
    allowed_fields = set(task.required_input_fields) | set(task.optional_input_fields)
    unsupported_fields = set(spec.field_mapping) - allowed_fields
    if unsupported_fields:
        raise EndpointBindingError(
            "binding maps fields outside canonical task schema: "
            + ", ".join(sorted(unsupported_fields))
        )

    if task.operation_class == "read" and spec.method != "GET":
        raise EndpointBindingError("read tasks must use GET endpoint bindings")
    if task.operation_class == "draft" and spec.method not in {"GET", "POST"}:
        raise EndpointBindingError("draft tasks may use only GET or POST in sandbox")
    if task.operation_class == "approval_gated_write":
        risky = [
            scope_id
            for scope_id in requested_scopes
            if not get_integration_scope(scope_id).requires_supervisor_approval
        ]
        if risky:
            raise EndpointBindingError(
                "approval-gated task contains scopes without supervisor approval posture"
            )

    return {
        "binding_id": spec.binding_id,
        "adapter_contract_id": contract.contract_id,
        "task_id": task.task_id,
        "safe_operation": task.safe_operation,
        "operation_class": task.operation_class,
        "required_scope_ids": list(requested_scopes),
        "canonical_required_fields": list(task.required_input_fields),
        "canonical_optional_fields": list(task.optional_input_fields),
        "output_slot": task.output_slot,
        "lifecycle_state": "schema_validated",
        "environment": "sandbox",
        "sandbox_allowed": task.sandbox_allowed,
        "production_allowed": False,
        "runtime_connector_approved": False,
        "raw_secret_visible": False,
    }


def safe_binding_payload(
    spec: EnterpriseEndpointBindingSpec,
) -> dict[str, Any]:
    validation = validate_endpoint_binding(spec)
    return {
        **spec.model_dump(),
        "required_scope_ids": validation["required_scope_ids"],
        "validation": validation,
        "production_allowed": False,
        "runtime_connector_approved": False,
        "raw_secret_visible": False,
    }


def _extract_path(value: Any, path: str) -> Any:
    normalized = str(path or "$").strip()
    if normalized in {"", "$"}:
        return value
    if normalized.startswith("$."):
        normalized = normalized[2:]
    elif normalized.startswith("."):
        normalized = normalized[1:]

    current = value
    for part in normalized.split("."):
        if not part:
            continue
        if isinstance(current, dict):
            if part not in current:
                raise EndpointBindingError(f"response path not found: {path}")
            current = current[part]
            continue
        if isinstance(current, list) and part.isdigit():
            index = int(part)
            if index >= len(current):
                raise EndpointBindingError(f"response index out of range: {path}")
            current = current[index]
            continue
        raise EndpointBindingError(f"response path not found: {path}")
    return current


def map_response_to_task_input(
    spec: EnterpriseEndpointBindingSpec,
    response_payload: Any,
) -> dict[str, Any]:
    validation = validate_endpoint_binding(spec)
    root = _extract_path(response_payload, spec.response_data_path)
    mapped = {
        canonical_field: _extract_path(root, source_path)
        for canonical_field, source_path in spec.field_mapping.items()
    }
    missing = [
        field
        for field in validation["canonical_required_fields"]
        if field not in mapped or mapped[field] is None
    ]
    if missing:
        raise EndpointBindingError(
            "mapped response is missing required canonical fields: "
            + ", ".join(sorted(missing))
        )
    return {
        "task_id": spec.task_id,
        "adapter_contract_id": spec.adapter_contract_id,
        "output_slot": validation["output_slot"],
        "canonical_input": mapped,
        "mapping_valid": True,
        "production_allowed": False,
        "runtime_connector_approved": False,
    }


def build_request_preview(
    spec: EnterpriseEndpointBindingSpec,
    task_input: dict[str, Any],
) -> dict[str, Any]:
    validate_endpoint_binding(spec)
    path = spec.path
    query: dict[str, Any] = {}

    def resolve(source: str) -> Any:
        field = source.removeprefix("$task.")
        if field not in task_input:
            raise EndpointBindingError(f"missing task parameter: {field}")
        return task_input[field]

    for name, source in spec.path_parameters.items():
        token = "{" + name + "}"
        if token not in path:
            raise EndpointBindingError(
                f"path parameter {name!r} is not present in endpoint path"
            )
        path = path.replace(token, str(resolve(source)))
    for name, source in spec.query_parameters.items():
        query[name] = resolve(source)

    return {
        "binding_id": spec.binding_id,
        "method": spec.method,
        "url": spec.base_url + path,
        "query": query,
        "headers": dict(spec.request_headers),
        "credential_profile_id": spec.credential_profile_id,
        "credential_material_included": False,
        "timeout_seconds": spec.timeout_seconds,
        "environment": "sandbox",
        "network_request_executed": False,
        "production_allowed": False,
    }


__all__ = [
    "BINDING_STORAGE_KEY",
    "EndpointBindingError",
    "EnterpriseEndpointBindingSpec",
    "build_request_preview",
    "map_response_to_task_input",
    "safe_binding_payload",
    "validate_endpoint_binding",
]
