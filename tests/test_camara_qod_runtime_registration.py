from __future__ import annotations

import pytest

from processual_api.integrations.camara_qod_governance_approval import (
    CAMARA_QOD_APPROVED_ENTITLEMENT_IDS,
    CAMARA_QOD_APPROVED_GOVERNANCE_VERSION,
    CAMARA_QOD_APPROVED_QUOTA_METERS,
    CAMARA_QOD_APPROVED_TASK_IDS,
    CAMARA_QOD_GOVERNANCE_APPROVED,
)
from processual_api.integrations.camara_qod_runtime_registration import (
    CAMARA_QOD_RUNTIME_TASK_IDS,
    assess_camara_qod_runtime_admission,
    camara_qod_runtime_registration_payload,
    get_camara_qod_runtime_registration,
)


def test_governance_approval_is_exact_and_does_not_grant_connector_authority() -> None:
    assert CAMARA_QOD_GOVERNANCE_APPROVED is True
    assert CAMARA_QOD_APPROVED_GOVERNANCE_VERSION == (
        "camara-qod-governance-r1@70d57dd3d8c9632c7e45260646c71049cbbc1cee"
    )
    assert len(CAMARA_QOD_APPROVED_TASK_IDS) == 5
    assert CAMARA_QOD_APPROVED_ENTITLEMENT_IDS == (
        "camara_qod_session_manage",
        "camara_qod_session_read",
    )
    assert CAMARA_QOD_APPROVED_QUOTA_METERS == (
        "camara_qod_session_create",
        "camara_qod_session_delete",
        "camara_qod_session_read",
        "camara_qod_session_retrieve_by_device",
        "camara_qod_session_update",
    )


def test_exact_approved_qod_tasks_are_runtime_registered() -> None:
    assert CAMARA_QOD_RUNTIME_TASK_IDS == CAMARA_QOD_APPROVED_TASK_IDS
    payload = camara_qod_runtime_registration_payload()
    assert payload["governance_approved"] is True
    assert payload["runtime_task_registered"] is True
    assert payload["registered_task_ids"] == list(CAMARA_QOD_APPROVED_TASK_IDS)
    assert payload["registered_entitlement_ids"] == list(
        CAMARA_QOD_APPROVED_ENTITLEMENT_IDS
    )
    assert payload["registered_quota_meters"] == list(CAMARA_QOD_APPROVED_QUOTA_METERS)
    assert payload["default_deny"] is True
    assert payload["runtime_connector_approved"] is False
    assert payload["provider_sandbox_proven"] is False
    assert payload["production_allowed"] is False


@pytest.mark.parametrize(
    "task_id,approval_required",
    [
        ("camara.qod.session_create", True),
        ("camara.qod.session_get", False),
        ("camara.qod.session_delete", True),
        ("camara.qod.session_extend", True),
        ("camara.qod.sessions_retrieve_by_device", False),
    ],
)
def test_registration_preserves_write_approval_boundary(
    task_id: str,
    approval_required: bool,
) -> None:
    registration = get_camara_qod_runtime_registration(task_id)
    assert registration.runtime_task_registered is True
    assert registration.approval_required is approval_required
    assert registration.runtime_connector_approved is False
    assert registration.provider_sandbox_proven is False
    assert registration.production_allowed is False


def test_default_admission_denies_without_entitlement_quota_provider_or_connector() -> None:
    result = assess_camara_qod_runtime_admission("camara.qod.session_get")
    assert result["execution_allowed"] is False
    assert result["blocker_codes"] == [
        "camara_qod_entitlement_missing",
        "camara_qod_provider_sandbox_unproven",
        "camara_qod_quota_evidence_missing",
        "camara_qod_runtime_connector_unapproved",
    ]
    assert result["production_allowed"] is False


def test_write_cannot_bypass_approval_even_with_other_runtime_evidence() -> None:
    result = assess_camara_qod_runtime_admission(
        "camara.qod.session_create",
        entitlement_ids=("camara_qod_session_manage",),
        quota_remaining=1,
        provider_sandbox_proven=True,
        runtime_connector_approved=True,
    )
    assert result["execution_allowed"] is False
    assert result["blocker_codes"] == ["camara_qod_write_approval_missing"]
    assert result["production_allowed"] is False


def test_read_requires_entitlement_and_positive_quota_before_execution() -> None:
    exhausted = assess_camara_qod_runtime_admission(
        "camara.qod.session_get",
        entitlement_ids=("camara_qod_session_read",),
        quota_remaining=0,
        provider_sandbox_proven=True,
        runtime_connector_approved=True,
    )
    assert exhausted["execution_allowed"] is False
    assert exhausted["blocker_codes"] == ["camara_qod_quota_exhausted"]

    allowed_sandbox_admission = assess_camara_qod_runtime_admission(
        "camara.qod.session_get",
        entitlement_ids=("camara_qod_session_read",),
        quota_remaining=1,
        provider_sandbox_proven=True,
        runtime_connector_approved=True,
    )
    assert allowed_sandbox_admission["execution_allowed"] is True
    assert allowed_sandbox_admission["blocker_codes"] == []
    assert allowed_sandbox_admission["production_allowed"] is False


def test_write_is_admissible_only_with_explicit_approval_and_all_other_gates() -> None:
    result = assess_camara_qod_runtime_admission(
        "camara.qod.session_delete",
        entitlement_ids=("camara_qod_session_manage",),
        quota_remaining=1,
        approval_reference="approval:test-only",
        provider_sandbox_proven=True,
        runtime_connector_approved=True,
    )
    assert result["execution_allowed"] is True
    assert result["blocker_codes"] == []
    assert result["production_allowed"] is False


def test_unknown_runtime_task_fails_closed() -> None:
    with pytest.raises(KeyError, match="Unsupported CAMARA QoD runtime task"):
        get_camara_qod_runtime_registration("camara.qod.unreviewed")
