"""Tamper-evident provenance binding for discovered Enterprise endpoints.

The discovery assessment is treated as evidence, not authority. This module
requires an assessment produced by the server-side discovery quality gate,
selects one exact operation, and binds it to a canonical fingerprint of the
Enterprise endpoint binding. A later mutation changes the fingerprint and
invalidates the qualification record.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, Field, field_validator

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SUPPORTED_FAMILIES = {
    "camara",
    "tm_forum",
    "proprietary",
    "legacy",
    "generic_enterprise",
}


class EndpointBindingProvenanceError(ValueError):
    """Discovery evidence does not match the endpoint binding exactly."""


class EndpointBindingProvenance(BaseModel):
    source_reference: str = Field(min_length=1, max_length=1000)
    source_sha256: str = Field(min_length=64, max_length=64)
    operation_id: str = Field(min_length=1, max_length=300)
    contract_family: str = Field(min_length=1, max_length=80)
    api_version: str = Field(min_length=1, max_length=120)
    method: str = Field(min_length=1, max_length=12)
    path: str = Field(min_length=1, max_length=500)
    binding_fingerprint: str = Field(min_length=64, max_length=64)
    discovery_quality_passed: bool = True
    binding_generation_ready: bool = True
    production_allowed: bool = False
    runtime_connector_approved: bool = False
    raw_secret_visible: bool = False

    @field_validator("source_sha256", "binding_fingerprint")
    @classmethod
    def _sha256(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not _SHA256.fullmatch(normalized):
            raise ValueError("provenance digests must be lowercase SHA-256 values")
        return normalized

    @field_validator("contract_family")
    @classmethod
    def _family(cls, value: str) -> str:
        normalized = value.strip().lower().replace("-", "_")
        if normalized not in _SUPPORTED_FAMILIES:
            raise ValueError("unsupported provenance contract family")
        return normalized

    @field_validator("method")
    @classmethod
    def _method(cls, value: str) -> str:
        return value.strip().upper()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")


def binding_fingerprint(spec: Any) -> str:
    """Fingerprint all secret-free fields that affect endpoint behavior."""

    payload = {
        "binding_id": str(spec.binding_id),
        "adapter_contract_id": str(spec.adapter_contract_id),
        "task_id": str(spec.task_id),
        "credential_profile_id": str(spec.credential_profile_id),
        "environment": str(spec.environment),
        "base_url": str(spec.base_url),
        "method": str(spec.method).upper(),
        "path": str(spec.path),
        "required_scope_ids": sorted(str(value) for value in spec.required_scope_ids),
        "path_parameters": dict(sorted(spec.path_parameters.items())),
        "query_parameters": dict(sorted(spec.query_parameters.items())),
        "request_headers": dict(sorted(spec.request_headers.items())),
        "response_format": str(spec.response_format),
        "response_data_path": str(spec.response_data_path),
        "field_mapping": dict(sorted(spec.field_mapping.items())),
        "success_codes": sorted(int(value) for value in spec.success_codes),
        "timeout_seconds": int(spec.timeout_seconds),
    }
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def _select_operation(
    assessment: Mapping[str, Any],
    operation_id: str,
) -> Mapping[str, Any]:
    operations = assessment.get("operations")
    if not isinstance(operations, list):
        raise EndpointBindingProvenanceError("discovery_operations_required")
    matches = [
        operation
        for operation in operations
        if isinstance(operation, Mapping)
        and str(operation.get("operation_id") or "") == operation_id
    ]
    if len(matches) != 1:
        raise EndpointBindingProvenanceError(
            "discovery_operation_must_match_exactly_once"
        )
    return matches[0]


def qualify_binding_from_discovery(
    spec: Any,
    assessment: Mapping[str, Any],
    *,
    operation_id: str,
) -> EndpointBindingProvenance:
    """Create a non-production provenance record for one exact discovered operation."""

    if assessment.get("discovery_quality_passed") is not True:
        raise EndpointBindingProvenanceError("discovery_quality_must_pass")
    if assessment.get("binding_generation_ready") is not True:
        raise EndpointBindingProvenanceError("binding_generation_must_be_ready")
    if assessment.get("production_allowed") is not False:
        raise EndpointBindingProvenanceError("discovery_must_remain_non_production")
    if assessment.get("runtime_connector_approved") is not False:
        raise EndpointBindingProvenanceError("discovery_must_not_grant_runtime_authority")

    source_reference = str(assessment.get("source_reference") or "").strip()
    source_sha256 = str(assessment.get("source_sha256") or "").strip().lower()
    family = str(assessment.get("contract_family") or "").strip().lower().replace("-", "_")
    api_version = str(assessment.get("version") or "").strip()
    if not source_reference or not _SHA256.fullmatch(source_sha256):
        raise EndpointBindingProvenanceError("immutable_discovery_source_required")
    if family not in _SUPPORTED_FAMILIES or not api_version:
        raise EndpointBindingProvenanceError("discovery_contract_identity_required")

    selected = _select_operation(assessment, operation_id)
    method = str(selected.get("method") or "").strip().upper()
    path = str(selected.get("path") or "").strip()
    if method != str(spec.method).upper():
        raise EndpointBindingProvenanceError("discovered_operation_method_mismatch")
    if path != str(spec.path):
        raise EndpointBindingProvenanceError("discovered_operation_path_mismatch")

    return EndpointBindingProvenance(
        source_reference=source_reference,
        source_sha256=source_sha256,
        operation_id=operation_id,
        contract_family=family,
        api_version=api_version,
        method=method,
        path=path,
        binding_fingerprint=binding_fingerprint(spec),
        discovery_quality_passed=True,
        binding_generation_ready=True,
        production_allowed=False,
        runtime_connector_approved=False,
        raw_secret_visible=False,
    )


def provenance_matches_binding(
    spec: Any,
    provenance: EndpointBindingProvenance | Mapping[str, Any],
) -> bool:
    """Return False when any behavior-affecting binding field has drifted."""

    record = (
        provenance
        if isinstance(provenance, EndpointBindingProvenance)
        else EndpointBindingProvenance(**dict(provenance))
    )
    return (
        record.method == str(spec.method).upper()
        and record.path == str(spec.path)
        and record.binding_fingerprint == binding_fingerprint(spec)
        and record.discovery_quality_passed is True
        and record.binding_generation_ready is True
        and record.production_allowed is False
        and record.runtime_connector_approved is False
    )


__all__ = [
    "EndpointBindingProvenance",
    "EndpointBindingProvenanceError",
    "binding_fingerprint",
    "provenance_matches_binding",
    "qualify_binding_from_discovery",
]
