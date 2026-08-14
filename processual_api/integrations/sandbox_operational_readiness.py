"""Operational content and readiness contracts for governed customer sandboxes."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


SANDBOX_CONTENT_STORAGE_KEY = "enterprise_sandbox_content_contracts_v1"
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


class SandboxOperationalStatus(StrEnum):
    NOT_CONFIGURED = "not_configured"
    INTAKE_COMPLETE = "intake_complete"
    BOUND = "bound"
    CREDENTIAL_READY = "credential_ready"
    CONTENT_READY = "content_ready"
    LIVE_PROOF_PASSED = "live_proof_passed"
    SANDBOX_READY = "sandbox_ready"


class SandboxContentContract(BaseModel):
    """References describing customer-owned sandbox test content, never raw data."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    binding_id: str = Field(min_length=1, max_length=160)
    dataset_reference: str = Field(min_length=1, max_length=256)
    fixture_profile_reference: str = Field(min_length=1, max_length=256)
    required_record_types: tuple[str, ...] = Field(min_length=1, max_length=32)
    acceptance_criteria_references: tuple[str, ...] = Field(min_length=1, max_length=32)
    customer_owned: bool = True
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
        lowered = value.casefold()
        if any(marker in lowered for marker in _PROHIBITED_MARKERS):
            raise ValueError("sandbox content fields accept references only")
        return value

    @field_validator("required_record_types", "acceptance_criteria_references")
    @classmethod
    def _safe_reference_tuple(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(values)) != len(values):
            raise ValueError("sandbox content references must be unique")
        for value in values:
            normalized = value.strip()
            if not normalized or any(marker in normalized.casefold() for marker in _PROHIBITED_MARKERS):
                raise ValueError("sandbox content fields accept references only")
        return values

    @field_validator("customer_owned", "synthetic_or_nonproduction")
    @classmethod
    def _required_true(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("sandbox content must remain customer-owned non-production content")
        return value

    @field_validator("secrets_included", "raw_payloads_included")
    @classmethod
    def _required_false(cls, value: bool) -> bool:
        if value is not False:
            raise ValueError("sandbox content contract cannot contain secrets or raw payloads")
        return value


def safe_content_projection(contract: SandboxContentContract) -> dict[str, Any]:
    return {
        **contract.model_dump(),
        "configured": True,
        "production_allowed": False,
        "runtime_connector_approved": False,
    }


def evaluate_sandbox_operational_readiness(
    *,
    binding_configured: bool,
    mapping_configured: bool,
    credential_reference_configured: bool,
    content_contract: SandboxContentContract | None,
    live_proof_evidence: dict[str, Any] | None,
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

    if binding_configured and mapping_configured and not credential_reference_configured:
        blockers.append("credential_reference_required")
    elif binding_configured and mapping_configured and credential_reference_configured:
        status = SandboxOperationalStatus.CREDENTIAL_READY

    if content_contract is None:
        blockers.append("sandbox_content_contract_required")
    elif status is SandboxOperationalStatus.CREDENTIAL_READY:
        status = SandboxOperationalStatus.CONTENT_READY

    proof_ok = bool(
        live_proof_evidence
        and live_proof_evidence.get("network_request_executed") is True
        and live_proof_evidence.get("mapping_valid") is True
        and live_proof_evidence.get("ready_for_task_consumption") is True
        and live_proof_evidence.get("production_allowed") is False
        and live_proof_evidence.get("runtime_connector_approved") is False
    )
    if not proof_ok:
        blockers.append("live_sandbox_proof_required")
    elif status is SandboxOperationalStatus.CONTENT_READY:
        status = SandboxOperationalStatus.LIVE_PROOF_PASSED
        status = SandboxOperationalStatus.SANDBOX_READY

    return {
        "status": status.value,
        "sandbox_ready": status is SandboxOperationalStatus.SANDBOX_READY,
        "blocker_codes": blockers,
        "content_contract_configured": content_contract is not None,
        "live_proof_passed": proof_ok,
        "production_allowed": False,
        "runtime_connector_approved": False,
    }


__all__ = [
    "SANDBOX_CONTENT_STORAGE_KEY",
    "SandboxContentContract",
    "SandboxOperationalStatus",
    "evaluate_sandbox_operational_readiness",
    "safe_content_projection",
]
