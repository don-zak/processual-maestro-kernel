from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Final

from processual_api.integrations.external_connectivity_cases import (
    CustomerReferencePackage,
    ExternalConnectivityCase,
    ExternalConnectivityCaseState,
    ExternalConnectivityQualificationKey,
    ExternalConnectivityQualificationKeyStatus,
    ExternalConnectivityReadinessAssessment,
    ExternalConnectivitySandboxApiKey,
    ExternalConnectivitySandboxApiKeyStatus,
    SupervisorReadinessAttestation,
    SupervisorReadinessDecision,
    customer_reference_package_fingerprint,
)

EXTERNAL_CONNECTIVITY_CASE_STORE_SCHEMA_VERSION: Final = (
    "external-connectivity-case-store/v1"
)

DEFAULT_EXTERNAL_CONNECTIVITY_CASE_STORE_PATH: Final = Path(
    "data/external_connectivity_cases.json"
)

_STORE_ENVIRONMENT_VARIABLE: Final = (
    "PMK_EXTERNAL_CONNECTIVITY_CASES_PATH"
)


@dataclass(frozen=True, slots=True)
class ExternalConnectivityCaseStoreSnapshot:
    cases: tuple[ExternalConnectivityCase, ...] = ()
    customer_reference_packages: tuple[
        CustomerReferencePackage, ...
    ] = ()
    readiness_assessments: tuple[
        ExternalConnectivityReadinessAssessment, ...
    ] = ()
    supervisor_readiness_attestations: tuple[
        SupervisorReadinessAttestation, ...
    ] = ()
    qualification_keys: tuple[
        ExternalConnectivityQualificationKey, ...
    ] = ()
    sandbox_api_keys: tuple[
        ExternalConnectivitySandboxApiKey, ...
    ] = ()
    schema_version: str = (
        EXTERNAL_CONNECTIVITY_CASE_STORE_SCHEMA_VERSION
    )

    def __post_init__(self) -> None:
        if not isinstance(self.cases, tuple):
            raise ValueError("store_cases_must_be_tuple")
        if not isinstance(self.customer_reference_packages, tuple):
            raise ValueError(
                "store_customer_reference_packages_must_be_tuple"
            )
        if not isinstance(self.readiness_assessments, tuple):
            raise ValueError(
                "store_readiness_assessments_must_be_tuple"
            )
        if not isinstance(
            self.supervisor_readiness_attestations,
            tuple,
        ):
            raise ValueError(
                "store_supervisor_attestations_must_be_tuple"
            )
        if not isinstance(self.qualification_keys, tuple):
            raise ValueError(
                "store_qualification_keys_must_be_tuple"
            )
        if not isinstance(self.sandbox_api_keys, tuple):
            raise ValueError(
                "store_sandbox_api_keys_must_be_tuple"
            )
        if (
            self.schema_version
            != EXTERNAL_CONNECTIVITY_CASE_STORE_SCHEMA_VERSION
        ):
            raise ValueError("store_schema_version_invalid")


def external_connectivity_case_store_path(
    path: str | Path | None = None,
) -> Path:
    if path is not None:
        return Path(path)

    configured = os.environ.get(
        _STORE_ENVIRONMENT_VARIABLE,
        "",
    ).strip()

    if configured:
        return Path(configured)

    return DEFAULT_EXTERNAL_CONNECTIVITY_CASE_STORE_PATH


def _duplicate_identifier(
    values: tuple[object, ...],
    *,
    attribute: str,
) -> str:
    seen: set[str] = set()

    for value in values:
        identifier = str(getattr(value, attribute))

        if identifier in seen:
            return identifier

        seen.add(identifier)

    return ""


def _validate_snapshot(
    snapshot: ExternalConnectivityCaseStoreSnapshot,
) -> None:
    if not isinstance(
        snapshot,
        ExternalConnectivityCaseStoreSnapshot,
    ):
        raise TypeError(
            "external_connectivity_case_store_snapshot_required"
        )

    if (
        snapshot.schema_version
        != EXTERNAL_CONNECTIVITY_CASE_STORE_SCHEMA_VERSION
    ):
        raise ValueError("store_schema_version_invalid")

    for case in snapshot.cases:
        if not isinstance(case, ExternalConnectivityCase):
            raise ValueError("store_case_record_invalid")

    for package in snapshot.customer_reference_packages:
        if not isinstance(package, CustomerReferencePackage):
            raise ValueError("store_customer_package_record_invalid")

    for assessment in snapshot.readiness_assessments:
        if not isinstance(
            assessment,
            ExternalConnectivityReadinessAssessment,
        ):
            raise ValueError("store_assessment_record_invalid")

    for attestation in (
        snapshot.supervisor_readiness_attestations
    ):
        if not isinstance(
            attestation,
            SupervisorReadinessAttestation,
        ):
            raise ValueError(
                "store_supervisor_attestation_record_invalid"
            )

    for qualification_key in snapshot.qualification_keys:
        if not isinstance(
            qualification_key,
            ExternalConnectivityQualificationKey,
        ):
            raise ValueError(
                "store_qualification_key_record_invalid"
            )

    for sandbox_api_key in snapshot.sandbox_api_keys:
        if not isinstance(
            sandbox_api_key,
            ExternalConnectivitySandboxApiKey,
        ):
            raise ValueError(
                "store_sandbox_api_key_record_invalid"
            )

    duplicate_case_id = _duplicate_identifier(
        snapshot.cases,
        attribute="case_id",
    )
    if duplicate_case_id:
        raise ValueError(f"duplicate_case_id:{duplicate_case_id}")

    duplicate_package_id = _duplicate_identifier(
        snapshot.customer_reference_packages,
        attribute="package_id",
    )
    if duplicate_package_id:
        raise ValueError(
            f"duplicate_package_id:{duplicate_package_id}"
        )

    duplicate_assessment_id = _duplicate_identifier(
        snapshot.readiness_assessments,
        attribute="assessment_id",
    )
    if duplicate_assessment_id:
        raise ValueError(
            f"duplicate_assessment_id:{duplicate_assessment_id}"
        )

    duplicate_attestation_id = _duplicate_identifier(
        snapshot.supervisor_readiness_attestations,
        attribute="attestation_id",
    )
    if duplicate_attestation_id:
        raise ValueError(
            f"duplicate_attestation_id:{duplicate_attestation_id}"
        )

    duplicate_qualification_key_id = _duplicate_identifier(
        snapshot.qualification_keys,
        attribute="qualification_key_id",
    )
    if duplicate_qualification_key_id:
        raise ValueError(
            "duplicate_qualification_key_id:"
            f"{duplicate_qualification_key_id}"
        )

    duplicate_sandbox_api_key_id = _duplicate_identifier(
        snapshot.sandbox_api_keys,
        attribute="sandbox_api_key_id",
    )
    if duplicate_sandbox_api_key_id:
        raise ValueError(
            "duplicate_sandbox_api_key_id:"
            f"{duplicate_sandbox_api_key_id}"
        )

    cases_by_id = {
        case.case_id: case
        for case in snapshot.cases
    }

    package_fingerprints_by_case: dict[
        str,
        set[str],
    ] = {}

    for package in snapshot.customer_reference_packages:
        case = cases_by_id.get(package.case_id)

        if case is None:
            raise ValueError(
                f"customer_package_case_missing:{package.case_id}"
            )

        if package.client_id != case.client_id:
            raise ValueError(
                "customer_package_client_mismatch"
            )
        if package.connector_id != case.connector_id:
            raise ValueError(
                "customer_package_connector_mismatch"
            )
        if (
            package.credential_profile_id
            != case.credential_profile_id
        ):
            raise ValueError(
                "customer_package_credential_profile_mismatch"
            )
        if package.target_environment != case.target_environment:
            raise ValueError(
                "customer_package_environment_mismatch"
            )

        fingerprint = customer_reference_package_fingerprint(
            package
        )

        package_fingerprints_by_case.setdefault(
            package.case_id,
            set(),
        ).add(fingerprint)

    assessments_by_id = {
        assessment.assessment_id: assessment
        for assessment in snapshot.readiness_assessments
    }

    for assessment in snapshot.readiness_assessments:
        case = cases_by_id.get(assessment.case_id)

        if case is None:
            raise ValueError(
                f"assessment_case_missing:{assessment.case_id}"
            )

        known_fingerprints = package_fingerprints_by_case.get(
            assessment.case_id,
            set(),
        )

        if (
            assessment.customer_package_fingerprint
            not in known_fingerprints
        ):
            raise ValueError(
                "assessment_package_fingerprint_mismatch"
            )

    for attestation in (
        snapshot.supervisor_readiness_attestations
    ):
        case = cases_by_id.get(attestation.case_id)

        if case is None:
            raise ValueError(
                f"attestation_case_missing:{attestation.case_id}"
            )

        assessment = assessments_by_id.get(
            attestation.readiness_assessment_id
        )

        if assessment is None:
            raise ValueError(
                "attestation_assessment_missing"
            )

        if assessment.case_id != attestation.case_id:
            raise ValueError(
                "attestation_assessment_case_mismatch"
            )

        if (
            assessment.customer_package_fingerprint
            != attestation.customer_package_fingerprint
        ):
            raise ValueError(
                "attestation_assessment_fingerprint_mismatch"
            )

        known_fingerprints = package_fingerprints_by_case.get(
            attestation.case_id,
            set(),
        )

        if (
            attestation.customer_package_fingerprint
            not in known_fingerprints
        ):
            raise ValueError(
                "attestation_package_fingerprint_missing"
            )

    for case in snapshot.cases:
        known_fingerprints = package_fingerprints_by_case.get(
            case.case_id,
            set(),
        )

        if (
            case.customer_package_fingerprint
            and case.customer_package_fingerprint
            not in known_fingerprints
        ):
            raise ValueError(
                "case_package_fingerprint_missing"
            )

        if (
            case.readiness_assessment_id
            and case.readiness_assessment_id
            not in assessments_by_id
        ):
            raise ValueError(
                "case_readiness_assessment_missing"
            )

        if case.readiness_assessment_id:
            linked_assessment = assessments_by_id[
                case.readiness_assessment_id
            ]

            if linked_assessment.case_id != case.case_id:
                raise ValueError(
                    "case_readiness_assessment_mismatch"
                )


    attestations_by_id = {
        attestation.attestation_id: attestation
        for attestation in (
            snapshot.supervisor_readiness_attestations
        )
    }

    qualification_keys_by_id = {
        qualification_key.qualification_key_id: qualification_key
        for qualification_key in snapshot.qualification_keys
    }

    for qualification_key in snapshot.qualification_keys:
        case = cases_by_id.get(qualification_key.case_id)

        if case is None:
            raise ValueError(
                "qualification_key_case_missing"
            )

        if qualification_key.client_id != case.client_id:
            raise ValueError(
                "qualification_key_client_mismatch"
            )

        attestation = attestations_by_id.get(
            qualification_key.attestation_id
        )

        if attestation is None:
            raise ValueError(
                "qualification_key_attestation_missing"
            )

        if attestation.case_id != qualification_key.case_id:
            raise ValueError(
                "qualification_key_attestation_case_mismatch"
            )

        if (
            attestation.readiness_assessment_id
            != qualification_key.readiness_assessment_id
        ):
            raise ValueError(
                "qualification_key_assessment_mismatch"
            )

        if (
            attestation.customer_package_fingerprint
            != qualification_key.customer_package_fingerprint
        ):
            raise ValueError(
                "qualification_key_fingerprint_mismatch"
            )

    for sandbox_api_key in snapshot.sandbox_api_keys:
        case = cases_by_id.get(sandbox_api_key.case_id)

        if case is None:
            raise ValueError(
                "sandbox_api_key_case_missing"
            )

        qualification_key = qualification_keys_by_id.get(
            sandbox_api_key.qualification_key_id
        )

        if qualification_key is None:
            raise ValueError(
                "sandbox_api_key_qualification_key_missing"
            )

        if qualification_key.case_id != sandbox_api_key.case_id:
            raise ValueError(
                "sandbox_api_key_qualification_case_mismatch"
            )

        if sandbox_api_key.client_id != case.client_id:
            raise ValueError(
                "sandbox_api_key_client_mismatch"
            )

        if sandbox_api_key.connector_id != case.connector_id:
            raise ValueError(
                "sandbox_api_key_connector_mismatch"
            )

        if (
            sandbox_api_key.credential_profile_id
            != case.credential_profile_id
        ):
            raise ValueError(
                "sandbox_api_key_credential_profile_mismatch"
            )

        if (
            sandbox_api_key.target_environment
            != case.target_environment
        ):
            raise ValueError(
                "sandbox_api_key_environment_mismatch"
            )


def _case_to_dict(
    case: ExternalConnectivityCase,
) -> dict[str, Any]:
    payload = asdict(case)
    payload["state"] = case.state.value
    return payload


def _package_to_dict(
    package: CustomerReferencePackage,
) -> dict[str, Any]:
    payload = asdict(package)
    payload["secret_reference_ids"] = list(
        package.secret_reference_ids
    )
    return payload


def _assessment_to_dict(
    assessment: ExternalConnectivityReadinessAssessment,
) -> dict[str, Any]:
    payload = asdict(assessment)

    tuple_fields = (
        "missing_input_codes",
        "missing_control_codes",
        "blocker_codes",
        "remediation_codes",
    )

    for field_name in tuple_fields:
        payload[field_name] = list(
            getattr(assessment, field_name)
        )

    return payload


def _attestation_to_dict(
    attestation: SupervisorReadinessAttestation,
) -> dict[str, Any]:
    payload = asdict(attestation)
    payload["decision"] = attestation.decision.value
    return payload


def _qualification_key_to_dict(
    qualification_key: ExternalConnectivityQualificationKey,
) -> dict[str, Any]:
    payload = asdict(qualification_key)
    payload["status"] = qualification_key.status.value
    return payload


def _sandbox_api_key_to_dict(
    sandbox_api_key: ExternalConnectivitySandboxApiKey,
) -> dict[str, Any]:
    payload = asdict(sandbox_api_key)
    payload["status"] = sandbox_api_key.status.value
    payload["allowed_scope_ids"] = list(
        sandbox_api_key.allowed_scope_ids
    )
    return payload


def _snapshot_to_dict(
    snapshot: ExternalConnectivityCaseStoreSnapshot,
) -> dict[str, Any]:
    return {
        "schema_version": snapshot.schema_version,
        "cases": [
            _case_to_dict(case)
            for case in snapshot.cases
        ],
        "customer_reference_packages": [
            _package_to_dict(package)
            for package in snapshot.customer_reference_packages
        ],
        "readiness_assessments": [
            _assessment_to_dict(assessment)
            for assessment in snapshot.readiness_assessments
        ],
        "supervisor_readiness_attestations": [
            _attestation_to_dict(attestation)
            for attestation in (
                snapshot.supervisor_readiness_attestations
            )
        ],
        "qualification_keys": [
            _qualification_key_to_dict(qualification_key)
            for qualification_key in snapshot.qualification_keys
        ],
        "sandbox_api_keys": [
            _sandbox_api_key_to_dict(sandbox_api_key)
            for sandbox_api_key in snapshot.sandbox_api_keys
        ],
    }


def _record_mapping(
    value: object,
    *,
    error: str,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(error)

    return dict(value)


def _case_from_dict(
    value: object,
) -> ExternalConnectivityCase:
    payload = _record_mapping(
        value,
        error="store_case_record_invalid",
    )

    try:
        payload["state"] = ExternalConnectivityCaseState(
            payload["state"]
        )
        return ExternalConnectivityCase(**payload)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("store_case_record_invalid") from exc


def _package_from_dict(
    value: object,
) -> CustomerReferencePackage:
    payload = _record_mapping(
        value,
        error="store_customer_package_record_invalid",
    )

    try:
        payload["secret_reference_ids"] = tuple(
            payload["secret_reference_ids"]
        )
        return CustomerReferencePackage(**payload)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            "store_customer_package_record_invalid"
        ) from exc


def _assessment_from_dict(
    value: object,
) -> ExternalConnectivityReadinessAssessment:
    payload = _record_mapping(
        value,
        error="store_assessment_record_invalid",
    )

    tuple_fields = (
        "missing_input_codes",
        "missing_control_codes",
        "blocker_codes",
        "remediation_codes",
    )

    try:
        for field_name in tuple_fields:
            payload[field_name] = tuple(payload[field_name])

        return ExternalConnectivityReadinessAssessment(**payload)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            "store_assessment_record_invalid"
        ) from exc


def _attestation_from_dict(
    value: object,
) -> SupervisorReadinessAttestation:
    payload = _record_mapping(
        value,
        error="store_supervisor_attestation_record_invalid",
    )

    try:
        payload["decision"] = SupervisorReadinessDecision(
            payload["decision"]
        )
        return SupervisorReadinessAttestation(**payload)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            "store_supervisor_attestation_record_invalid"
        ) from exc


def _qualification_key_from_dict(
    value: object,
) -> ExternalConnectivityQualificationKey:
    payload = _record_mapping(
        value,
        error="store_qualification_key_record_invalid",
    )

    try:
        payload["status"] = (
            ExternalConnectivityQualificationKeyStatus(
                payload["status"]
            )
        )
        return ExternalConnectivityQualificationKey(**payload)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            "store_qualification_key_record_invalid"
        ) from exc


def _sandbox_api_key_from_dict(
    value: object,
) -> ExternalConnectivitySandboxApiKey:
    payload = _record_mapping(
        value,
        error="store_sandbox_api_key_record_invalid",
    )

    try:
        payload["status"] = (
            ExternalConnectivitySandboxApiKeyStatus(
                payload["status"]
            )
        )
        payload["allowed_scope_ids"] = tuple(
            payload["allowed_scope_ids"]
        )
        return ExternalConnectivitySandboxApiKey(**payload)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            "store_sandbox_api_key_record_invalid"
        ) from exc


def _snapshot_from_dict(
    payload: object,
) -> ExternalConnectivityCaseStoreSnapshot:
    if not isinstance(payload, dict):
        raise ValueError("store_payload_invalid")

    if (
        payload.get("schema_version")
        != EXTERNAL_CONNECTIVITY_CASE_STORE_SCHEMA_VERSION
    ):
        raise ValueError("store_schema_version_invalid")

    raw_cases = payload.get("cases", [])
    raw_packages = payload.get(
        "customer_reference_packages",
        [],
    )
    raw_assessments = payload.get(
        "readiness_assessments",
        [],
    )
    raw_attestations = payload.get(
        "supervisor_readiness_attestations",
        [],
    )

    raw_qualification_keys = payload.get(
        "qualification_keys",
        [],
    )
    raw_sandbox_api_keys = payload.get(
        "sandbox_api_keys",
        [],
    )

    if not isinstance(raw_cases, list):
        raise ValueError("store_cases_invalid")
    if not isinstance(raw_packages, list):
        raise ValueError(
            "store_customer_reference_packages_invalid"
        )
    if not isinstance(raw_assessments, list):
        raise ValueError("store_readiness_assessments_invalid")
    if not isinstance(raw_attestations, list):
        raise ValueError(
            "store_supervisor_attestations_invalid"
        )

    if not isinstance(raw_qualification_keys, list):
        raise ValueError(
            "store_qualification_keys_invalid"
        )
    if not isinstance(raw_sandbox_api_keys, list):
        raise ValueError(
            "store_sandbox_api_keys_invalid"
        )

    snapshot = ExternalConnectivityCaseStoreSnapshot(
        cases=tuple(
            _case_from_dict(value)
            for value in raw_cases
        ),
        customer_reference_packages=tuple(
            _package_from_dict(value)
            for value in raw_packages
        ),
        readiness_assessments=tuple(
            _assessment_from_dict(value)
            for value in raw_assessments
        ),
        supervisor_readiness_attestations=tuple(
            _attestation_from_dict(value)
            for value in raw_attestations
        ),
        qualification_keys=tuple(
            _qualification_key_from_dict(value)
            for value in raw_qualification_keys
        ),
        sandbox_api_keys=tuple(
            _sandbox_api_key_from_dict(value)
            for value in raw_sandbox_api_keys
        ),
    )

    _validate_snapshot(snapshot)
    return snapshot


def load_external_connectivity_case_store(
    path: str | Path | None = None,
) -> ExternalConnectivityCaseStoreSnapshot:
    resolved_path = external_connectivity_case_store_path(path)

    if not resolved_path.exists():
        return ExternalConnectivityCaseStoreSnapshot()

    try:
        raw_text = resolved_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError("store_read_failed") from exc

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError("store_json_invalid") from exc

    return _snapshot_from_dict(payload)


def _atomic_write_text(
    path: Path,
    content: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary_path = Path(temporary_name)

    try:
        with os.fdopen(
            descriptor,
            "w",
            encoding="utf-8",
            newline="\n",
        ) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())

        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def save_external_connectivity_case_store(
    snapshot: ExternalConnectivityCaseStoreSnapshot,
    path: str | Path | None = None,
) -> None:
    _validate_snapshot(snapshot)

    resolved_path = external_connectivity_case_store_path(path)
    payload = _snapshot_to_dict(snapshot)

    content = (
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        + "\n"
    )

    _atomic_write_text(resolved_path, content)


__all__ = [
    "DEFAULT_EXTERNAL_CONNECTIVITY_CASE_STORE_PATH",
    "EXTERNAL_CONNECTIVITY_CASE_STORE_SCHEMA_VERSION",
    "ExternalConnectivityCaseStoreSnapshot",
    "external_connectivity_case_store_path",
    "load_external_connectivity_case_store",
    "save_external_connectivity_case_store",
]
