from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Final

EXTERNAL_CONNECTIVITY_CASE_SCHEMA_VERSION: Final = (
    "external-connectivity-case/v1"
)

_SHA256_PATTERN: Final = re.compile(r"^[0-9a-f]{64}$")
_SAFE_IDENTIFIER_PATTERN: Final = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,239}$"
)


class ExternalConnectivityCaseState(StrEnum):
    DRAFT = "draft"
    CUSTOMER_PACKAGE_SUBMITTED = "customer_package_submitted"
    UNDER_AUTOMATED_REVIEW = "under_automated_review"
    NEEDS_REMEDIATION = "needs_remediation"
    READY_FOR_SUPERVISOR_APPROVAL = "ready_for_supervisor_approval"
    READINESS_APPROVED = "readiness_approved"
    QUALIFICATION_KEY_ISSUED = "qualification_key_issued"
    QUALIFICATION_REDEEMED = "qualification_redeemed"
    SANDBOX_API_KEY_ISSUED = "sandbox_api_key_issued"
    SANDBOX_AUTHORIZED = "sandbox_authorized"
    SANDBOX_SUSPENDED = "sandbox_suspended"
    SANDBOX_REVOKED = "sandbox_revoked"
    CLOSED = "closed"


class ExternalConnectivityAuditEventType(StrEnum):
    CASE_CREATED = "case_created"
    CUSTOMER_PACKAGE_SUBMITTED = "customer_package_submitted"
    AUTOMATED_REVIEW_STARTED = "automated_review_started"
    REMEDIATION_REQUIRED = "remediation_required"
    READY_FOR_SUPERVISOR_APPROVAL = "ready_for_supervisor_approval"
    READINESS_APPROVED = "readiness_approved"
    QUALIFICATION_KEY_ISSUED = "qualification_key_issued"
    QUALIFICATION_REDEEMED = "qualification_redeemed"
    SANDBOX_API_KEY_ISSUED = "sandbox_api_key_issued"
    SANDBOX_AUTHORIZED = "sandbox_authorized"
    SANDBOX_SUSPENDED = "sandbox_suspended"
    SANDBOX_REVOKED = "sandbox_revoked"
    CASE_CLOSED = "case_closed"
    TRANSITION_REJECTED = "transition_rejected"
    PROHIBITED_FIELD_REJECTED = "prohibited_field_rejected"


class SupervisorReadinessDecision(StrEnum):
    APPROVED = "approved"
    REMEDIATION_REQUIRED = "remediation_required"
    REJECTED = "rejected"


PROHIBITED_CUSTOMER_FIELD_NAMES: Final[frozenset[str]] = frozenset(
    {
        "password",
        "secret",
        "secret_value",
        "raw_secret",
        "raw_key",
        "api_key",
        "access_token",
        "refresh_token",
        "client_secret",
        "private_key",
        "certificate_pem",
        "authorization",
        "cookie",
    }
)


ALLOWED_EXTERNAL_CONNECTIVITY_TRANSITIONS: Final[
    Mapping[
        ExternalConnectivityCaseState,
        frozenset[ExternalConnectivityCaseState],
    ]
] = MappingProxyType(
    {
        ExternalConnectivityCaseState.DRAFT: frozenset(
            {
                ExternalConnectivityCaseState.CUSTOMER_PACKAGE_SUBMITTED,
                ExternalConnectivityCaseState.CLOSED,
            }
        ),
        ExternalConnectivityCaseState.CUSTOMER_PACKAGE_SUBMITTED: frozenset(
            {
                ExternalConnectivityCaseState.UNDER_AUTOMATED_REVIEW,
                ExternalConnectivityCaseState.CLOSED,
            }
        ),
        ExternalConnectivityCaseState.UNDER_AUTOMATED_REVIEW: frozenset(
            {
                ExternalConnectivityCaseState.NEEDS_REMEDIATION,
                ExternalConnectivityCaseState.READY_FOR_SUPERVISOR_APPROVAL,
                ExternalConnectivityCaseState.CLOSED,
            }
        ),
        ExternalConnectivityCaseState.NEEDS_REMEDIATION: frozenset(
            {
                ExternalConnectivityCaseState.CUSTOMER_PACKAGE_SUBMITTED,
                ExternalConnectivityCaseState.CLOSED,
            }
        ),
        ExternalConnectivityCaseState.READY_FOR_SUPERVISOR_APPROVAL: frozenset(
            {
                ExternalConnectivityCaseState.READINESS_APPROVED,
                ExternalConnectivityCaseState.NEEDS_REMEDIATION,
                ExternalConnectivityCaseState.CLOSED,
            }
        ),
        ExternalConnectivityCaseState.READINESS_APPROVED: frozenset(
            {
                ExternalConnectivityCaseState.QUALIFICATION_KEY_ISSUED,
                ExternalConnectivityCaseState.NEEDS_REMEDIATION,
                ExternalConnectivityCaseState.CLOSED,
            }
        ),
        ExternalConnectivityCaseState.QUALIFICATION_KEY_ISSUED: frozenset(
            {
                ExternalConnectivityCaseState.QUALIFICATION_REDEEMED,
                ExternalConnectivityCaseState.SANDBOX_REVOKED,
                ExternalConnectivityCaseState.CLOSED,
            }
        ),
        ExternalConnectivityCaseState.QUALIFICATION_REDEEMED: frozenset(
            {
                ExternalConnectivityCaseState.SANDBOX_API_KEY_ISSUED,
                ExternalConnectivityCaseState.SANDBOX_REVOKED,
                ExternalConnectivityCaseState.CLOSED,
            }
        ),
        ExternalConnectivityCaseState.SANDBOX_API_KEY_ISSUED: frozenset(
            {
                ExternalConnectivityCaseState.SANDBOX_AUTHORIZED,
                ExternalConnectivityCaseState.SANDBOX_REVOKED,
                ExternalConnectivityCaseState.CLOSED,
            }
        ),
        ExternalConnectivityCaseState.SANDBOX_AUTHORIZED: frozenset(
            {
                ExternalConnectivityCaseState.SANDBOX_SUSPENDED,
                ExternalConnectivityCaseState.SANDBOX_REVOKED,
                ExternalConnectivityCaseState.CLOSED,
            }
        ),
        ExternalConnectivityCaseState.SANDBOX_SUSPENDED: frozenset(
            {
                ExternalConnectivityCaseState.SANDBOX_AUTHORIZED,
                ExternalConnectivityCaseState.SANDBOX_REVOKED,
                ExternalConnectivityCaseState.CLOSED,
            }
        ),
        ExternalConnectivityCaseState.SANDBOX_REVOKED: frozenset(
            {
                ExternalConnectivityCaseState.CLOSED,
            }
        ),
        ExternalConnectivityCaseState.CLOSED: frozenset(),
    }
)


def _require_text(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name}_required")


def _require_identifier(field_name: str, value: str) -> None:
    _require_text(field_name, value)
    if _SAFE_IDENTIFIER_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field_name}_invalid")


def _require_reference(field_name: str, value: str) -> None:
    _require_identifier(field_name, value)


def _require_sha256_or_empty(field_name: str, value: str) -> None:
    if value == "":
        return
    if _SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field_name}_must_be_sha256")


def _require_default_deny(field_name: str, value: bool) -> None:
    if value is not False:
        raise ValueError(f"{field_name}_must_be_false")


def _require_aware_datetime(
    field_name: str,
    value: str,
) -> datetime:
    _require_text(field_name, value)

    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            f"{field_name}_must_be_iso_datetime"
        ) from exc

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(
            f"{field_name}_must_be_timezone_aware"
        )

    return parsed


def _normalize_customer_field_name(value: object) -> str:
    text = str(value).strip().lower()
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def _walk_prohibited_customer_fields(
    value: object,
    *,
    path: str,
    matches: list[str],
) -> None:
    if isinstance(value, Mapping):
        for raw_key, child in value.items():
            key = str(raw_key)
            normalized_key = _normalize_customer_field_name(key)
            child_path = f"{path}.{key}" if path else key

            if normalized_key in PROHIBITED_CUSTOMER_FIELD_NAMES:
                matches.append(child_path)

            _walk_prohibited_customer_fields(
                child,
                path=child_path,
                matches=matches,
            )
        return

    if isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            child_path = f"{path}[{index}]"
            _walk_prohibited_customer_fields(
                child,
                path=child_path,
                matches=matches,
            )


def find_prohibited_customer_fields(value: object) -> tuple[str, ...]:
    matches: list[str] = []
    _walk_prohibited_customer_fields(
        value,
        path="",
        matches=matches,
    )
    return tuple(sorted(set(matches)))


@dataclass(frozen=True, slots=True)
class CustomerReferencePackage:
    package_id: str
    case_id: str
    client_id: str
    schema_version: str
    connector_id: str
    credential_profile_id: str
    target_environment: str
    target_reference_id: str
    secret_reference_ids: tuple[str, ...]
    dns_reference: str
    tls_policy_reference: str
    certificate_reference: str
    outbound_allowlist_reference: str
    submitted_at: str

    def __post_init__(self) -> None:
        _require_identifier("package_id", self.package_id)
        _require_identifier("case_id", self.case_id)
        _require_identifier("client_id", self.client_id)
        _require_text("schema_version", self.schema_version)
        _require_identifier("connector_id", self.connector_id)
        _require_identifier(
            "credential_profile_id",
            self.credential_profile_id,
        )

        if self.target_environment != "sandbox":
            raise ValueError("target_environment_must_be_sandbox")

        _require_reference(
            "target_reference_id",
            self.target_reference_id,
        )
        _require_reference("dns_reference", self.dns_reference)
        _require_reference(
            "tls_policy_reference",
            self.tls_policy_reference,
        )
        _require_reference(
            "certificate_reference",
            self.certificate_reference,
        )
        _require_reference(
            "outbound_allowlist_reference",
            self.outbound_allowlist_reference,
        )
        _require_text("submitted_at", self.submitted_at)

        if not isinstance(self.secret_reference_ids, tuple):
            raise ValueError("secret_reference_ids_must_be_tuple")

        if len(set(self.secret_reference_ids)) != len(
            self.secret_reference_ids
        ):
            raise ValueError("secret_reference_ids_must_be_unique")

        for secret_reference_id in self.secret_reference_ids:
            _require_reference(
                "secret_reference_id",
                secret_reference_id,
            )

        prohibited = find_prohibited_customer_fields(asdict(self))
        if prohibited:
            raise ValueError("prohibited_customer_fields_present")


@dataclass(frozen=True, slots=True)
class ExternalConnectivityReadinessAssessment:
    assessment_id: str
    case_id: str
    customer_package_fingerprint: str
    assessment_schema_version: str
    readiness_status: str
    missing_input_codes: tuple[str, ...]
    missing_control_codes: tuple[str, ...]
    blocker_codes: tuple[str, ...]
    remediation_codes: tuple[str, ...]
    evidence_completeness: float
    ready_for_supervisor_approval: bool
    assessed_at: str
    network_access_performed: bool = False
    secrets_read: bool = False
    provider_sdk_initialized: bool = False
    certificate_loaded: bool = False
    sandbox_launched: bool = False
    production_allowed: bool = False

    def __post_init__(self) -> None:
        _require_identifier("assessment_id", self.assessment_id)
        _require_identifier("case_id", self.case_id)
        _require_sha256_or_empty(
            "customer_package_fingerprint",
            self.customer_package_fingerprint,
        )
        _require_text(
            "assessment_schema_version",
            self.assessment_schema_version,
        )
        _require_identifier(
            "readiness_status",
            self.readiness_status,
        )
        _require_text("assessed_at", self.assessed_at)

        if not math.isfinite(self.evidence_completeness):
            raise ValueError("evidence_completeness_must_be_finite")
        if not 0.0 <= self.evidence_completeness <= 1.0:
            raise ValueError("evidence_completeness_out_of_range")

        tuple_fields = (
            ("missing_input_codes", self.missing_input_codes),
            ("missing_control_codes", self.missing_control_codes),
            ("blocker_codes", self.blocker_codes),
            ("remediation_codes", self.remediation_codes),
        )

        for field_name, values in tuple_fields:
            if not isinstance(values, tuple):
                raise ValueError(f"{field_name}_must_be_tuple")
            if len(set(values)) != len(values):
                raise ValueError(f"{field_name}_must_be_unique")
            for value in values:
                _require_identifier(field_name, value)

        _require_default_deny(
            "network_access_performed",
            self.network_access_performed,
        )
        _require_default_deny("secrets_read", self.secrets_read)
        _require_default_deny(
            "provider_sdk_initialized",
            self.provider_sdk_initialized,
        )
        _require_default_deny(
            "certificate_loaded",
            self.certificate_loaded,
        )
        _require_default_deny(
            "sandbox_launched",
            self.sandbox_launched,
        )
        _require_default_deny(
            "production_allowed",
            self.production_allowed,
        )


@dataclass(frozen=True, slots=True)
class ExternalConnectivityCase:
    case_id: str
    client_id: str
    readiness_case_id: str
    integration_task_id: str
    connector_id: str
    credential_profile_id: str
    target_environment: str
    state: ExternalConnectivityCaseState
    customer_package_fingerprint: str
    readiness_assessment_id: str
    revision: int
    created_at: str
    updated_at: str
    production_allowed: bool = False
    runtime_connector_allowed: bool = False
    external_http_allowed: bool = False
    secret_resolution_allowed: bool = False
    automatic_activation_allowed: bool = False
    raw_secret_visible: bool = False

    def __post_init__(self) -> None:
        _require_identifier("case_id", self.case_id)
        _require_identifier("client_id", self.client_id)
        _require_identifier(
            "readiness_case_id",
            self.readiness_case_id,
        )

        if self.integration_task_id:
            _require_identifier(
                "integration_task_id",
                self.integration_task_id,
            )

        _require_identifier("connector_id", self.connector_id)
        _require_identifier(
            "credential_profile_id",
            self.credential_profile_id,
        )

        if self.target_environment != "sandbox":
            raise ValueError("target_environment_must_be_sandbox")

        if not isinstance(self.state, ExternalConnectivityCaseState):
            raise ValueError("external_connectivity_case_state_invalid")

        _require_sha256_or_empty(
            "customer_package_fingerprint",
            self.customer_package_fingerprint,
        )

        if self.readiness_assessment_id:
            _require_identifier(
                "readiness_assessment_id",
                self.readiness_assessment_id,
            )

        if not isinstance(self.revision, int) or self.revision < 1:
            raise ValueError("revision_must_be_positive")

        _require_text("created_at", self.created_at)
        _require_text("updated_at", self.updated_at)

        default_deny_fields = (
            ("production_allowed", self.production_allowed),
            (
                "runtime_connector_allowed",
                self.runtime_connector_allowed,
            ),
            ("external_http_allowed", self.external_http_allowed),
            (
                "secret_resolution_allowed",
                self.secret_resolution_allowed,
            ),
            (
                "automatic_activation_allowed",
                self.automatic_activation_allowed,
            ),
            ("raw_secret_visible", self.raw_secret_visible),
        )

        for field_name, value in default_deny_fields:
            _require_default_deny(field_name, value)


@dataclass(frozen=True, slots=True)
class SupervisorReadinessAttestation:
    attestation_id: str
    case_id: str
    readiness_assessment_id: str
    customer_package_fingerprint: str
    decision: SupervisorReadinessDecision
    supervisor_actor: str
    reason_code: str
    issued_at: str
    expires_at: str
    production_allowed: bool = False
    qualification_key_issuance_allowed: bool = False
    sandbox_activation_allowed: bool = False
    external_http_allowed: bool = False
    secret_resolution_allowed: bool = False

    def __post_init__(self) -> None:
        _require_identifier(
            "attestation_id",
            self.attestation_id,
        )
        _require_identifier("case_id", self.case_id)
        _require_identifier(
            "readiness_assessment_id",
            self.readiness_assessment_id,
        )
        _require_sha256_or_empty(
            "customer_package_fingerprint",
            self.customer_package_fingerprint,
        )

        if not self.customer_package_fingerprint:
            raise ValueError(
                "customer_package_fingerprint_required"
            )

        if not isinstance(
            self.decision,
            SupervisorReadinessDecision,
        ):
            raise ValueError(
                "supervisor_readiness_decision_invalid"
            )

        _require_identifier(
            "supervisor_actor",
            self.supervisor_actor,
        )
        _require_identifier(
            "reason_code",
            self.reason_code,
        )

        issued = _require_aware_datetime(
            "issued_at",
            self.issued_at,
        )
        expires = _require_aware_datetime(
            "expires_at",
            self.expires_at,
        )

        if expires <= issued:
            raise ValueError(
                "expires_at_must_follow_issued_at"
            )

        default_deny_fields = (
            ("production_allowed", self.production_allowed),
            (
                "qualification_key_issuance_allowed",
                self.qualification_key_issuance_allowed,
            ),
            (
                "sandbox_activation_allowed",
                self.sandbox_activation_allowed,
            ),
            (
                "external_http_allowed",
                self.external_http_allowed,
            ),
            (
                "secret_resolution_allowed",
                self.secret_resolution_allowed,
            ),
        )

        for field_name, value in default_deny_fields:
            _require_default_deny(field_name, value)


def is_supervisor_readiness_attestation_current(
    attestation: SupervisorReadinessAttestation,
    case: ExternalConnectivityCase,
    *,
    checked_at: str,
) -> bool:
    if not isinstance(
        attestation,
        SupervisorReadinessAttestation,
    ):
        raise TypeError(
            "supervisor_readiness_attestation_required"
        )

    if not isinstance(case, ExternalConnectivityCase):
        raise TypeError("external_connectivity_case_required")

    checked = _require_aware_datetime(
        "checked_at",
        checked_at,
    )
    issued = _require_aware_datetime(
        "issued_at",
        attestation.issued_at,
    )
    expires = _require_aware_datetime(
        "expires_at",
        attestation.expires_at,
    )

    return (
        attestation.decision
        is SupervisorReadinessDecision.APPROVED
        and case.state
        is ExternalConnectivityCaseState.READINESS_APPROVED
        and attestation.case_id == case.case_id
        and (
            attestation.readiness_assessment_id
            == case.readiness_assessment_id
        )
        and (
            attestation.customer_package_fingerprint
            == case.customer_package_fingerprint
        )
        and issued <= checked < expires
    )


def _customer_reference_package_payload(
    package: CustomerReferencePackage,
) -> dict[str, Any]:
    return {
        "package_id": package.package_id,
        "case_id": package.case_id,
        "client_id": package.client_id,
        "schema_version": package.schema_version,
        "connector_id": package.connector_id,
        "credential_profile_id": package.credential_profile_id,
        "target_environment": package.target_environment,
        "target_reference_id": package.target_reference_id,
        "secret_reference_ids": sorted(package.secret_reference_ids),
        "dns_reference": package.dns_reference,
        "tls_policy_reference": package.tls_policy_reference,
        "certificate_reference": package.certificate_reference,
        "outbound_allowlist_reference": (
            package.outbound_allowlist_reference
        ),
        "submitted_at": package.submitted_at,
    }


def customer_reference_package_fingerprint(
    package: CustomerReferencePackage,
) -> str:
    if not isinstance(package, CustomerReferencePackage):
        raise TypeError("customer_reference_package_required")

    payload = _customer_reference_package_payload(package)
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()


def is_external_connectivity_transition_allowed(
    current_state: ExternalConnectivityCaseState,
    target_state: ExternalConnectivityCaseState,
) -> bool:
    try:
        normalized_current = ExternalConnectivityCaseState(current_state)
        normalized_target = ExternalConnectivityCaseState(target_state)
    except (TypeError, ValueError):
        return False

    return normalized_target in ALLOWED_EXTERNAL_CONNECTIVITY_TRANSITIONS[
        normalized_current
    ]


def advance_external_connectivity_case(
    case: ExternalConnectivityCase,
    *,
    target_state: ExternalConnectivityCaseState,
    updated_at: str,
    customer_package_fingerprint: str | None = None,
    readiness_assessment_id: str | None = None,
    integration_task_id: str | None = None,
) -> ExternalConnectivityCase:
    if not isinstance(case, ExternalConnectivityCase):
        raise TypeError("external_connectivity_case_required")

    try:
        normalized_target = ExternalConnectivityCaseState(target_state)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "external_connectivity_transition_not_allowed"
        ) from exc

    if not is_external_connectivity_transition_allowed(
        case.state,
        normalized_target,
    ):
        raise ValueError(
            "external_connectivity_transition_not_allowed"
        )

    changes: dict[str, Any] = {
        "state": normalized_target,
        "updated_at": updated_at,
        "revision": case.revision + 1,
    }

    if customer_package_fingerprint is not None:
        changes["customer_package_fingerprint"] = (
            customer_package_fingerprint
        )

    if readiness_assessment_id is not None:
        changes["readiness_assessment_id"] = readiness_assessment_id

    if integration_task_id is not None:
        changes["integration_task_id"] = integration_task_id

    return replace(case, **changes)


__all__ = [
    "ALLOWED_EXTERNAL_CONNECTIVITY_TRANSITIONS",
    "EXTERNAL_CONNECTIVITY_CASE_SCHEMA_VERSION",
    "PROHIBITED_CUSTOMER_FIELD_NAMES",
    "CustomerReferencePackage",
    "ExternalConnectivityAuditEventType",
    "ExternalConnectivityCase",
    "ExternalConnectivityCaseState",
    "ExternalConnectivityReadinessAssessment",
    "advance_external_connectivity_case",
    "customer_reference_package_fingerprint",
    "find_prohibited_customer_fields",
    "is_external_connectivity_transition_allowed",
    "is_supervisor_readiness_attestation_current",
    "SupervisorReadinessAttestation",
    "SupervisorReadinessDecision",
]
