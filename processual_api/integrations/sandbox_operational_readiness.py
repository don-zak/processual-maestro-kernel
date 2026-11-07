"""Operational provisioning and readiness contracts for customer and project sandboxes."""

from __future__ import annotations

from enum import StrEnum
from hashlib import sha256
from json import dumps
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SANDBOX_CONTENT_STORAGE_KEY = "enterprise_sandbox_content_contracts_v1"
SANDBOX_SECRET_REFERENCE_STORAGE_KEY = "enterprise_sandbox_secret_references_v1"
_PROHIBITED_MARKERS = (
    "http://",
    "https://",
    "bearer ",
    "password=",
    "token=",
    "secret=",
    "api_key=",
    "client_secret=",
    "private_key=",
    "authorization:",
    "raw_payload=",
)


def _validate_reference(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("sandbox provisioning references must not be empty")
    lowered = normalized.casefold()
    if any(marker in lowered for marker in _PROHIBITED_MARKERS):
        raise ValueError("sandbox provisioning fields accept references only")
    return normalized


class SandboxOperationalStatus(StrEnum):
    NOT_CONFIGURED = "not_configured"
    BOUND = "bound"
    CREDENTIAL_READY = "credential_ready"
    CONTENT_READY = "content_ready"
    LIVE_PROOF_PASSED = "live_proof_passed"
    SANDBOX_READY = "sandbox_ready"


class SandboxSecretReference(BaseModel):
    """Owned sandbox credential reference. Secret values are prohibited."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    binding_id: str = Field(min_length=1, max_length=160)
    provider_id: str = Field(min_length=1, max_length=160)
    secret_reference: str = Field(min_length=1, max_length=320)
    customer_scoped: bool = True
    project_scoped: bool = False
    value_included: bool = False

    @field_validator("binding_id", "provider_id", "secret_reference")
    @classmethod
    def _reference_only(cls, value: str) -> str:
        return _validate_reference(value)

    @field_validator("value_included")
    @classmethod
    def _no_value(cls, value: bool) -> bool:
        if value is not False:
            raise ValueError("sandbox secret references cannot include secret values")
        return value

    @model_validator(mode="after")
    def _exactly_one_reference_scope(self) -> SandboxSecretReference:
        if self.customer_scoped == self.project_scoped:
            raise ValueError(
                "sandbox reference must be scoped to exactly one of customer or project"
            )
        return self


class SandboxContentContract(BaseModel):
    """References describing owned sandbox test content, never raw data."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    binding_id: str = Field(min_length=1, max_length=160)
    dataset_reference: str = Field(min_length=1, max_length=256)
    fixture_profile_reference: str = Field(min_length=1, max_length=256)
    required_record_types: tuple[str, ...] = Field(min_length=1, max_length=32)
    acceptance_criteria_references: tuple[str, ...] = Field(min_length=1, max_length=32)
    customer_owned: bool = True
    project_owned: bool = False
    synthetic_or_nonproduction: bool = True
    secrets_included: bool = False
    raw_payloads_included: bool = False

    @field_validator(
        "binding_id",
        "dataset_reference",
        "fixture_profile_reference",
    )
    @classmethod
    def _safe_reference(cls, value: str) -> str:
        return _validate_reference(value)

    @field_validator("required_record_types", "acceptance_criteria_references")
    @classmethod
    def _safe_reference_tuple(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(values)) != len(values):
            raise ValueError("sandbox content references must be unique")
        return tuple(_validate_reference(value) for value in values)

    @field_validator("synthetic_or_nonproduction")
    @classmethod
    def _nonproduction_required(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("sandbox content must remain synthetic or non-production")
        return value

    @field_validator("secrets_included", "raw_payloads_included")
    @classmethod
    def _required_false(cls, value: bool) -> bool:
        if value is not False:
            raise ValueError("sandbox content contract cannot contain secrets or raw payloads")
        return value

    @model_validator(mode="after")
    def _exactly_one_owned_source(self) -> SandboxContentContract:
        if self.customer_owned == self.project_owned:
            raise ValueError(
                "sandbox content must be owned by exactly one of customer or project"
            )
        return self


def safe_content_projection(contract: SandboxContentContract) -> dict[str, Any]:
    return {
        **contract.model_dump(),
        "content_owner": "customer" if contract.customer_owned else "project",
        "configured": True,
        "production_allowed": False,
        "runtime_connector_approved": False,
    }


def safe_secret_reference_projection(reference: SandboxSecretReference) -> dict[str, Any]:
    return {
        "binding_id": reference.binding_id,
        "provider_id": reference.provider_id,
        "secret_reference": reference.secret_reference,
        "customer_scoped": reference.customer_scoped,
        "project_scoped": reference.project_scoped,
        "reference_scope": "customer" if reference.customer_scoped else "project",
        "value_included": False,
        "configured": True,
        "production_allowed": False,
        "runtime_connector_approved": False,
    }


def _content_fingerprint_payload(contract: SandboxContentContract) -> dict[str, Any]:
    payload = contract.model_dump(mode="json")
    # Preserve hashes generated before project-owned Evaluation sandboxes were
    # introduced. The default False field is metadata-only for legacy customer
    # contracts and must not invalidate their already-qualified live proof.
    if payload.get("project_owned") is False:
        payload.pop("project_owned", None)
    return payload


def sandbox_provisioning_fingerprint(
    *,
    binding: dict[str, Any],
    request_mapping: dict[str, Any] | None,
    secret_reference: SandboxSecretReference,
    content_contract: SandboxContentContract,
) -> str:
    """Bind proof evidence to the exact non-secret sandbox provisioning state."""

    payload = {
        "binding": binding,
        "request_mapping": request_mapping,
        "secret_reference": {
            "binding_id": secret_reference.binding_id,
            "provider_id": secret_reference.provider_id,
            "secret_reference": secret_reference.secret_reference,
        },
        "content_contract": _content_fingerprint_payload(content_contract),
    }
    encoded = dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def evaluate_sandbox_operational_readiness(
    *,
    binding_configured: bool,
    mapping_configured: bool,
    secret_reference: SandboxSecretReference | None,
    content_contract: SandboxContentContract | None,
    live_proof_evidence: dict[str, Any] | None,
    expected_provisioning_sha256: str | None = None,
) -> dict[str, Any]:
    """Derive one monotonic, fail-closed sandbox readiness status."""

    blockers: list[str] = []
    status = SandboxOperationalStatus.NOT_CONFIGURED

    if not binding_configured:
        blockers.append("endpoint_binding_required")
    else:
        status = SandboxOperationalStatus.BOUND

    if binding_configured and not mapping_configured:
        blockers.append("request_or_response_mapping_required")

    if secret_reference is None:
        blockers.append("customer_secret_reference_required")
    elif binding_configured and mapping_configured:
        status = SandboxOperationalStatus.CREDENTIAL_READY

    if content_contract is None:
        blockers.append("sandbox_content_contract_required")
    elif status is SandboxOperationalStatus.CREDENTIAL_READY:
        status = SandboxOperationalStatus.CONTENT_READY

    proof_ok = bool(
        live_proof_evidence
        and live_proof_evidence.get("operational_proof") is True
        and live_proof_evidence.get("peer_address_verified") is True
        and live_proof_evidence.get("customer_secret_reference_configured") is True
        and live_proof_evidence.get("network_request_executed") is True
        and live_proof_evidence.get("mapping_valid") is True
        and live_proof_evidence.get("ready_for_task_consumption") is True
        and live_proof_evidence.get("production_allowed") is False
        and live_proof_evidence.get("runtime_connector_approved") is False
        and (
            expected_provisioning_sha256 is None
            or live_proof_evidence.get("provisioning_sha256")
            == expected_provisioning_sha256
        )
    )
    if not proof_ok:
        blockers.append("hardened_live_sandbox_proof_required")
    elif status is SandboxOperationalStatus.CONTENT_READY:
        status = SandboxOperationalStatus.LIVE_PROOF_PASSED
        status = SandboxOperationalStatus.SANDBOX_READY

    return {
        "status": status.value,
        "sandbox_ready": status is SandboxOperationalStatus.SANDBOX_READY,
        "blocker_codes": blockers,
        "secret_reference_configured": secret_reference is not None,
        "content_contract_configured": content_contract is not None,
        "live_proof_passed": proof_ok,
        "provisioning_sha256": expected_provisioning_sha256,
        "production_allowed": False,
        "runtime_connector_approved": False,
    }


__all__ = [
    "SANDBOX_CONTENT_STORAGE_KEY",
    "SANDBOX_SECRET_REFERENCE_STORAGE_KEY",
    "SandboxContentContract",
    "SandboxOperationalStatus",
    "SandboxSecretReference",
    "evaluate_sandbox_operational_readiness",
    "safe_content_projection",
    "safe_secret_reference_projection",
    "sandbox_provisioning_fingerprint",
]
