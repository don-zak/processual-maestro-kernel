from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from processual_api.integrations.connector_bindings import (
    ConnectorEnvironmentBinding,
    get_connector_secret_reference,
    list_connector_environment_bindings,
)
from processual_api.integrations.external_connectivity_cases import (
    ExternalConnectivityCaseState,
    customer_reference_package_fingerprint,
)
from processual_api.schemas.external_connectivity import (
    CustomerReferencePackageSubmissionRequest,
    ExternalConnectivityCaseCreateRequest,
)
from processual_api.services.external_connectivity_case_store import (
    load_external_connectivity_case_store,
)
from processual_api.services.external_connectivity_intake import (
    EXTERNAL_CONNECTIVITY_INTAKE_SCHEMA_VERSION,
    ExternalConnectivityIntakeError,
    SupervisorReadinessDecision,
    create_external_connectivity_case,
    get_external_connectivity_case,
    is_supervisor_readiness_attestation_current,
    list_external_connectivity_cases,
    record_external_connectivity_supervisor_decision,
    review_external_connectivity_reference_package,
    submit_external_connectivity_reference_package,
)

CREATED_AT = "2026-07-14T10:00:00+00:00"
SUBMITTED_AT = "2026-07-14T10:01:00+00:00"
REVIEWED_AT = "2026-07-14T10:02:00+00:00"
DECIDED_AT = "2026-07-14T10:03:00+00:00"
EXPIRES_AT = "2026-07-15T10:03:00+00:00"
ACTOR = "supsk_r9_supervisor"


def _sandbox_binding() -> ConnectorEnvironmentBinding:
    return next(
        binding
        for binding in list_connector_environment_bindings()
        if binding.environment == "sandbox"
    )


def _create_request() -> ExternalConnectivityCaseCreateRequest:
    binding = _sandbox_binding()
    secret_reference = get_connector_secret_reference(
        binding.secret_reference_ids[0]
    )

    return ExternalConnectivityCaseCreateRequest(
        client_id="client_r9",
        readiness_case_id="readiness_case_r9",
        connector_id=binding.connector_id,
        credential_profile_id=(
            secret_reference.credential_profile_id
        ),
        target_environment="sandbox",
    )


def _submission(
    *,
    package_id: str = "package_r9",
    target_reference_id: str | None = None,
    dns_reference: str = "dns_reference_r9",
) -> CustomerReferencePackageSubmissionRequest:
    binding = _sandbox_binding()
    secret_reference = get_connector_secret_reference(
        binding.secret_reference_ids[0]
    )

    return CustomerReferencePackageSubmissionRequest(
        package_id=package_id,
        client_id="client_r9",
        schema_version="customer-reference-package/v1",
        connector_id=binding.connector_id,
        credential_profile_id=(
            secret_reference.credential_profile_id
        ),
        target_environment="sandbox",
        target_reference_id=(
            target_reference_id
            if target_reference_id is not None
            else binding.target_reference_id
        ),
        secret_reference_ids=binding.secret_reference_ids,
        dns_reference=dns_reference,
        tls_policy_reference="tls_policy_reference_r9",
        certificate_reference="certificate_reference_r9",
        outbound_allowlist_reference=(
            "outbound_allowlist_reference_r9"
        ),
        submitted_at=SUBMITTED_AT,
    )


def _create_case(path: Path):
    return create_external_connectivity_case(
        _create_request(),
        case_id="case_r9",
        actor=ACTOR,
        occurred_at=CREATED_AT,
        path=path,
    )


def _submit_case(path: Path):
    _create_case(path)
    return submit_external_connectivity_reference_package(
        "case_r9",
        _submission(),
        expected_revision=1,
        actor=ACTOR,
        occurred_at=SUBMITTED_AT,
        path=path,
    )


def _review_ready_case(path: Path):
    _submit_case(path)
    assessment = review_external_connectivity_reference_package(
        "case_r9",
        assessment_id="assessment_r9",
        expected_revision=2,
        actor=ACTOR,
        occurred_at=REVIEWED_AT,
        path=path,
    )
    return assessment


def test_r9_intake_schema_version_is_fixed() -> None:
    assert EXTERNAL_CONNECTIVITY_INTAKE_SCHEMA_VERSION == (
        "external-connectivity-intake/v1"
    )


def test_r9_create_case_persists_clean_draft(tmp_path: Path) -> None:
    store = tmp_path / "cases.json"
    case = _create_case(store)

    assert case.state is ExternalConnectivityCaseState.DRAFT
    assert case.revision == 1
    assert case.target_environment == "sandbox"
    assert case.production_allowed is False
    assert case.external_http_allowed is False
    assert case.secret_resolution_allowed is False

    assert get_external_connectivity_case(
        "case_r9",
        path=store,
    ) == case
    assert list_external_connectivity_cases(path=store) == (case,)


def test_r9_duplicate_case_is_rejected_without_mutation(
    tmp_path: Path,
) -> None:
    store = tmp_path / "cases.json"
    original = _create_case(store)
    before = store.read_bytes()

    with pytest.raises(
        ExternalConnectivityIntakeError,
        match="case_already_exists",
    ):
        _create_case(store)

    assert store.read_bytes() == before
    assert get_external_connectivity_case(
        "case_r9",
        path=store,
    ) == original


def test_r9_submission_persists_package_and_fingerprint(
    tmp_path: Path,
) -> None:
    store = tmp_path / "cases.json"
    case = _submit_case(store)
    snapshot = load_external_connectivity_case_store(store)

    assert case.state is (
        ExternalConnectivityCaseState.CUSTOMER_PACKAGE_SUBMITTED
    )
    assert case.revision == 2
    assert len(snapshot.customer_reference_packages) == 1

    package = snapshot.customer_reference_packages[0]

    assert case.customer_package_fingerprint == (
        customer_reference_package_fingerprint(package)
    )
    assert case.readiness_assessment_id == ""


def test_r9_stale_revision_is_rejected_without_mutation(
    tmp_path: Path,
) -> None:
    store = tmp_path / "cases.json"
    _create_case(store)
    before = store.read_bytes()

    with pytest.raises(
        ExternalConnectivityIntakeError,
        match="case_revision_conflict",
    ):
        submit_external_connectivity_reference_package(
            "case_r9",
            _submission(),
            expected_revision=99,
            actor=ACTOR,
            occurred_at=SUBMITTED_AT,
            path=store,
        )

    assert store.read_bytes() == before


def test_r9_valid_binding_becomes_ready_for_supervisor(
    tmp_path: Path,
) -> None:
    store = tmp_path / "cases.json"
    assessment = _review_ready_case(store)
    case = get_external_connectivity_case(
        "case_r9",
        path=store,
    )

    assert assessment.ready_for_supervisor_approval is True
    assert assessment.readiness_status == (
        "ready_for_supervisor_approval"
    )
    assert assessment.blocker_codes == ()
    assert assessment.remediation_codes == ()
    assert assessment.evidence_completeness == 1.0

    assert case.state is (
        ExternalConnectivityCaseState.READY_FOR_SUPERVISOR_APPROVAL
    )
    assert case.revision == 4
    assert case.readiness_assessment_id == "assessment_r9"

    assert assessment.network_access_performed is False
    assert assessment.secrets_read is False
    assert assessment.provider_sdk_initialized is False
    assert assessment.certificate_loaded is False
    assert assessment.sandbox_launched is False
    assert assessment.production_allowed is False


def test_r9_mismatched_target_requires_remediation(
    tmp_path: Path,
) -> None:
    store = tmp_path / "cases.json"
    _create_case(store)

    submitted = submit_external_connectivity_reference_package(
        "case_r9",
        _submission(
            target_reference_id="mismatched_target_reference"
        ),
        expected_revision=1,
        actor=ACTOR,
        occurred_at=SUBMITTED_AT,
        path=store,
    )

    assessment = review_external_connectivity_reference_package(
        "case_r9",
        assessment_id="assessment_r9_blocked",
        expected_revision=submitted.revision,
        actor=ACTOR,
        occurred_at=REVIEWED_AT,
        path=store,
    )

    case = get_external_connectivity_case(
        "case_r9",
        path=store,
    )

    assert assessment.ready_for_supervisor_approval is False
    assert "target_reference_mismatch" in assessment.blocker_codes
    assert (
        "provide_declared_target_reference"
        in assessment.remediation_codes
    )
    assert case.state is (
        ExternalConnectivityCaseState.NEEDS_REMEDIATION
    )


def test_r9_approval_is_bound_to_exact_fingerprint(
    tmp_path: Path,
) -> None:
    store = tmp_path / "cases.json"
    assessment = _review_ready_case(store)
    case_before = get_external_connectivity_case(
        "case_r9",
        path=store,
    )

    attestation = record_external_connectivity_supervisor_decision(
        "case_r9",
        decision=SupervisorReadinessDecision.APPROVED,
        attestation_id="attestation_r9",
        expected_revision=case_before.revision,
        expected_package_fingerprint=(
            assessment.customer_package_fingerprint
        ),
        actor=ACTOR,
        reason_code="readiness_review_completed",
        occurred_at=DECIDED_AT,
        expires_at=EXPIRES_AT,
        path=store,
    )

    approved_case = get_external_connectivity_case(
        "case_r9",
        path=store,
    )

    assert approved_case.state is (
        ExternalConnectivityCaseState.READINESS_APPROVED
    )
    assert approved_case.revision == 5

    assert is_supervisor_readiness_attestation_current(
        attestation,
        approved_case,
        checked_at=DECIDED_AT,
    )

    snapshot = load_external_connectivity_case_store(store)

    assert snapshot.supervisor_readiness_attestations == (
        attestation,
    )


def test_r9_wrong_fingerprint_cannot_be_approved(
    tmp_path: Path,
) -> None:
    store = tmp_path / "cases.json"
    _review_ready_case(store)
    case = get_external_connectivity_case(
        "case_r9",
        path=store,
    )
    before = store.read_bytes()

    with pytest.raises(
        ExternalConnectivityIntakeError,
        match="package_fingerprint_conflict",
    ):
        record_external_connectivity_supervisor_decision(
            "case_r9",
            decision=SupervisorReadinessDecision.APPROVED,
            attestation_id="attestation_r9",
            expected_revision=case.revision,
            expected_package_fingerprint="f" * 64,
            actor=ACTOR,
            reason_code="readiness_review_completed",
            occurred_at=DECIDED_AT,
            expires_at=EXPIRES_AT,
            path=store,
        )

    assert store.read_bytes() == before


@pytest.mark.parametrize(
    ("decision", "expected_state"),
    (
        (
            SupervisorReadinessDecision.REMEDIATION_REQUIRED,
            ExternalConnectivityCaseState.NEEDS_REMEDIATION,
        ),
        (
            SupervisorReadinessDecision.REJECTED,
            ExternalConnectivityCaseState.CLOSED,
        ),
    ),
)
def test_r9_nonapproval_decisions_remain_default_deny(
    tmp_path: Path,
    decision: SupervisorReadinessDecision,
    expected_state: ExternalConnectivityCaseState,
) -> None:
    store = tmp_path / f"{decision.value}.json"
    assessment = _review_ready_case(store)
    case = get_external_connectivity_case(
        "case_r9",
        path=store,
    )

    attestation = record_external_connectivity_supervisor_decision(
        "case_r9",
        decision=decision,
        attestation_id=f"attestation_{decision.value}",
        expected_revision=case.revision,
        expected_package_fingerprint=(
            assessment.customer_package_fingerprint
        ),
        actor=ACTOR,
        reason_code=f"supervisor_{decision.value}",
        occurred_at=DECIDED_AT,
        expires_at=EXPIRES_AT,
        path=store,
    )

    decided_case = get_external_connectivity_case(
        "case_r9",
        path=store,
    )

    assert decided_case.state is expected_state
    assert attestation.production_allowed is False
    assert attestation.qualification_key_issuance_allowed is False
    assert attestation.sandbox_activation_allowed is False


def test_r9_resubmission_invalidates_prior_approval(
    tmp_path: Path,
) -> None:
    store = tmp_path / "cases.json"
    assessment = _review_ready_case(store)
    ready_case = get_external_connectivity_case(
        "case_r9",
        path=store,
    )

    attestation = record_external_connectivity_supervisor_decision(
        "case_r9",
        decision=SupervisorReadinessDecision.APPROVED,
        attestation_id="attestation_r9",
        expected_revision=ready_case.revision,
        expected_package_fingerprint=(
            assessment.customer_package_fingerprint
        ),
        actor=ACTOR,
        reason_code="readiness_review_completed",
        occurred_at=DECIDED_AT,
        expires_at=EXPIRES_AT,
        path=store,
    )

    approved_case = get_external_connectivity_case(
        "case_r9",
        path=store,
    )

    resubmitted = submit_external_connectivity_reference_package(
        "case_r9",
        _submission(
            package_id="package_r9_revision_2",
            dns_reference="dns_reference_r9_revision_2",
        ),
        expected_revision=approved_case.revision,
        actor=ACTOR,
        occurred_at="2026-07-14T10:04:00+00:00",
        path=store,
    )

    assert resubmitted.state is (
        ExternalConnectivityCaseState.CUSTOMER_PACKAGE_SUBMITTED
    )
    assert resubmitted.customer_package_fingerprint != (
        attestation.customer_package_fingerprint
    )
    assert resubmitted.readiness_assessment_id == ""

    assert not is_supervisor_readiness_attestation_current(
        attestation,
        resubmitted,
        checked_at="2026-07-14T10:04:00+00:00",
    )


def test_r9_intake_service_has_no_network_or_secret_clients() -> None:
    import processual_api.services.external_connectivity_intake as module

    source = inspect.getsource(module).lower()

    for forbidden in (
        "import requests",
        "import httpx",
        "import socket",
        "import urllib",
        "import boto3",
        "google.cloud",
        "azure.keyvault",
        "hvac",
        "subprocess",
    ):
        assert forbidden not in source
