"""Auditable approval record for the exact CAMARA QoD governance contract."""

from __future__ import annotations

from types import MappingProxyType
from typing import Final

CAMARA_QOD_APPROVED_GOVERNANCE_VERSION: Final = (
    "camara-qod-governance-r1@70d57dd3d8c9632c7e45260646c71049cbbc1cee"
)
CAMARA_QOD_APPROVED_CONTRACT_BLOB_SHA: Final = (
    "70d57dd3d8c9632c7e45260646c71049cbbc1cee"
)
CAMARA_QOD_GOVERNANCE_DECISION: Final = "approved_with_conditions"
CAMARA_QOD_GOVERNANCE_APPROVED: Final = True

CAMARA_QOD_APPROVED_TASK_IDS: Final = (
    "camara.qod.session_create",
    "camara.qod.session_get",
    "camara.qod.session_delete",
    "camara.qod.session_extend",
    "camara.qod.sessions_retrieve_by_device",
)
CAMARA_QOD_APPROVED_ENTITLEMENT_IDS: Final = (
    "camara_qod_session_manage",
    "camara_qod_session_read",
)
CAMARA_QOD_APPROVED_QUOTA_METERS: Final = (
    "camara_qod_session_create",
    "camara_qod_session_delete",
    "camara_qod_session_read",
    "camara_qod_session_retrieve_by_device",
    "camara_qod_session_update",
)

CAMARA_QOD_APPROVAL_BOUNDARIES: Final = MappingProxyType(
    {
        "runtime_connector_approved": False,
        "provider_sandbox_proven": False,
        "production_allowed": False,
        "staging_allowed": False,
    }
)


def camara_qod_governance_approval_payload() -> dict[str, object]:
    return {
        "governance_decision": CAMARA_QOD_GOVERNANCE_DECISION,
        "governance_approved": CAMARA_QOD_GOVERNANCE_APPROVED,
        "approved_governance_version": CAMARA_QOD_APPROVED_GOVERNANCE_VERSION,
        "approved_contract_blob_sha": CAMARA_QOD_APPROVED_CONTRACT_BLOB_SHA,
        "approved_task_ids": list(CAMARA_QOD_APPROVED_TASK_IDS),
        "approved_entitlement_ids": list(CAMARA_QOD_APPROVED_ENTITLEMENT_IDS),
        "approved_quota_meters": list(CAMARA_QOD_APPROVED_QUOTA_METERS),
        **dict(CAMARA_QOD_APPROVAL_BOUNDARIES),
    }


__all__ = [
    "CAMARA_QOD_APPROVAL_BOUNDARIES",
    "CAMARA_QOD_APPROVED_CONTRACT_BLOB_SHA",
    "CAMARA_QOD_APPROVED_ENTITLEMENT_IDS",
    "CAMARA_QOD_APPROVED_GOVERNANCE_VERSION",
    "CAMARA_QOD_APPROVED_QUOTA_METERS",
    "CAMARA_QOD_APPROVED_TASK_IDS",
    "CAMARA_QOD_GOVERNANCE_APPROVED",
    "CAMARA_QOD_GOVERNANCE_DECISION",
    "camara_qod_governance_approval_payload",
]
