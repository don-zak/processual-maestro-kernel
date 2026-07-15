from __future__ import annotations

from dataclasses import asdict
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from processual_api.integrations.external_connectivity_cases import (
    CustomerReferencePackage,
    ExternalConnectivityCase,
    ExternalConnectivityCaseState,
    ExternalConnectivityQualificationKeyStatus,
    ExternalConnectivityReadinessAssessment,
    ExternalConnectivitySandboxApiKeyStatus,
    SupervisorReadinessAttestation,
    SupervisorReadinessDecision,
)


class _FrozenForbidModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )


class ExternalConnectivityCaseCreateRequest(_FrozenForbidModel):
    client_id: str = Field(min_length=1, max_length=240)
    readiness_case_id: str = Field(min_length=1, max_length=240)
    connector_id: str = Field(min_length=1, max_length=240)
    credential_profile_id: str = Field(
        min_length=1,
        max_length=240,
    )
    target_environment: Literal["sandbox"] = "sandbox"
    integration_task_id: str = Field(
        default="",
        max_length=240,
    )


class CustomerReferencePackageSubmissionRequest(
    _FrozenForbidModel
):
    package_id: str = Field(min_length=1, max_length=240)
    client_id: str = Field(min_length=1, max_length=240)
    schema_version: str = Field(min_length=1, max_length=240)
    connector_id: str = Field(min_length=1, max_length=240)
    credential_profile_id: str = Field(
        min_length=1,
        max_length=240,
    )
    target_environment: Literal["sandbox"] = "sandbox"
    target_reference_id: str = Field(
        min_length=1,
        max_length=240,
    )
    secret_reference_ids: tuple[str, ...] = ()
    dns_reference: str = Field(min_length=1, max_length=240)
    tls_policy_reference: str = Field(
        min_length=1,
        max_length=240,
    )
    certificate_reference: str = Field(
        min_length=1,
        max_length=240,
    )
    outbound_allowlist_reference: str = Field(
        min_length=1,
        max_length=240,
    )
    submitted_at: str = Field(min_length=1, max_length=80)


class ExternalConnectivityCaseResponse(_FrozenForbidModel):
    case_id: str
    client_id: str
    readiness_case_id: str
    integration_task_id: str
    connector_id: str
    credential_profile_id: str
    target_environment: Literal["sandbox"]
    state: ExternalConnectivityCaseState
    customer_package_fingerprint: str = Field(
        pattern=r"^(?:|[0-9a-f]{64})$"
    )
    readiness_assessment_id: str
    revision: int = Field(ge=1)
    created_at: str
    updated_at: str
    production_allowed: Literal[False] = False
    runtime_connector_allowed: Literal[False] = False
    external_http_allowed: Literal[False] = False
    secret_resolution_allowed: Literal[False] = False
    automatic_activation_allowed: Literal[False] = False
    raw_secret_visible: Literal[False] = False


class ExternalConnectivityReadinessAssessmentResponse(
    _FrozenForbidModel
):
    assessment_id: str
    case_id: str
    customer_package_fingerprint: str = Field(
        pattern=r"^[0-9a-f]{64}$"
    )
    assessment_schema_version: str
    readiness_status: str
    missing_input_codes: tuple[str, ...]
    missing_control_codes: tuple[str, ...]
    blocker_codes: tuple[str, ...]
    remediation_codes: tuple[str, ...]
    evidence_completeness: float = Field(ge=0.0, le=1.0)
    ready_for_supervisor_approval: bool
    assessed_at: str
    network_access_performed: Literal[False] = False
    secrets_read: Literal[False] = False
    provider_sdk_initialized: Literal[False] = False
    certificate_loaded: Literal[False] = False
    sandbox_launched: Literal[False] = False
    production_allowed: Literal[False] = False


class ExternalConnectivityReadinessReviewRequest(
    _FrozenForbidModel
):
    expected_revision: int = Field(ge=1)


class ExternalConnectivitySupervisorDecisionRequest(
    _FrozenForbidModel
):
    expected_revision: int = Field(ge=1)
    expected_package_fingerprint: str = Field(
        pattern=r"^[0-9a-f]{64}$"
    )
    decision: SupervisorReadinessDecision
    reason_code: str = Field(min_length=1, max_length=240)
    expires_at: str = Field(min_length=1, max_length=80)


class SupervisorReadinessAttestationResponse(
    _FrozenForbidModel
):
    attestation_id: str
    case_id: str
    readiness_assessment_id: str
    customer_package_fingerprint: str = Field(
        pattern=r"^[0-9a-f]{64}$"
    )
    decision: SupervisorReadinessDecision
    supervisor_actor: str
    reason_code: str
    issued_at: str
    expires_at: str
    production_allowed: Literal[False] = False
    qualification_key_issuance_allowed: Literal[False] = False
    sandbox_activation_allowed: Literal[False] = False
    external_http_allowed: Literal[False] = False
    secret_resolution_allowed: Literal[False] = False


class ExternalConnectivityReviewResultResponse(
    _FrozenForbidModel
):
    case: ExternalConnectivityCaseResponse
    assessment: ExternalConnectivityReadinessAssessmentResponse


class ExternalConnectivitySupervisorDecisionResultResponse(
    _FrozenForbidModel
):
    case: ExternalConnectivityCaseResponse
    attestation: SupervisorReadinessAttestationResponse


class ExternalConnectivityQualificationKeyIssueRequest(
    _FrozenForbidModel
):
    expected_revision: int = Field(ge=1)
    expires_at: str = Field(min_length=1, max_length=80)


class ExternalConnectivityQualificationRedeemRequest(
    _FrozenForbidModel
):
    qualification_key: str = Field(min_length=1, max_length=512)
    client_id: str = Field(min_length=1, max_length=240)
    redeemed_by: str = Field(min_length=1, max_length=240)
    expected_revision: int = Field(ge=1)


class ExternalConnectivitySandboxApiKeyIssueRequest(
    _FrozenForbidModel
):
    expected_revision: int = Field(ge=1)
    allowed_scope_ids: tuple[str, ...] = Field(
        min_length=1,
        max_length=100,
    )
    expires_at: str = Field(min_length=1, max_length=80)


class ExternalConnectivityKeyMutationRequest(
    _FrozenForbidModel
):
    expected_revision: int = Field(ge=1)


class ExternalConnectivityQualificationKeyResponse(
    _FrozenForbidModel
):
    qualification_key_id: str
    case_id: str
    client_id: str
    attestation_id: str
    readiness_assessment_id: str
    customer_package_fingerprint: str = Field(
        pattern=r"^[0-9a-f]{64}$"
    )
    status: ExternalConnectivityQualificationKeyStatus
    issued_at: str
    expires_at: str
    issued_by: str
    redeemed_at: str
    redeemed_by: str
    revoked_at: str
    revoked_by: str
    production_allowed: Literal[False] = False
    external_http_allowed: Literal[False] = False
    secret_resolution_allowed: Literal[False] = False
    sandbox_activation_allowed: Literal[False] = False
    raw_secret_visible: Literal[False] = False


class ExternalConnectivitySandboxApiKeyResponse(
    _FrozenForbidModel
):
    sandbox_api_key_id: str
    case_id: str
    client_id: str
    qualification_key_id: str
    connector_id: str
    credential_profile_id: str
    target_environment: Literal["sandbox"]
    allowed_scope_ids: tuple[str, ...]
    status: ExternalConnectivitySandboxApiKeyStatus
    issued_at: str
    expires_at: str
    issued_by: str
    suspended_at: str
    suspended_by: str
    revoked_at: str
    revoked_by: str
    runtime_connector_allowed: Literal[False] = False
    production_allowed: Literal[False] = False
    external_http_allowed: Literal[False] = False
    secret_resolution_allowed: Literal[False] = False
    automatic_activation_allowed: Literal[False] = False
    raw_secret_visible: Literal[False] = False


class ExternalConnectivityQualificationKeyIssueResponse(
    _FrozenForbidModel
):
    schema_version: str
    qualification_key_once: str
    raw_qualification_key_visible_once: Literal[True]
    qualification_key: ExternalConnectivityQualificationKeyResponse
    case: ExternalConnectivityCaseResponse
    guardrails: dict[str, bool]


class ExternalConnectivitySandboxApiKeyIssueResponse(
    _FrozenForbidModel
):
    schema_version: str
    sandbox_api_key_once: str
    raw_sandbox_api_key_visible_once: Literal[True]
    sandbox_api_key: ExternalConnectivitySandboxApiKeyResponse
    case: ExternalConnectivityCaseResponse
    guardrails: dict[str, bool]


class ExternalConnectivityKeyMutationResponse(
    _FrozenForbidModel
):
    schema_version: str
    case: ExternalConnectivityCaseResponse
    guardrails: dict[str, bool]
    qualification_key: (
        ExternalConnectivityQualificationKeyResponse | None
    ) = None
    sandbox_api_key: (
        ExternalConnectivitySandboxApiKeyResponse | None
    ) = None


def customer_reference_package_from_submission(
    *,
    case_id: str,
    request: CustomerReferencePackageSubmissionRequest,
) -> CustomerReferencePackage:
    if not case_id.strip():
        raise ValueError("case_id_required")

    return CustomerReferencePackage(
        package_id=request.package_id,
        case_id=case_id,
        client_id=request.client_id,
        schema_version=request.schema_version,
        connector_id=request.connector_id,
        credential_profile_id=request.credential_profile_id,
        target_environment=request.target_environment,
        target_reference_id=request.target_reference_id,
        secret_reference_ids=request.secret_reference_ids,
        dns_reference=request.dns_reference,
        tls_policy_reference=request.tls_policy_reference,
        certificate_reference=request.certificate_reference,
        outbound_allowlist_reference=(
            request.outbound_allowlist_reference
        ),
        submitted_at=request.submitted_at,
    )


def external_connectivity_case_response_from_contract(
    case: ExternalConnectivityCase,
) -> ExternalConnectivityCaseResponse:
    if not isinstance(case, ExternalConnectivityCase):
        raise TypeError("external_connectivity_case_required")

    return ExternalConnectivityCaseResponse.model_validate(
        asdict(case)
    )


def external_connectivity_assessment_response_from_contract(
    assessment: ExternalConnectivityReadinessAssessment,
) -> ExternalConnectivityReadinessAssessmentResponse:
    if not isinstance(
        assessment,
        ExternalConnectivityReadinessAssessment,
    ):
        raise TypeError(
            "external_connectivity_readiness_assessment_required"
        )

    return (
        ExternalConnectivityReadinessAssessmentResponse
        .model_validate(asdict(assessment))
    )


def supervisor_readiness_attestation_response_from_contract(
    attestation: SupervisorReadinessAttestation,
) -> SupervisorReadinessAttestationResponse:
    if not isinstance(
        attestation,
        SupervisorReadinessAttestation,
    ):
        raise TypeError(
            "supervisor_readiness_attestation_required"
        )

    return SupervisorReadinessAttestationResponse.model_validate(
        asdict(attestation)
    )


__all__ = [
    "CustomerReferencePackageSubmissionRequest",
    "ExternalConnectivityCaseCreateRequest",
    "ExternalConnectivityCaseResponse",
    "ExternalConnectivityReadinessAssessmentResponse",
    "ExternalConnectivityReadinessReviewRequest",
    "ExternalConnectivityReviewResultResponse",
    "ExternalConnectivitySupervisorDecisionRequest",
    "ExternalConnectivitySupervisorDecisionResultResponse",
    "SupervisorReadinessAttestationResponse",
    "ExternalConnectivityKeyMutationRequest",
    "ExternalConnectivityKeyMutationResponse",
    "ExternalConnectivityQualificationKeyIssueRequest",
    "ExternalConnectivityQualificationKeyIssueResponse",
    "ExternalConnectivityQualificationKeyResponse",
    "ExternalConnectivityQualificationRedeemRequest",
    "ExternalConnectivitySandboxApiKeyIssueRequest",
    "ExternalConnectivitySandboxApiKeyIssueResponse",
    "ExternalConnectivitySandboxApiKeyResponse",
    "customer_reference_package_from_submission",
    "external_connectivity_assessment_response_from_contract",
    "external_connectivity_case_response_from_contract",
    "supervisor_readiness_attestation_response_from_contract",
]
