from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Final

from processual_api.integrations.connector_bindings import (
    ConnectorEnvironmentBinding,
    get_connector_environment_binding,
    get_connector_secret_reference,
)
from processual_api.integrations.external_connectivity_cases import (
    CustomerReferencePackage,
    ExternalConnectivityCase,
    ExternalConnectivityCaseState,
    ExternalConnectivityReadinessAssessment,
    SupervisorReadinessAttestation,
    SupervisorReadinessDecision,
    advance_external_connectivity_case,
    customer_reference_package_fingerprint,
    is_supervisor_readiness_attestation_current,
)
from processual_api.schemas.external_connectivity import (
    CustomerReferencePackageSubmissionRequest,
    ExternalConnectivityCaseCreateRequest,
    customer_reference_package_from_submission,
)
from processual_api.services.external_connectivity_case_store import (
    ExternalConnectivityCaseStoreSnapshot,
    load_external_connectivity_case_store,
    save_external_connectivity_case_store,
)

EXTERNAL_CONNECTIVITY_INTAKE_SCHEMA_VERSION: Final = (
    "external-connectivity-intake/v1"
)


class ExternalConnectivityIntakeError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require_actor(actor: str) -> str:
    normalized = str(actor).strip()

    if not normalized:
        raise ExternalConnectivityIntakeError(
            "supervisor_actor_required"
        )

    return normalized


def _case_by_id(
    snapshot: ExternalConnectivityCaseStoreSnapshot,
    case_id: str,
) -> ExternalConnectivityCase:
    for case in snapshot.cases:
        if case.case_id == case_id:
            return case

    raise ExternalConnectivityIntakeError(
        "external_connectivity_case_not_found"
    )


def _replace_case(
    snapshot: ExternalConnectivityCaseStoreSnapshot,
    updated_case: ExternalConnectivityCase,
) -> ExternalConnectivityCaseStoreSnapshot:
    return replace(
        snapshot,
        cases=tuple(
            updated_case
            if case.case_id == updated_case.case_id
            else case
            for case in snapshot.cases
        ),
    )


def _require_revision(
    case: ExternalConnectivityCase,
    expected_revision: int,
) -> None:
    if case.revision != expected_revision:
        raise ExternalConnectivityIntakeError(
            "case_revision_conflict"
        )


def _binding_id(
    connector_id: str,
    environment: str,
) -> str:
    return f"{connector_id}_{environment}_binding"


def _binding_for_case(
    case: ExternalConnectivityCase,
) -> ConnectorEnvironmentBinding:
    try:
        return get_connector_environment_binding(
            _binding_id(
                case.connector_id,
                case.target_environment,
            )
        )
    except KeyError as exc:
        raise ExternalConnectivityIntakeError(
            "connector_environment_binding_not_found"
        ) from exc


def _binding_profiles(
    binding: ConnectorEnvironmentBinding,
) -> tuple[str, ...]:
    profiles: list[str] = []

    for reference_id in binding.secret_reference_ids:
        try:
            reference = get_connector_secret_reference(
                reference_id
            )
        except KeyError:
            continue

        profiles.append(reference.credential_profile_id)

    return tuple(profiles)


def _validate_create_binding(
    request: ExternalConnectivityCaseCreateRequest,
) -> None:
    try:
        binding = get_connector_environment_binding(
            _binding_id(
                request.connector_id,
                request.target_environment,
            )
        )
    except KeyError as exc:
        raise ExternalConnectivityIntakeError(
            "connector_environment_binding_not_found"
        ) from exc

    if request.credential_profile_id not in _binding_profiles(
        binding
    ):
        raise ExternalConnectivityIntakeError(
            "credential_profile_binding_mismatch"
        )


def get_external_connectivity_case(
    case_id: str,
    *,
    path: str | Path | None = None,
) -> ExternalConnectivityCase:
    snapshot = load_external_connectivity_case_store(path)
    return _case_by_id(snapshot, case_id)


def list_external_connectivity_cases(
    *,
    path: str | Path | None = None,
) -> tuple[ExternalConnectivityCase, ...]:
    snapshot = load_external_connectivity_case_store(path)
    return snapshot.cases


def create_external_connectivity_case(
    request: ExternalConnectivityCaseCreateRequest,
    *,
    case_id: str,
    actor: str,
    occurred_at: str,
    path: str | Path | None = None,
) -> ExternalConnectivityCase:
    if not isinstance(
        request,
        ExternalConnectivityCaseCreateRequest,
    ):
        raise TypeError(
            "external_connectivity_case_create_request_required"
        )

    _require_actor(actor)
    _validate_create_binding(request)

    snapshot = load_external_connectivity_case_store(path)

    if any(
        existing.case_id == case_id
        for existing in snapshot.cases
    ):
        raise ExternalConnectivityIntakeError(
            "case_already_exists"
        )

    case = ExternalConnectivityCase(
        case_id=case_id,
        client_id=request.client_id,
        readiness_case_id=request.readiness_case_id,
        integration_task_id=request.integration_task_id,
        connector_id=request.connector_id,
        credential_profile_id=(
            request.credential_profile_id
        ),
        target_environment=request.target_environment,
        state=ExternalConnectivityCaseState.DRAFT,
        customer_package_fingerprint="",
        readiness_assessment_id="",
        revision=1,
        created_at=occurred_at,
        updated_at=occurred_at,
    )

    updated = replace(
        snapshot,
        cases=(*snapshot.cases, case),
    )
    save_external_connectivity_case_store(updated, path)
    return case


def _validate_package_identity(
    case: ExternalConnectivityCase,
    package: CustomerReferencePackage,
) -> None:
    if package.client_id != case.client_id:
        raise ExternalConnectivityIntakeError(
            "customer_package_client_mismatch"
        )
    if package.connector_id != case.connector_id:
        raise ExternalConnectivityIntakeError(
            "customer_package_connector_mismatch"
        )
    if (
        package.credential_profile_id
        != case.credential_profile_id
    ):
        raise ExternalConnectivityIntakeError(
            "customer_package_credential_profile_mismatch"
        )
    if package.target_environment != case.target_environment:
        raise ExternalConnectivityIntakeError(
            "customer_package_environment_mismatch"
        )


def submit_external_connectivity_reference_package(
    case_id: str,
    request: CustomerReferencePackageSubmissionRequest,
    *,
    expected_revision: int,
    actor: str,
    occurred_at: str,
    path: str | Path | None = None,
) -> ExternalConnectivityCase:
    if not isinstance(
        request,
        CustomerReferencePackageSubmissionRequest,
    ):
        raise TypeError(
            "customer_reference_package_submission_required"
        )

    _require_actor(actor)
    snapshot = load_external_connectivity_case_store(path)
    case = _case_by_id(snapshot, case_id)
    _require_revision(case, expected_revision)

    allowed_states = {
        ExternalConnectivityCaseState.DRAFT,
        ExternalConnectivityCaseState.NEEDS_REMEDIATION,
        ExternalConnectivityCaseState.READINESS_APPROVED,
    }

    if case.state not in allowed_states:
        raise ExternalConnectivityIntakeError(
            "customer_package_submission_not_allowed"
        )

    if any(
        package.package_id == request.package_id
        for package in snapshot.customer_reference_packages
    ):
        raise ExternalConnectivityIntakeError(
            "customer_package_already_exists"
        )

    package = customer_reference_package_from_submission(
        case_id=case_id,
        request=request,
    )
    _validate_package_identity(case, package)

    fingerprint = customer_reference_package_fingerprint(
        package
    )

    working_case = case

    if (
        working_case.state
        is ExternalConnectivityCaseState.READINESS_APPROVED
    ):
        working_case = advance_external_connectivity_case(
            working_case,
            target_state=(
                ExternalConnectivityCaseState.NEEDS_REMEDIATION
            ),
            updated_at=occurred_at,
            readiness_assessment_id="",
        )

    updated_case = advance_external_connectivity_case(
        working_case,
        target_state=(
            ExternalConnectivityCaseState
            .CUSTOMER_PACKAGE_SUBMITTED
        ),
        updated_at=occurred_at,
        customer_package_fingerprint=fingerprint,
        readiness_assessment_id="",
    )

    updated = _replace_case(snapshot, updated_case)
    updated = replace(
        updated,
        customer_reference_packages=(
            *updated.customer_reference_packages,
            package,
        ),
    )

    save_external_connectivity_case_store(updated, path)
    return updated_case


def _package_for_current_fingerprint(
    snapshot: ExternalConnectivityCaseStoreSnapshot,
    case: ExternalConnectivityCase,
) -> CustomerReferencePackage:
    matches = tuple(
        package
        for package in snapshot.customer_reference_packages
        if (
            package.case_id == case.case_id
            and customer_reference_package_fingerprint(
                package
            )
            == case.customer_package_fingerprint
        )
    )

    if len(matches) != 1:
        raise ExternalConnectivityIntakeError(
            "current_customer_package_not_found"
        )

    return matches[0]


def _evaluate_binding(
    case: ExternalConnectivityCase,
    package: CustomerReferencePackage,
) -> tuple[
    tuple[str, ...],
    tuple[str, ...],
    float,
]:
    blockers: list[str] = []
    remediation: list[str] = []

    try:
        binding = _binding_for_case(case)
    except ExternalConnectivityIntakeError:
        return (
            ("connector_environment_binding_missing",),
            ("select_supported_connector_binding",),
            0.0,
        )

    target_matches = (
        package.target_reference_id
        == binding.target_reference_id
    )

    secret_references_match = (
        package.secret_reference_ids
        == binding.secret_reference_ids
    )

    profile_matches = (
        case.credential_profile_id
        in _binding_profiles(binding)
    )

    if not target_matches:
        blockers.append("target_reference_mismatch")
        remediation.append(
            "provide_declared_target_reference"
        )

    if not secret_references_match:
        blockers.append(
            "binding_secret_reference_mismatch"
        )
        remediation.append(
            "provide_declared_secret_references"
        )

    if not profile_matches:
        blockers.append(
            "credential_profile_binding_mismatch"
        )
        remediation.append(
            "select_declared_credential_profile"
        )

    checks = (
        target_matches,
        secret_references_match,
        profile_matches,
    )

    completeness = sum(
        1 for check in checks if check
    ) / len(checks)

    return (
        tuple(blockers),
        tuple(remediation),
        completeness,
    )


def review_external_connectivity_reference_package(
    case_id: str,
    *,
    assessment_id: str,
    expected_revision: int,
    actor: str,
    occurred_at: str,
    path: str | Path | None = None,
) -> ExternalConnectivityReadinessAssessment:
    _require_actor(actor)
    snapshot = load_external_connectivity_case_store(path)
    case = _case_by_id(snapshot, case_id)
    _require_revision(case, expected_revision)

    if case.state is not (
        ExternalConnectivityCaseState
        .CUSTOMER_PACKAGE_SUBMITTED
    ):
        raise ExternalConnectivityIntakeError(
            "automated_review_not_allowed"
        )

    if any(
        assessment.assessment_id == assessment_id
        for assessment in snapshot.readiness_assessments
    ):
        raise ExternalConnectivityIntakeError(
            "readiness_assessment_already_exists"
        )

    package = _package_for_current_fingerprint(
        snapshot,
        case,
    )

    blockers, remediation, completeness = (
        _evaluate_binding(case, package)
    )

    ready = not blockers

    readiness_status = (
        "ready_for_supervisor_approval"
        if ready
        else "needs_remediation"
    )

    assessment = ExternalConnectivityReadinessAssessment(
        assessment_id=assessment_id,
        case_id=case.case_id,
        customer_package_fingerprint=(
            case.customer_package_fingerprint
        ),
        assessment_schema_version=(
            EXTERNAL_CONNECTIVITY_INTAKE_SCHEMA_VERSION
        ),
        readiness_status=readiness_status,
        missing_input_codes=(),
        missing_control_codes=(),
        blocker_codes=blockers,
        remediation_codes=remediation,
        evidence_completeness=completeness,
        ready_for_supervisor_approval=ready,
        assessed_at=occurred_at,
    )

    under_review = advance_external_connectivity_case(
        case,
        target_state=(
            ExternalConnectivityCaseState
            .UNDER_AUTOMATED_REVIEW
        ),
        updated_at=occurred_at,
    )

    target_state = (
        ExternalConnectivityCaseState
        .READY_FOR_SUPERVISOR_APPROVAL
        if ready
        else ExternalConnectivityCaseState.NEEDS_REMEDIATION
    )

    reviewed_case = advance_external_connectivity_case(
        under_review,
        target_state=target_state,
        updated_at=occurred_at,
        readiness_assessment_id=assessment.assessment_id,
    )

    updated = _replace_case(snapshot, reviewed_case)
    updated = replace(
        updated,
        readiness_assessments=(
            *updated.readiness_assessments,
            assessment,
        ),
    )

    save_external_connectivity_case_store(updated, path)
    return assessment


def _current_assessment(
    snapshot: ExternalConnectivityCaseStoreSnapshot,
    case: ExternalConnectivityCase,
) -> ExternalConnectivityReadinessAssessment:
    for assessment in snapshot.readiness_assessments:
        if (
            assessment.assessment_id
            == case.readiness_assessment_id
        ):
            return assessment

    raise ExternalConnectivityIntakeError(
        "current_readiness_assessment_not_found"
    )


def record_external_connectivity_supervisor_decision(
    case_id: str,
    *,
    decision: SupervisorReadinessDecision,
    attestation_id: str,
    expected_revision: int,
    expected_package_fingerprint: str,
    actor: str,
    reason_code: str,
    occurred_at: str,
    expires_at: str,
    path: str | Path | None = None,
) -> SupervisorReadinessAttestation:
    _require_actor(actor)

    if not isinstance(
        decision,
        SupervisorReadinessDecision,
    ):
        raise ExternalConnectivityIntakeError(
            "supervisor_readiness_decision_invalid"
        )

    snapshot = load_external_connectivity_case_store(path)
    case = _case_by_id(snapshot, case_id)
    _require_revision(case, expected_revision)

    if case.state is not (
        ExternalConnectivityCaseState
        .READY_FOR_SUPERVISOR_APPROVAL
    ):
        raise ExternalConnectivityIntakeError(
            "supervisor_decision_not_allowed"
        )

    if (
        case.customer_package_fingerprint
        != expected_package_fingerprint
    ):
        raise ExternalConnectivityIntakeError(
            "package_fingerprint_conflict"
        )

    assessment = _current_assessment(snapshot, case)

    if (
        assessment.customer_package_fingerprint
        != expected_package_fingerprint
        or not assessment.ready_for_supervisor_approval
    ):
        raise ExternalConnectivityIntakeError(
            "readiness_assessment_not_approvable"
        )

    if any(
        existing.attestation_id == attestation_id
        for existing in (
            snapshot.supervisor_readiness_attestations
        )
    ):
        raise ExternalConnectivityIntakeError(
            "supervisor_attestation_already_exists"
        )

    attestation = SupervisorReadinessAttestation(
        attestation_id=attestation_id,
        case_id=case.case_id,
        readiness_assessment_id=assessment.assessment_id,
        customer_package_fingerprint=(
            expected_package_fingerprint
        ),
        decision=decision,
        supervisor_actor=actor,
        reason_code=reason_code,
        issued_at=occurred_at,
        expires_at=expires_at,
    )

    target_states = {
        SupervisorReadinessDecision.APPROVED: (
            ExternalConnectivityCaseState.READINESS_APPROVED
        ),
        SupervisorReadinessDecision.REMEDIATION_REQUIRED: (
            ExternalConnectivityCaseState.NEEDS_REMEDIATION
        ),
        SupervisorReadinessDecision.REJECTED: (
            ExternalConnectivityCaseState.CLOSED
        ),
    }

    decided_case = advance_external_connectivity_case(
        case,
        target_state=target_states[decision],
        updated_at=occurred_at,
    )

    updated = _replace_case(snapshot, decided_case)
    updated = replace(
        updated,
        supervisor_readiness_attestations=(
            *updated.supervisor_readiness_attestations,
            attestation,
        ),
    )

    save_external_connectivity_case_store(updated, path)
    return attestation


__all__ = [
    "EXTERNAL_CONNECTIVITY_INTAKE_SCHEMA_VERSION",
    "ExternalConnectivityIntakeError",
    "SupervisorReadinessDecision",
    "create_external_connectivity_case",
    "get_external_connectivity_case",
    "is_supervisor_readiness_attestation_current",
    "list_external_connectivity_cases",
    "record_external_connectivity_supervisor_decision",
    "review_external_connectivity_reference_package",
    "submit_external_connectivity_reference_package",
]
