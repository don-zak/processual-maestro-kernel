"""Fail-closed runtime registration for the approved CAMARA QoD task set.

Registration does not grant provider or production execution authority. Admission
requires the exact entitlement and quota evidence, write approval where needed,
and later provider/connector qualification.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from types import MappingProxyType
from typing import Final

from processual_api.integrations.camara_qod_governance_approval import (
    CAMARA_QOD_APPROVED_ENTITLEMENT_IDS,
    CAMARA_QOD_APPROVED_GOVERNANCE_VERSION,
    CAMARA_QOD_APPROVED_QUOTA_METERS,
    CAMARA_QOD_APPROVED_TASK_IDS,
    CAMARA_QOD_GOVERNANCE_APPROVED,
)
from processual_api.integrations.camara_qod_semantic_mapping import (
    APPROVAL_GATED_WRITE,
    CAMARA_QOD_R32_CALLABLE_OPERATION_IDS,
    get_camara_qod_semantic_mapping,
)


@dataclass(frozen=True, slots=True)
class CamaraQodRuntimeRegistration:
    operation_id: str
    task_id: str
    method: str
    path: str
    security_scope: str
    operation_class: str
    entitlement_id: str
    quota_meter: str
    required_input_fields: tuple[str, ...]
    optional_input_fields: tuple[str, ...]
    approval_required: bool
    runtime_task_registered: bool = True
    runtime_connector_approved: bool = False
    provider_sandbox_proven: bool = False
    production_allowed: bool = False


def _build_registry() -> MappingProxyType[str, CamaraQodRuntimeRegistration]:
    if not CAMARA_QOD_GOVERNANCE_APPROVED:
        raise RuntimeError("CAMARA QoD runtime registration requires governance approval.")

    registrations: dict[str, CamaraQodRuntimeRegistration] = {}
    task_ids: list[str] = []
    entitlement_ids: set[str] = set()
    quota_meters: set[str] = set()

    for operation_id in CAMARA_QOD_R32_CALLABLE_OPERATION_IDS:
        mapping = get_camara_qod_semantic_mapping(operation_id)
        registration = CamaraQodRuntimeRegistration(
            operation_id=operation_id,
            task_id=mapping.proposed_task_id,
            method=mapping.method,
            path=mapping.path,
            security_scope=mapping.camara_scope,
            operation_class=mapping.operation_class,
            entitlement_id=mapping.proposed_entitlement_id,
            quota_meter=mapping.proposed_quota_meter,
            required_input_fields=mapping.required_input_fields,
            optional_input_fields=mapping.optional_input_fields,
            approval_required=mapping.operation_class == APPROVAL_GATED_WRITE,
        )
        registrations[registration.task_id] = registration
        task_ids.append(registration.task_id)
        entitlement_ids.add(registration.entitlement_id)
        quota_meters.add(registration.quota_meter)

    if tuple(task_ids) != CAMARA_QOD_APPROVED_TASK_IDS:
        raise RuntimeError("CAMARA QoD approved task set drift detected.")
    if tuple(sorted(entitlement_ids)) != CAMARA_QOD_APPROVED_ENTITLEMENT_IDS:
        raise RuntimeError("CAMARA QoD approved entitlement set drift detected.")
    if tuple(sorted(quota_meters)) != CAMARA_QOD_APPROVED_QUOTA_METERS:
        raise RuntimeError("CAMARA QoD approved quota-meter set drift detected.")

    return MappingProxyType(registrations)


CAMARA_QOD_RUNTIME_REGISTRY: Final = _build_registry()
CAMARA_QOD_RUNTIME_TASK_IDS: Final = tuple(CAMARA_QOD_RUNTIME_REGISTRY)


def get_camara_qod_runtime_registration(task_id: str) -> CamaraQodRuntimeRegistration:
    normalized = str(task_id or "").strip().lower()
    try:
        return CAMARA_QOD_RUNTIME_REGISTRY[normalized]
    except KeyError as exc:
        raise KeyError(f"Unsupported CAMARA QoD runtime task '{task_id}'.") from exc


def assess_camara_qod_runtime_admission(
    task_id: str,
    *,
    entitlement_ids: tuple[str, ...] = (),
    quota_remaining: int | None = None,
    approval_reference: str | None = None,
    provider_sandbox_proven: bool = False,
    runtime_connector_approved: bool = False,
) -> dict[str, object]:
    """Evaluate execution admission with conservative default-deny semantics."""

    registration = get_camara_qod_runtime_registration(task_id)
    blockers: list[str] = []

    entitlements = {str(value).strip() for value in entitlement_ids if str(value).strip()}
    if registration.entitlement_id not in entitlements:
        blockers.append("camara_qod_entitlement_missing")

    if quota_remaining is None:
        blockers.append("camara_qod_quota_evidence_missing")
    elif quota_remaining <= 0:
        blockers.append("camara_qod_quota_exhausted")

    if registration.approval_required and not str(approval_reference or "").strip():
        blockers.append("camara_qod_write_approval_missing")

    if not provider_sandbox_proven:
        blockers.append("camara_qod_provider_sandbox_unproven")
    if not runtime_connector_approved:
        blockers.append("camara_qod_runtime_connector_unapproved")

    blockers = sorted(set(blockers))
    return {
        "task_id": registration.task_id,
        "operation_id": registration.operation_id,
        "governance_approved": True,
        "approved_governance_version": CAMARA_QOD_APPROVED_GOVERNANCE_VERSION,
        "runtime_task_registered": True,
        "entitlement_id": registration.entitlement_id,
        "quota_meter": registration.quota_meter,
        "approval_required": registration.approval_required,
        "execution_allowed": not blockers,
        "blocker_codes": blockers,
        "runtime_connector_approved": runtime_connector_approved,
        "provider_sandbox_proven": provider_sandbox_proven,
        "production_allowed": False,
    }


def camara_qod_runtime_registration_payload() -> dict[str, object]:
    return {
        "approved_governance_version": CAMARA_QOD_APPROVED_GOVERNANCE_VERSION,
        "governance_approved": True,
        "runtime_task_registered": True,
        "registered_task_ids": list(CAMARA_QOD_RUNTIME_TASK_IDS),
        "registrations": [
            asdict(CAMARA_QOD_RUNTIME_REGISTRY[task_id])
            for task_id in CAMARA_QOD_RUNTIME_TASK_IDS
        ],
        "registered_entitlement_ids": list(CAMARA_QOD_APPROVED_ENTITLEMENT_IDS),
        "registered_quota_meters": list(CAMARA_QOD_APPROVED_QUOTA_METERS),
        "default_deny": True,
        "runtime_connector_approved": False,
        "provider_sandbox_proven": False,
        "production_allowed": False,
    }


__all__ = [
    "CAMARA_QOD_RUNTIME_REGISTRY",
    "CAMARA_QOD_RUNTIME_TASK_IDS",
    "CamaraQodRuntimeRegistration",
    "assess_camara_qod_runtime_admission",
    "camara_qod_runtime_registration_payload",
    "get_camara_qod_runtime_registration",
]
