"""Reviewed semantic mapping for the pinned CAMARA QoD r3.2 API.

This module deliberately does not register runtime tasks or a connector. It
records the exact provider operation/scopes and the proposed Maestro semantics
that must be reviewed before endpoint bindings can become executable.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from types import MappingProxyType
from typing import Any

from processual_api.integrations.integration_task_catalog import SUPPORTED_INTEGRATION_TASKS
from processual_api.integrations.trusted_endpoint_source_acquisition import (
    CAMARA_QOD_R32_COMMIT,
    CAMARA_QOD_R32_PATH,
)

READ = "read"
APPROVAL_GATED_WRITE = "approval_gated_write"


@dataclass(frozen=True, slots=True)
class CamaraQodSemanticMapping:
    operation_id: str
    method: str
    path: str
    camara_scope: str
    proposed_task_id: str
    operation_class: str
    required_input_fields: tuple[str, ...]
    optional_input_fields: tuple[str, ...]
    conditional_input_rules: tuple[str, ...]
    data_classifications: tuple[str, ...]
    proposed_entitlement_id: str
    proposed_quota_meter: str
    runtime_task_registered: bool = False
    runtime_connector_approved: bool = False
    production_allowed: bool = False


@dataclass(frozen=True, slots=True)
class CamaraQodGovernanceCandidate:
    operation_id: str
    task_id: str
    operation_class: str
    entitlement_id: str
    quota_meter: str
    approval_required: bool
    runtime_registered: bool = False


_MAPPINGS = {
    "createSession": CamaraQodSemanticMapping(
        operation_id="createSession",
        method="POST",
        path="/sessions",
        camara_scope="quality-on-demand:sessions:create",
        proposed_task_id="camara.qod.session_create",
        operation_class=APPROVAL_GATED_WRITE,
        required_input_fields=("application_server", "qos_profile", "duration_seconds"),
        optional_input_fields=(
            "device",
            "device_ports",
            "application_server_ports",
            "notification_sink",
            "notification_sink_credential_reference",
        ),
        conditional_input_rules=(
            "two_legged_token_requires_device",
            "three_legged_token_forbids_device",
            "notification_sink_credential_must_be_managed_reference",
        ),
        data_classifications=(
            "network_identifier",
            "device_identifier_possible_personal_data",
            "application_endpoint",
        ),
        proposed_entitlement_id="camara_qod_session_manage",
        proposed_quota_meter="camara_qod_session_create",
    ),
    "getSession": CamaraQodSemanticMapping(
        operation_id="getSession",
        method="GET",
        path="/sessions/{sessionId}",
        camara_scope="quality-on-demand:sessions:read",
        proposed_task_id="camara.qod.session_get",
        operation_class=READ,
        required_input_fields=("session_id",),
        optional_input_fields=(),
        conditional_input_rules=(
            "three_legged_token_subject_must_match_session_subject",
            "session_must_belong_to_same_api_consumer",
        ),
        data_classifications=("session_identifier", "network_service_state"),
        proposed_entitlement_id="camara_qod_session_read",
        proposed_quota_meter="camara_qod_session_read",
    ),
    "deleteSession": CamaraQodSemanticMapping(
        operation_id="deleteSession",
        method="DELETE",
        path="/sessions/{sessionId}",
        camara_scope="quality-on-demand:sessions:delete",
        proposed_task_id="camara.qod.session_delete",
        operation_class=APPROVAL_GATED_WRITE,
        required_input_fields=("session_id",),
        optional_input_fields=(),
        conditional_input_rules=(
            "three_legged_token_subject_must_match_session_subject",
            "session_must_belong_to_same_api_consumer",
        ),
        data_classifications=("session_identifier", "network_service_control"),
        proposed_entitlement_id="camara_qod_session_manage",
        proposed_quota_meter="camara_qod_session_delete",
    ),
    "extendQosSessionDuration": CamaraQodSemanticMapping(
        operation_id="extendQosSessionDuration",
        method="POST",
        path="/sessions/{sessionId}/extend",
        camara_scope="quality-on-demand:sessions:update",
        proposed_task_id="camara.qod.session_extend",
        operation_class=APPROVAL_GATED_WRITE,
        required_input_fields=("session_id", "requested_additional_duration_seconds"),
        optional_input_fields=(),
        conditional_input_rules=(
            "three_legged_token_subject_must_match_session_subject",
            "session_must_belong_to_same_api_consumer",
            "provider_qos_profile_max_duration_applies",
        ),
        data_classifications=("session_identifier", "network_service_control"),
        proposed_entitlement_id="camara_qod_session_manage",
        proposed_quota_meter="camara_qod_session_update",
    ),
    "retrieveSessionsByDevice": CamaraQodSemanticMapping(
        operation_id="retrieveSessionsByDevice",
        method="POST",
        path="/retrieve-sessions",
        camara_scope="quality-on-demand:sessions:retrieve-by-device",
        proposed_task_id="camara.qod.sessions_retrieve_by_device",
        operation_class=READ,
        required_input_fields=(),
        optional_input_fields=("device",),
        conditional_input_rules=(
            "two_legged_token_requires_device",
            "three_legged_token_forbids_device",
            "three_legged_token_subject_selects_device",
        ),
        data_classifications=(
            "device_identifier_possible_personal_data",
            "network_service_state",
        ),
        proposed_entitlement_id="camara_qod_session_read",
        proposed_quota_meter="camara_qod_session_retrieve_by_device",
    ),
}

CAMARA_QOD_R32_SEMANTIC_MAPPINGS = MappingProxyType(_MAPPINGS)
CAMARA_QOD_R32_CALLABLE_OPERATION_IDS = tuple(_MAPPINGS)
CAMARA_QOD_R32_CALLBACK_OPERATION_IDS = ("postNotification",)

_GOVERNANCE_CANDIDATES = {
    operation_id: CamaraQodGovernanceCandidate(
        operation_id=operation_id,
        task_id=mapping.proposed_task_id,
        operation_class=mapping.operation_class,
        entitlement_id=mapping.proposed_entitlement_id,
        quota_meter=mapping.proposed_quota_meter,
        approval_required=mapping.operation_class == APPROVAL_GATED_WRITE,
    )
    for operation_id, mapping in _MAPPINGS.items()
}
CAMARA_QOD_GOVERNANCE_CANDIDATES = MappingProxyType(_GOVERNANCE_CANDIDATES)
CAMARA_QOD_ENTITLEMENT_CANDIDATES = (
    "camara_qod_session_manage",
    "camara_qod_session_read",
)
CAMARA_QOD_QUOTA_METER_CANDIDATES = (
    "camara_qod_session_create",
    "camara_qod_session_delete",
    "camara_qod_session_read",
    "camara_qod_session_retrieve_by_device",
    "camara_qod_session_update",
)


def get_camara_qod_semantic_mapping(operation_id: str) -> CamaraQodSemanticMapping:
    try:
        return CAMARA_QOD_R32_SEMANTIC_MAPPINGS[str(operation_id or "").strip()]
    except KeyError as exc:
        raise KeyError(f"Unsupported CAMARA QoD operation '{operation_id}'.") from exc


def assess_camara_qod_semantic_alignment(
    discovered_operations: Sequence[Mapping[str, Any]],
) -> dict[str, object]:
    """Require exact operation/method/path/scope alignment with the reviewed map."""

    by_id: dict[str, Mapping[str, Any]] = {}
    blockers: list[str] = []
    for operation in discovered_operations:
        operation_id = str(operation.get("operation_id") or "").strip()
        if not operation_id:
            blockers.append("camara_qod_operation_id_missing")
            continue
        if operation_id in by_id:
            blockers.append(f"camara_qod_duplicate_operation:{operation_id}")
            continue
        by_id[operation_id] = operation

    expected_ids = set(CAMARA_QOD_R32_CALLABLE_OPERATION_IDS)
    discovered_ids = set(by_id)
    for operation_id in sorted(expected_ids - discovered_ids):
        blockers.append(f"camara_qod_expected_operation_missing:{operation_id}")
    for operation_id in sorted(discovered_ids - expected_ids):
        blockers.append(f"camara_qod_unreviewed_operation_present:{operation_id}")

    aligned_ids: list[str] = []
    for operation_id in CAMARA_QOD_R32_CALLABLE_OPERATION_IDS:
        operation = by_id.get(operation_id)
        if operation is None:
            continue
        mapping = _MAPPINGS[operation_id]
        method = str(operation.get("method") or "").upper()
        path = str(operation.get("path") or "")
        scopes = tuple(sorted(str(scope) for scope in operation.get("security_scopes", ())))
        expected_scopes = (mapping.camara_scope,)
        if method != mapping.method:
            blockers.append(f"camara_qod_method_drift:{operation_id}")
        if path != mapping.path:
            blockers.append(f"camara_qod_path_drift:{operation_id}")
        if scopes != expected_scopes:
            blockers.append(f"camara_qod_scope_drift:{operation_id}")
        if method == mapping.method and path == mapping.path and scopes == expected_scopes:
            aligned_ids.append(operation_id)

    blockers = sorted(set(blockers))
    return {
        "semantic_mapping_aligned": not blockers,
        "semantic_mapping_blocker_codes": blockers,
        "aligned_operation_ids": aligned_ids,
        "expected_operation_ids": list(CAMARA_QOD_R32_CALLABLE_OPERATION_IDS),
        "runtime_task_registered": False,
        "runtime_connector_approved": False,
        "production_allowed": False,
    }


def assess_camara_qod_governance_candidate() -> dict[str, object]:
    """Validate the governance proposal without granting runtime authority."""

    blockers: list[str] = []
    task_ids: list[str] = []
    entitlement_ids: set[str] = set()
    quota_meters: set[str] = set()

    for operation_id in CAMARA_QOD_R32_CALLABLE_OPERATION_IDS:
        mapping = _MAPPINGS[operation_id]
        candidate = _GOVERNANCE_CANDIDATES[operation_id]
        if candidate.task_id != mapping.proposed_task_id:
            blockers.append(f"camara_qod_governance_task_drift:{operation_id}")
        if candidate.operation_class != mapping.operation_class:
            blockers.append(f"camara_qod_governance_operation_class_drift:{operation_id}")
        if candidate.entitlement_id != mapping.proposed_entitlement_id:
            blockers.append(f"camara_qod_governance_entitlement_drift:{operation_id}")
        if candidate.quota_meter != mapping.proposed_quota_meter:
            blockers.append(f"camara_qod_governance_quota_drift:{operation_id}")
        if candidate.approval_required is not (
            mapping.operation_class == APPROVAL_GATED_WRITE
        ):
            blockers.append(f"camara_qod_governance_approval_drift:{operation_id}")
        if candidate.runtime_registered:
            blockers.append(f"camara_qod_governance_candidate_runtime_enabled:{operation_id}")
        if candidate.task_id in SUPPORTED_INTEGRATION_TASKS:
            blockers.append(f"camara_qod_governance_task_already_registered:{operation_id}")

        task_ids.append(candidate.task_id)
        entitlement_ids.add(candidate.entitlement_id)
        quota_meters.add(candidate.quota_meter)

    if len(task_ids) != len(set(task_ids)):
        blockers.append("camara_qod_governance_task_ids_must_be_unique")
    if tuple(sorted(entitlement_ids)) != CAMARA_QOD_ENTITLEMENT_CANDIDATES:
        blockers.append("camara_qod_governance_entitlement_set_drift")
    if tuple(sorted(quota_meters)) != CAMARA_QOD_QUOTA_METER_CANDIDATES:
        blockers.append("camara_qod_governance_quota_meter_set_drift")

    blockers = sorted(set(blockers))
    return {
        "governance_candidate_valid": not blockers,
        "governance_blocker_codes": blockers,
        "candidate_task_ids": task_ids,
        "candidate_entitlement_ids": list(CAMARA_QOD_ENTITLEMENT_CANDIDATES),
        "candidate_quota_meters": list(CAMARA_QOD_QUOTA_METER_CANDIDATES),
        "governance_approved": False,
        "runtime_task_registered": False,
        "runtime_connector_approved": False,
        "provider_sandbox_proven": False,
        "production_allowed": False,
    }


def camara_qod_semantic_mapping_payload() -> dict[str, object]:
    return {
        "source_identity_id": "camara.quality_on_demand.r3_2",
        "repository": "camaraproject/QualityOnDemand",
        "source_revision": CAMARA_QOD_R32_COMMIT,
        "source_path": CAMARA_QOD_R32_PATH,
        "api_version": "1.1.0",
        "mapping_state": "proposal_only",
        "callable_operations": [asdict(_MAPPINGS[key]) for key in _MAPPINGS],
        "callback_operations_excluded_from_outbound_binding": list(
            CAMARA_QOD_R32_CALLBACK_OPERATION_IDS
        ),
        "existing_network_assurance_reused": False,
        "governance_candidate": {
            "candidate_state": "review_required",
            "tasks": [
                asdict(_GOVERNANCE_CANDIDATES[key])
                for key in CAMARA_QOD_R32_CALLABLE_OPERATION_IDS
            ],
            **assess_camara_qod_governance_candidate(),
        },
        "runtime_task_registered": False,
        "runtime_connector_approved": False,
        "provider_sandbox_proven": False,
        "production_allowed": False,
    }


__all__ = [
    "APPROVAL_GATED_WRITE",
    "CAMARA_QOD_ENTITLEMENT_CANDIDATES",
    "CAMARA_QOD_GOVERNANCE_CANDIDATES",
    "CAMARA_QOD_QUOTA_METER_CANDIDATES",
    "CAMARA_QOD_R32_CALLBACK_OPERATION_IDS",
    "CAMARA_QOD_R32_CALLABLE_OPERATION_IDS",
    "CAMARA_QOD_R32_SEMANTIC_MAPPINGS",
    "CamaraQodGovernanceCandidate",
    "CamaraQodSemanticMapping",
    "READ",
    "assess_camara_qod_governance_candidate",
    "assess_camara_qod_semantic_alignment",
    "camara_qod_semantic_mapping_payload",
    "get_camara_qod_semantic_mapping",
]
