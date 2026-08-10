"""Canonical Maestro task input -> customer sandbox request body mapping."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from processual_api.integrations.enterprise_endpoint_bindings import (
    EnterpriseEndpointBindingSpec,
    validate_endpoint_binding,
)
from processual_api.integrations.integration_task_catalog import get_integration_task

REQUEST_MAPPING_STORAGE_KEY = "enterprise_endpoint_request_mappings_v1"
_SAFE_EXTERNAL_PATH = re.compile(r"^[A-Za-z0-9_.-]{1,240}$")


class EndpointRequestMappingError(ValueError):
    """A request-body mapping violates the canonical task contract."""


class EnterpriseEndpointRequestMappingSpec(BaseModel):
    binding_id: str = Field(min_length=1, max_length=120)
    body_mapping: dict[str, str] = Field(default_factory=dict)

    @field_validator("binding_id")
    @classmethod
    def _binding_id(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def _mapping_shape(self) -> EnterpriseEndpointRequestMappingSpec:
        if len(self.body_mapping) > 100:
            raise ValueError("request body mapping may contain at most 100 fields")
        for external_path, source in self.body_mapping.items():
            if not _SAFE_EXTERNAL_PATH.fullmatch(str(external_path).strip()):
                raise ValueError("request body field paths must use safe dotted names")
            if not str(source).startswith("$task."):
                raise ValueError(
                    "request body values must bind to canonical $task.<field> inputs"
                )
        return self


def validate_request_mapping(
    binding: EnterpriseEndpointBindingSpec,
    mapping: EnterpriseEndpointRequestMappingSpec,
) -> dict[str, Any]:
    validation = validate_endpoint_binding(binding)
    task = get_integration_task(binding.task_id)
    if mapping.binding_id != binding.binding_id:
        raise EndpointRequestMappingError("request mapping binding id mismatch")

    canonical_fields = set(task.required_input_fields) | set(task.optional_input_fields)
    used_fields = {
        str(source).removeprefix("$task.")
        for source in mapping.body_mapping.values()
    }
    unknown = used_fields - canonical_fields
    if unknown:
        raise EndpointRequestMappingError(
            "request mapping references fields outside canonical task schema: "
            + ", ".join(sorted(unknown))
        )

    if binding.method in {"POST", "PUT", "PATCH"}:
        missing = set(task.required_input_fields) - used_fields
        if missing:
            raise EndpointRequestMappingError(
                "request mapping omits required canonical task fields: "
                + ", ".join(sorted(missing))
            )
    elif mapping.body_mapping:
        raise EndpointRequestMappingError(
            "GET/DELETE endpoint bindings may not define a JSON request body mapping"
        )

    return {
        "binding_id": binding.binding_id,
        "task_id": task.task_id,
        "operation_class": task.operation_class,
        "required_scope_ids": validation["required_scope_ids"],
        "mapped_body_field_count": len(mapping.body_mapping),
        "environment": "sandbox",
        "production_allowed": False,
        "runtime_connector_approved": False,
    }


def _assign_dotted(target: dict[str, Any], path: str, value: Any) -> None:
    parts = [part for part in path.split(".") if part]
    if not parts:
        raise EndpointRequestMappingError("request body path is empty")
    current = target
    for part in parts[:-1]:
        existing = current.get(part)
        if existing is None:
            nested: dict[str, Any] = {}
            current[part] = nested
            current = nested
            continue
        if not isinstance(existing, dict):
            raise EndpointRequestMappingError(
                f"request body path collision at {part}"
            )
        current = existing
    current[parts[-1]] = value


def build_external_request_body(
    binding: EnterpriseEndpointBindingSpec,
    mapping: EnterpriseEndpointRequestMappingSpec,
    task_input: dict[str, Any],
) -> dict[str, Any] | None:
    validate_request_mapping(binding, mapping)
    if not mapping.body_mapping:
        return None

    result: dict[str, Any] = {}
    for external_path, source in mapping.body_mapping.items():
        field = str(source).removeprefix("$task.")
        if field not in task_input:
            raise EndpointRequestMappingError(
                f"missing canonical request field: {field}"
            )
        _assign_dotted(result, external_path, task_input[field])
    return result


__all__ = [
    "EndpointRequestMappingError",
    "EnterpriseEndpointRequestMappingSpec",
    "REQUEST_MAPPING_STORAGE_KEY",
    "build_external_request_body",
    "validate_request_mapping",
]
