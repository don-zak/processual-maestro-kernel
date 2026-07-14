from __future__ import annotations

import importlib
import json
from dataclasses import replace
from pathlib import Path
from types import ModuleType

import pytest

from processual_api.integrations.external_connectivity_cases import (
    CustomerReferencePackage,
    ExternalConnectivityCase,
    ExternalConnectivityCaseState,
    ExternalConnectivityReadinessAssessment,
    customer_reference_package_fingerprint,
)


def _store_module() -> ModuleType:
    return importlib.import_module(
        "processual_api.services.external_connectivity_case_store"
    )


def _package(**overrides: object) -> CustomerReferencePackage:
    values: dict[str, object] = {
        "package_id": "ecpkg_case001_v1",
        "case_id": "eccase_001",
        "client_id": "client_001",
        "schema_version": "external-connectivity-customer-package/v1",
        "connector_id": "telecom_crm_reference",
        "credential_profile_id": "oauth2_client_credentials_reference",
        "target_environment": "sandbox",
        "target_reference_id": "target_ref_crm_sandbox_001",
        "secret_reference_ids": ("secret_ref_crm_oauth_001",),
        "dns_reference": "dns_ref_customer_crm_001",
        "tls_policy_reference": "tls_policy_ref_12_plus_001",
        "certificate_reference": "certificate_ref_customer_001",
        "outbound_allowlist_reference": "allowlist_ref_customer_001",
        "submitted_at": "2026-07-14T10:00:00Z",
    }
    values.update(overrides)
    return CustomerReferencePackage(**values)


def _case(
    *,
    package_fingerprint: str,
    **overrides: object,
) -> ExternalConnectivityCase:
    values: dict[str, object] = {
        "case_id": "eccase_001",
        "client_id": "client_001",
        "readiness_case_id": "readiness_case_001",
        "integration_task_id": "",
        "connector_id": "telecom_crm_reference",
        "credential_profile_id": "oauth2_client_credentials_reference",
        "target_environment": "sandbox",
        "state": (
            ExternalConnectivityCaseState.CUSTOMER_PACKAGE_SUBMITTED
        ),
        "customer_package_fingerprint": package_fingerprint,
        "readiness_assessment_id": "ecassessment_001",
        "revision": 2,
        "created_at": "2026-07-14T10:00:00Z",
        "updated_at": "2026-07-14T10:05:00Z",
    }
    values.update(overrides)
    return ExternalConnectivityCase(**values)


def _assessment(
    *,
    package_fingerprint: str,
    **overrides: object,
) -> ExternalConnectivityReadinessAssessment:
    values: dict[str, object] = {
        "assessment_id": "ecassessment_001",
        "case_id": "eccase_001",
        "customer_package_fingerprint": package_fingerprint,
        "assessment_schema_version": (
            "external-connectivity-readiness-assessment/v1"
        ),
        "readiness_status": "needs_remediation",
        "missing_input_codes": ("customer_crm_scope_reference",),
        "missing_control_codes": ("tls_policy_review",),
        "blocker_codes": ("tls_policy_review_required",),
        "remediation_codes": ("submit_tls_policy_reference",),
        "evidence_completeness": 0.75,
        "ready_for_supervisor_approval": False,
        "assessed_at": "2026-07-14T10:05:00Z",
    }
    values.update(overrides)
    return ExternalConnectivityReadinessAssessment(**values)


def _complete_snapshot(module: ModuleType) -> object:
    package = _package()
    fingerprint = customer_reference_package_fingerprint(package)
    case = _case(package_fingerprint=fingerprint)
    assessment = _assessment(package_fingerprint=fingerprint)

    return module.ExternalConnectivityCaseStoreSnapshot(
        cases=(case,),
        customer_reference_packages=(package,),
        readiness_assessments=(assessment,),
    )


def test_r8_store_exports_required_symbols() -> None:
    module = _store_module()

    required = {
        "EXTERNAL_CONNECTIVITY_CASE_STORE_SCHEMA_VERSION",
        "DEFAULT_EXTERNAL_CONNECTIVITY_CASE_STORE_PATH",
        "ExternalConnectivityCaseStoreSnapshot",
        "external_connectivity_case_store_path",
        "load_external_connectivity_case_store",
        "save_external_connectivity_case_store",
    }

    assert required.issubset(set(dir(module)))
    assert (
        module.EXTERNAL_CONNECTIVITY_CASE_STORE_SCHEMA_VERSION
        == "external-connectivity-case-store/v1"
    )


def test_r8_store_path_precedence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _store_module()
    environment_path = tmp_path / "environment.json"
    explicit_path = tmp_path / "explicit.json"

    monkeypatch.setenv(
        "PMK_EXTERNAL_CONNECTIVITY_CASES_PATH",
        str(environment_path),
    )

    assert module.external_connectivity_case_store_path() == environment_path
    assert (
        module.external_connectivity_case_store_path(explicit_path)
        == explicit_path
    )


def test_r8_missing_store_returns_empty_snapshot(
    tmp_path: Path,
) -> None:
    module = _store_module()
    snapshot = module.load_external_connectivity_case_store(
        tmp_path / "missing.json"
    )

    assert snapshot.cases == ()
    assert snapshot.customer_reference_packages == ()
    assert snapshot.readiness_assessments == ()


def test_r8_store_round_trip(
    tmp_path: Path,
) -> None:
    module = _store_module()
    path = tmp_path / "cases.json"
    expected = _complete_snapshot(module)

    module.save_external_connectivity_case_store(expected, path)
    actual = module.load_external_connectivity_case_store(path)

    assert actual == expected


def test_r8_store_serialization_is_deterministic(
    tmp_path: Path,
) -> None:
    module = _store_module()
    path = tmp_path / "cases.json"
    snapshot = _complete_snapshot(module)

    module.save_external_connectivity_case_store(snapshot, path)
    first = path.read_bytes()

    module.save_external_connectivity_case_store(snapshot, path)
    second = path.read_bytes()

    assert first == second


def test_r8_store_paths_are_isolated(
    tmp_path: Path,
) -> None:
    module = _store_module()
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"

    module.save_external_connectivity_case_store(
        _complete_snapshot(module),
        first_path,
    )

    first = module.load_external_connectivity_case_store(first_path)
    second = module.load_external_connectivity_case_store(second_path)

    assert len(first.cases) == 1
    assert second.cases == ()
    assert second.customer_reference_packages == ()
    assert second.readiness_assessments == ()


def test_r8_store_rejects_duplicate_case_ids(
    tmp_path: Path,
) -> None:
    module = _store_module()
    snapshot = _complete_snapshot(module)

    duplicated = replace(
        snapshot,
        cases=(snapshot.cases[0], snapshot.cases[0]),
    )

    with pytest.raises(ValueError, match="duplicate_case_id"):
        module.save_external_connectivity_case_store(
            duplicated,
            tmp_path / "cases.json",
        )


def test_r8_store_rejects_duplicate_package_ids(
    tmp_path: Path,
) -> None:
    module = _store_module()
    snapshot = _complete_snapshot(module)

    duplicated = replace(
        snapshot,
        customer_reference_packages=(
            snapshot.customer_reference_packages[0],
            snapshot.customer_reference_packages[0],
        ),
    )

    with pytest.raises(ValueError, match="duplicate_package_id"):
        module.save_external_connectivity_case_store(
            duplicated,
            tmp_path / "cases.json",
        )


def test_r8_store_rejects_duplicate_assessment_ids(
    tmp_path: Path,
) -> None:
    module = _store_module()
    snapshot = _complete_snapshot(module)

    duplicated = replace(
        snapshot,
        readiness_assessments=(
            snapshot.readiness_assessments[0],
            snapshot.readiness_assessments[0],
        ),
    )

    with pytest.raises(ValueError, match="duplicate_assessment_id"):
        module.save_external_connectivity_case_store(
            duplicated,
            tmp_path / "cases.json",
        )


def test_r8_store_rejects_orphan_customer_package(
    tmp_path: Path,
) -> None:
    module = _store_module()
    snapshot = _complete_snapshot(module)
    orphan = replace(
        snapshot.customer_reference_packages[0],
        case_id="eccase_missing",
    )

    invalid = replace(
        snapshot,
        customer_reference_packages=(orphan,),
    )

    with pytest.raises(ValueError, match="customer_package_case_missing"):
        module.save_external_connectivity_case_store(
            invalid,
            tmp_path / "cases.json",
        )


def test_r8_store_rejects_assessment_fingerprint_mismatch(
    tmp_path: Path,
) -> None:
    module = _store_module()
    snapshot = _complete_snapshot(module)
    mismatched = replace(
        snapshot.readiness_assessments[0],
        customer_package_fingerprint="b" * 64,
    )

    invalid = replace(
        snapshot,
        readiness_assessments=(mismatched,),
    )

    with pytest.raises(
        ValueError,
        match="assessment_package_fingerprint_mismatch",
    ):
        module.save_external_connectivity_case_store(
            invalid,
            tmp_path / "cases.json",
        )


def test_r8_store_rejects_corrupted_json_without_mutation(
    tmp_path: Path,
) -> None:
    module = _store_module()
    path = tmp_path / "cases.json"
    original = b'{"broken":'
    path.write_bytes(original)

    with pytest.raises(ValueError, match="store_json_invalid"):
        module.load_external_connectivity_case_store(path)

    assert path.read_bytes() == original


def test_r8_store_rejects_unknown_schema_version(
    tmp_path: Path,
) -> None:
    module = _store_module()
    path = tmp_path / "cases.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "unknown/v99",
                "cases": [],
                "customer_reference_packages": [],
                "readiness_assessments": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="store_schema_version_invalid"):
        module.load_external_connectivity_case_store(path)


def test_r8_store_atomic_write_leaves_no_temp_files(
    tmp_path: Path,
) -> None:
    module = _store_module()
    path = tmp_path / "cases.json"

    module.save_external_connectivity_case_store(
        _complete_snapshot(module),
        path,
    )

    assert path.is_file()
    assert not list(tmp_path.glob("*.tmp"))


def test_r8_store_round_trip_preserves_default_deny(
    tmp_path: Path,
) -> None:
    module = _store_module()
    path = tmp_path / "cases.json"

    module.save_external_connectivity_case_store(
        _complete_snapshot(module),
        path,
    )
    loaded = module.load_external_connectivity_case_store(path)
    case = loaded.cases[0]
    assessment = loaded.readiness_assessments[0]

    assert case.production_allowed is False
    assert case.runtime_connector_allowed is False
    assert case.external_http_allowed is False
    assert case.secret_resolution_allowed is False
    assert case.automatic_activation_allowed is False
    assert case.raw_secret_visible is False

    assert assessment.network_access_performed is False
    assert assessment.secrets_read is False
    assert assessment.provider_sdk_initialized is False
    assert assessment.certificate_loaded is False
    assert assessment.sandbox_launched is False
    assert assessment.production_allowed is False


def test_r8_store_module_has_no_network_or_secret_provider_sdk() -> None:
    module = _store_module()
    source = Path(module.__file__).read_text(encoding="utf-8")

    prohibited = (
        "import requests",
        "import httpx",
        "import socket",
        "from requests",
        "from httpx",
        "from socket",
        "boto3",
        "google.cloud.secretmanager",
        "azure.keyvault",
        "hvac.Client",
        "urlopen(",
        "requests.",
        "httpx.",
    )

    for marker in prohibited:
        assert marker not in source
