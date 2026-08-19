"""Compatibility assessment between Telefonica QoD v0.10 evidence and CAMARA v1.1.0.

The assessment is intentionally non-authoritative: matching HTTP semantics do
not upgrade provider sandbox proof for the pinned CAMARA v1.1.0 contract.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Final

from processual_api.integrations.camara_qod_external_sandbox_qualification import (
    TELEFONICA_QOD_EXTERNAL_SANDBOX_EVIDENCE,
)
from processual_api.integrations.camara_qod_semantic_mapping import (
    CAMARA_QOD_R32_CALLABLE_OPERATION_IDS,
    get_camara_qod_semantic_mapping,
)


@dataclass(frozen=True, slots=True)
class CamaraQodProviderCompatibilityOperation:
    operation_id: str
    governed_method: str
    governed_path: str
    provider_method: str | None
    provider_path: str | None
    provider_proven: bool
    semantic_shape_matches: bool


_TELEFONICA_OPERATIONS: Final = {
    "createSession": ("POST", "/sessions", True),
    "getSession": ("GET", "/sessions/{sessionId}", True),
    "deleteSession": ("DELETE", "/sessions/{sessionId}", True),
    "extendQosSessionDuration": ("POST", "/sessions/{sessionId}/extend", False),
    "retrieveSessionsByDevice": (None, None, False),
}


def camara_qod_telefonica_compatibility_payload() -> dict[str, object]:
    operations: list[dict[str, object]] = []
    proven_ids: list[str] = []
    semantically_matching_ids: list[str] = []

    for operation_id in CAMARA_QOD_R32_CALLABLE_OPERATION_IDS:
        governed = get_camara_qod_semantic_mapping(operation_id)
        provider_method, provider_path, provider_proven = _TELEFONICA_OPERATIONS[operation_id]
        shape_matches = (
            provider_method == governed.method and provider_path == governed.path
        )
        operation = CamaraQodProviderCompatibilityOperation(
            operation_id=operation_id,
            governed_method=governed.method,
            governed_path=governed.path,
            provider_method=provider_method,
            provider_path=provider_path,
            provider_proven=provider_proven,
            semantic_shape_matches=shape_matches,
        )
        operations.append(asdict(operation))
        if provider_proven:
            proven_ids.append(operation_id)
        if shape_matches:
            semantically_matching_ids.append(operation_id)

    blockers = [
        "provider_api_version_v0_10_differs_from_governed_v1_1_0",
        "operator_network_qos_unproven",
        "runtime_connector_unapproved",
    ]
    if "extendQosSessionDuration" not in proven_ids:
        blockers.append("telefonica_extend_operation_unproven")
    if "retrieveSessionsByDevice" not in proven_ids:
        blockers.append("telefonica_retrieve_sessions_by_device_unproven")

    return {
        "provider": TELEFONICA_QOD_EXTERNAL_SANDBOX_EVIDENCE.provider,
        "provider_api_version": TELEFONICA_QOD_EXTERNAL_SANDBOX_EVIDENCE.provider_api_version,
        "governed_api_version": "1.1.0",
        "compatibility_state": "partial_interoperability_only",
        "operations": operations,
        "provider_proven_operation_ids": proven_ids,
        "semantically_matching_operation_ids": semantically_matching_ids,
        "provider_sandbox_proven": False,
        "runtime_connector_approved": False,
        "production_allowed": False,
        "blocker_codes": sorted(blockers),
    }


__all__ = [
    "CamaraQodProviderCompatibilityOperation",
    "camara_qod_telefonica_compatibility_payload",
]
