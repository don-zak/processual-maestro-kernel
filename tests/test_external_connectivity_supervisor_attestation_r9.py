from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from processual_api.integrations.external_connectivity_cases import (
    ExternalConnectivityCase,
    ExternalConnectivityCaseState,
    SupervisorReadinessAttestation,
    SupervisorReadinessDecision,
    is_supervisor_readiness_attestation_current,
)

FINGERPRINT = "a" * 64
OTHER_FINGERPRINT = "b" * 64


def _case(
    *,
    state: ExternalConnectivityCaseState = (
        ExternalConnectivityCaseState.READINESS_APPROVED
    ),
    fingerprint: str = FINGERPRINT,
    assessment_id: str = "assessment_r9",
) -> ExternalConnectivityCase:
    return ExternalConnectivityCase(
        case_id="case_r9",
        client_id="client_r9",
        readiness_case_id="readiness_case_r9",
        integration_task_id="",
        connector_id="telecom_ticketing_reference",
        credential_profile_id="telecom_operations_api_reference",
        target_environment="sandbox",
        state=state,
        customer_package_fingerprint=fingerprint,
        readiness_assessment_id=assessment_id,
        revision=5,
        created_at="2026-07-14T10:00:00+00:00",
        updated_at="2026-07-14T10:04:00+00:00",
    )


def _attestation(
    *,
    decision: SupervisorReadinessDecision = (
        SupervisorReadinessDecision.APPROVED
    ),
    fingerprint: str = FINGERPRINT,
    assessment_id: str = "assessment_r9",
) -> SupervisorReadinessAttestation:
    return SupervisorReadinessAttestation(
        attestation_id="attestation_r9",
        case_id="case_r9",
        readiness_assessment_id=assessment_id,
        customer_package_fingerprint=fingerprint,
        decision=decision,
        supervisor_actor="supsk_r9_supervisor",
        reason_code="readiness_review_completed",
        issued_at="2026-07-14T10:05:00+00:00",
        expires_at="2026-07-15T10:05:00+00:00",
    )


def test_r9_supervisor_decision_catalog_is_exact() -> None:
    assert tuple(SupervisorReadinessDecision) == (
        SupervisorReadinessDecision.APPROVED,
        SupervisorReadinessDecision.REMEDIATION_REQUIRED,
        SupervisorReadinessDecision.REJECTED,
    )
    assert tuple(value.value for value in SupervisorReadinessDecision) == (
        "approved",
        "remediation_required",
        "rejected",
    )


def test_r9_attestation_is_frozen_and_default_deny() -> None:
    attestation = _attestation()

    with pytest.raises(FrozenInstanceError):
        attestation.reason_code = "forged"  # type: ignore[misc]

    assert attestation.production_allowed is False
    assert attestation.qualification_key_issuance_allowed is False
    assert attestation.sandbox_activation_allowed is False
    assert attestation.external_http_allowed is False
    assert attestation.secret_resolution_allowed is False


@pytest.mark.parametrize(
    ("field_name", "value"),
    (
        ("customer_package_fingerprint", "not-a-sha256"),
        ("supervisor_actor", ""),
        ("reason_code", ""),
        ("issued_at", ""),
        ("expires_at", ""),
    ),
)
def test_r9_attestation_rejects_invalid_required_values(
    field_name: str,
    value: str,
) -> None:
    with pytest.raises(ValueError):
        replace(_attestation(), **{field_name: value})


@pytest.mark.parametrize(
    "field_name",
    (
        "production_allowed",
        "qualification_key_issuance_allowed",
        "sandbox_activation_allowed",
        "external_http_allowed",
        "secret_resolution_allowed",
    ),
)
def test_r9_attestation_rejects_enabled_authority(
    field_name: str,
) -> None:
    with pytest.raises(ValueError, match="must_be_false"):
        replace(_attestation(), **{field_name: True})


def test_r9_approved_attestation_is_current_only_for_exact_case() -> None:
    assert is_supervisor_readiness_attestation_current(
        _attestation(),
        _case(),
        checked_at="2026-07-14T12:00:00+00:00",
    )


def test_r9_attestation_becomes_stale_when_package_changes() -> None:
    assert not is_supervisor_readiness_attestation_current(
        _attestation(),
        _case(fingerprint=OTHER_FINGERPRINT),
        checked_at="2026-07-14T12:00:00+00:00",
    )


def test_r9_attestation_becomes_stale_when_assessment_changes() -> None:
    assert not is_supervisor_readiness_attestation_current(
        _attestation(),
        _case(assessment_id="assessment_r9_new"),
        checked_at="2026-07-14T12:00:00+00:00",
    )


def test_r9_attestation_is_not_current_after_expiry() -> None:
    assert not is_supervisor_readiness_attestation_current(
        _attestation(),
        _case(),
        checked_at="2026-07-16T00:00:00+00:00",
    )


@pytest.mark.parametrize(
    "decision",
    (
        SupervisorReadinessDecision.REMEDIATION_REQUIRED,
        SupervisorReadinessDecision.REJECTED,
    ),
)
def test_r9_nonapproval_attestation_is_never_current(
    decision: SupervisorReadinessDecision,
) -> None:
    assert not is_supervisor_readiness_attestation_current(
        _attestation(decision=decision),
        _case(),
        checked_at="2026-07-14T12:00:00+00:00",
    )
