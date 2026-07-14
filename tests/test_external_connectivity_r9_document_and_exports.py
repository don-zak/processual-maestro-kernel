from __future__ import annotations

import importlib
from pathlib import Path

DOCUMENT_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "integrations"
    / "EXTERNAL_CONNECTIVITY_R9.md"
)


def _document() -> str:
    assert DOCUMENT_PATH.is_file(), (
        "R9 documentation is missing: "
        f"{DOCUMENT_PATH}"
    )
    return DOCUMENT_PATH.read_text(encoding="utf-8")


def _normalized_document() -> str:
    return _document().lower()


def test_r9_public_integration_exports_are_complete() -> None:
    integrations = importlib.import_module(
        "processual_api.integrations"
    )
    expected = {
        "SupervisorReadinessAttestation",
        "SupervisorReadinessDecision",
        "is_supervisor_readiness_attestation_current",
    }

    missing_attributes = {
        name
        for name in expected
        if not hasattr(integrations, name)
    }
    exported = set(getattr(integrations, "__all__", ()))
    missing_all = expected - exported

    assert not missing_attributes, (
        "missing R9 integration attributes: "
        f"{sorted(missing_attributes)}"
    )
    assert not missing_all, (
        "missing R9 __all__ exports: "
        f"{sorted(missing_all)}"
    )


def test_r9_document_declares_identity_status_and_purpose() -> None:
    document = _document()

    assert document.startswith("# EXTERNAL-CONNECTIVITY-R9")
    assert "## Status" in document
    assert "## Purpose" in document
    assert "## Implemented scope" in document


def test_r9_document_lists_exact_implementation_scope() -> None:
    normalized = _normalized_document()
    required_paths = {
        "processual_api/integrations/external_connectivity_cases.py",
        "processual_api/integrations/__init__.py",
        "processual_api/services/external_connectivity_case_store.py",
        "processual_api/services/external_connectivity_intake.py",
        "processual_api/schemas/external_connectivity.py",
        "processual_api/schemas/__init__.py",
        "processual_api/main.py",
        "tests/test_external_connectivity_supervisor_attestation_r9.py",
        "tests/test_external_connectivity_intake_service_r9.py",
        "tests/test_external_connectivity_routes_r9.py",
        "tests/test_external_connectivity_r9_document_and_exports.py",
    }

    assert required_paths.issubset(normalized.split())


def test_r9_document_records_routes_and_security_boundary() -> None:
    normalized = _normalized_document()
    required_markers = {
        "supervisor_write_guard_enabled=true",
        "raw_customer_secret_accepted=false",
        "raw_secret_echoed=false",
        "server_generated_identifiers=true",
        "optimistic_revision_checks=true",
        "prior_approval_invalidated_on_resubmission=true",
    }

    assert required_markers.issubset(normalized.split())

    required_routes = {
        "get /settings/admin/external-connectivity/cases",
        "post /settings/admin/external-connectivity/cases",
        "get /settings/admin/external-connectivity/cases/{case_id}",
        (
            "post /settings/admin/external-connectivity/"
            "cases/{case_id}/reference-package"
        ),
        (
            "post /settings/admin/external-connectivity/"
            "cases/{case_id}/readiness-review"
        ),
        (
            "post /settings/admin/external-connectivity/"
            "cases/{case_id}/supervisor-decision"
        ),
    }

    assert all(route in normalized for route in required_routes)


def test_r9_document_records_non_authority_invariants() -> None:
    normalized = _normalized_document()
    required_markers = {
        "network_access_performed=false",
        "external_http_enabled=false",
        "socket_access_enabled=false",
        "dns_resolution_performed=false",
        "credentials_resolved=false",
        "provider_sdk_invoked=false",
        "qualification_key_issued=false",
        "sandbox_api_key_issued=false",
        "runtime_enabled=false",
        "production_allowed=false",
    }

    assert required_markers.issubset(normalized.split())


def test_r9_document_records_acceptance_and_next_boundary() -> None:
    document = _document()
    normalized = document.lower()

    assert "## Regression coverage" in document
    assert "## Acceptance criteria" in document
    assert "## Phase 2 boundary" in document
    assert "r9_direct_tests=39_passed" in normalized
    assert "r8_compatibility_tests=78_passed" in normalized
    assert "combined_pre_document_tests=117_passed" in normalized
    assert "phase_1_readiness_completed=true" in normalized
    assert "phase_2_qualification_implemented=false" in normalized
    assert "real_sandbox_connection_attempted=false" in normalized
    assert "production_connectivity_enabled=false" in normalized
