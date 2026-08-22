"""Reference-only intake for a real CAMARA QoD operator sandbox.

This module deliberately accepts reference identifiers only. It does not accept
raw endpoint URLs, credentials, tokens, certificates, API keys, or payloads and
it does not perform network I/O. Receiving a complete intake is not provider
sandbox proof and does not approve the runtime connector.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from processual_api.integrations.camara_qod_governance_approval import (
    CAMARA_QOD_APPROVED_GOVERNANCE_VERSION,
)
from processual_api.integrations.camara_qod_runtime_registration import (
    CAMARA_QOD_RUNTIME_TASK_IDS,
)


class CamaraQodOperatorSandboxIntakeStatus(StrEnum):
    PENDING_OPERATOR_INPUT = "pending_operator_input"
    REFERENCES_RECEIVED_FOR_REVIEW = "references_received_for_review"
    BLOCKED = "blocked"


_REQUIRED_REFERENCE_NAMES: Final = (
    "operator_identity_reference",
    "sandbox_base_url_reference",
    "auth_contract_reference",
    "secret_provider_reference",
    "credential_reference",
    "tls_policy_reference",
    "outbound_allowlist_reference",
    "operator_approval_reference",
    "support_owner_reference",
    "rotation_policy_reference",
    "revocation_policy_reference",
)

_PROHIBITED_REFERENCE_MARKERS: Final = (
    "http://",
    "https://",
    "://",
    "bearer ",
    "basic ",
    "password=",
    "token=",
    "secret=",
    "client_secret=",
    "api_key=",
    "private_key=",
    "certificate=",
    "raw_payload=",
)


def _validate_reference(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string reference.")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} must not be empty.")
    if normalized != value:
        raise ValueError(f"{name} must not contain surrounding whitespace.")
    lowered = normalized.lower()
    if any(marker in lowered for marker in _PROHIBITED_REFERENCE_MARKERS):
        raise ValueError(f"{name} must be a reference identifier, not raw material.")
    return normalized


@dataclass(frozen=True, slots=True)
class CamaraQodOperatorSandboxReferenceSubmission:
    operator_identity_reference: str
    sandbox_base_url_reference: str
    auth_contract_reference: str
    secret_provider_reference: str
    credential_reference: str
    tls_policy_reference: str
    outbound_allowlist_reference: str
    operator_approval_reference: str
    support_owner_reference: str
    rotation_policy_reference: str
    revocation_policy_reference: str

    def __post_init__(self) -> None:
        for name in _REQUIRED_REFERENCE_NAMES:
            _validate_reference(name, getattr(self, name))


@dataclass(frozen=True, slots=True)
class CamaraQodOperatorSandboxIntakeAssessment:
    status: CamaraQodOperatorSandboxIntakeStatus
    governance_version: str
    runtime_task_ids: tuple[str, ...]
    received_reference_names: tuple[str, ...]
    missing_reference_names: tuple[str, ...]
    references_complete: bool
    endpoint_registered: bool = False
    credentials_resolved: bool = False
    provider_network_proof: bool = False
    provider_sandbox_proven: bool = False
    runtime_connector_approved: bool = False
    request_execution_allowed: bool = False
    production_allowed: bool = False


CAMARA_QOD_OPERATOR_SANDBOX_INTAKE_CONTRACT: Final = MappingProxyType(
    {
        "contract_id": "camara_qod_operator_sandbox_reference_intake_r1",
        "environment": "sandbox",
        "governance_version": CAMARA_QOD_APPROVED_GOVERNANCE_VERSION,
        "runtime_task_ids": CAMARA_QOD_RUNTIME_TASK_IDS,
        "required_reference_names": _REQUIRED_REFERENCE_NAMES,
        "reference_only": True,
        "raw_endpoint_allowed": False,
        "raw_credentials_allowed": False,
        "network_io_allowed": False,
        "provider_sandbox_proven": False,
        "runtime_connector_approved": False,
        "production_allowed": False,
    }
)


def assess_camara_qod_operator_sandbox_intake(
    submission: CamaraQodOperatorSandboxReferenceSubmission | None,
) -> CamaraQodOperatorSandboxIntakeAssessment:
    if submission is None:
        return CamaraQodOperatorSandboxIntakeAssessment(
            status=CamaraQodOperatorSandboxIntakeStatus.PENDING_OPERATOR_INPUT,
            governance_version=CAMARA_QOD_APPROVED_GOVERNANCE_VERSION,
            runtime_task_ids=CAMARA_QOD_RUNTIME_TASK_IDS,
            received_reference_names=(),
            missing_reference_names=_REQUIRED_REFERENCE_NAMES,
            references_complete=False,
        )

    received = tuple(
        name
        for name in _REQUIRED_REFERENCE_NAMES
        if _validate_reference(name, getattr(submission, name))
    )
    missing = tuple(name for name in _REQUIRED_REFERENCE_NAMES if name not in received)
    return CamaraQodOperatorSandboxIntakeAssessment(
        status=(
            CamaraQodOperatorSandboxIntakeStatus.REFERENCES_RECEIVED_FOR_REVIEW
            if not missing
            else CamaraQodOperatorSandboxIntakeStatus.BLOCKED
        ),
        governance_version=CAMARA_QOD_APPROVED_GOVERNANCE_VERSION,
        runtime_task_ids=CAMARA_QOD_RUNTIME_TASK_IDS,
        received_reference_names=received,
        missing_reference_names=missing,
        references_complete=not missing,
    )


def camara_qod_operator_sandbox_intake_payload(
    submission: CamaraQodOperatorSandboxReferenceSubmission | None = None,
) -> dict[str, object]:
    assessment = assess_camara_qod_operator_sandbox_intake(submission)
    return {
        "contract": {
            key: list(value) if isinstance(value, tuple) else value
            for key, value in CAMARA_QOD_OPERATOR_SANDBOX_INTAKE_CONTRACT.items()
        },
        "assessment": asdict(assessment),
    }


__all__ = [
    "CAMARA_QOD_OPERATOR_SANDBOX_INTAKE_CONTRACT",
    "CamaraQodOperatorSandboxIntakeAssessment",
    "CamaraQodOperatorSandboxIntakeStatus",
    "CamaraQodOperatorSandboxReferenceSubmission",
    "assess_camara_qod_operator_sandbox_intake",
    "camara_qod_operator_sandbox_intake_payload",
]
