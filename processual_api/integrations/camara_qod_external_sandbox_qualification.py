"""Independent external-sandbox evidence for CAMARA QoD qualification.

This module records only evidence already retained in the repository from a
user-executed Telefonica Open Gateway sandbox/mock run. It intentionally does
not upgrade provider-network proof, connector approval, or production authority
for the governed CAMARA QoD v1.1.0 contract.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class CamaraQodExternalSandboxEvidence:
    provider: str
    environment: str
    provider_api_version: str
    authorization_flow: str
    provider_scope: str
    qod_base_uri: str
    evidence_path: str
    missing_session_divergence_evidence_path: str
    session_lifecycle_execution_commit: str
    extend_execution_commit: str
    missing_session_probe_execution_commit: str
    proven_operations: tuple[str, ...]
    authenticated_sandbox_reachability_proven: bool
    external_mock_sandbox_proven: bool
    external_mock_extend_proven: bool
    negative_path_conformance_complete: bool
    missing_session_documented_expectation_met: bool
    mock_documentation_divergence_observed: bool
    operator_network_qos_proven: bool = False
    governed_camara_v1_1_provider_sandbox_proven: bool = False
    runtime_connector_approved: bool = False
    production_allowed: bool = False


TELEFONICA_QOD_EXTERNAL_SANDBOX_EVIDENCE: Final = CamaraQodExternalSandboxEvidence(
    provider="telefonica_open_gateway",
    environment="sandbox_mock_candidate",
    provider_api_version="v0.10",
    authorization_flow="CIBA",
    provider_scope="dpv:RequestedServiceProvision#qod",
    qod_base_uri="https://sandbox.opengateway.telefonica.com/apigateway/qod/v0",
    evidence_path=(
        "docs/qualification/evidence/"
        "TELEFONICA_QOD_CIBA_SESSION_LIFECYCLE_2026-08-19.json"
    ),
    missing_session_divergence_evidence_path=(
        "docs/qualification/evidence/"
        "TELEFONICA_QOD_MISSING_SESSION_DIVERGENCE_2026-08-19.json"
    ),
    session_lifecycle_execution_commit="558dc92f5b43b32b05917f52d21e7cae442b7fd6",
    extend_execution_commit="046835b656be7536d5b5bb9b7ad257503875e655",
    missing_session_probe_execution_commit="abcf5388ae56571715287d7d473ef7c17af38041",
    proven_operations=(
        "createSession",
        "getSession",
        "deleteSession",
        "extendQosSessionDuration",
    ),
    authenticated_sandbox_reachability_proven=True,
    external_mock_sandbox_proven=True,
    external_mock_extend_proven=True,
    negative_path_conformance_complete=False,
    missing_session_documented_expectation_met=False,
    mock_documentation_divergence_observed=True,
)


def camara_qod_external_sandbox_qualification_payload() -> dict[str, object]:
    """Project external evidence without converting it into provider authority."""

    payload = asdict(TELEFONICA_QOD_EXTERNAL_SANDBOX_EVIDENCE)
    payload["evidence_class"] = "external_mock_interoperability_with_divergence"
    payload["compatible_with_governed_contract"] = "partial_semantic_only"
    payload["provider_sandbox_proven"] = False
    payload["qualification_blockers"] = [
        "telefonica_api_version_differs_from_governed_camara_v1_1",
        "telefonica_missing_session_returns_200_instead_of_documented_404",
        "telefonica_negative_path_conformance_incomplete",
        "operator_network_qos_unproven",
        "retrieve_sessions_by_device_unproven",
        "runtime_connector_unapproved",
    ]
    return payload


__all__ = [
    "CamaraQodExternalSandboxEvidence",
    "TELEFONICA_QOD_EXTERNAL_SANDBOX_EVIDENCE",
    "camara_qod_external_sandbox_qualification_payload",
]
