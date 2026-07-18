from __future__ import annotations

import importlib
from pathlib import Path

DOCUMENT_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "integrations"
    / "EXTERNAL_CONNECTIVITY_R10.md"
)


def _document() -> str:
    assert DOCUMENT_PATH.is_file(), (
        "R10 documentation is missing: "
        f"{DOCUMENT_PATH}"
    )
    return DOCUMENT_PATH.read_text(encoding="utf-8")


def _normalized_document() -> str:
    return _document().lower()


def test_r10_public_integration_exports_are_complete() -> None:
    integrations = importlib.import_module(
        "processual_api.integrations"
    )
    expected = {
        "ExternalConnectivityQualificationKey",
        "ExternalConnectivityQualificationKeyStatus",
        "ExternalConnectivitySandboxApiKey",
        "ExternalConnectivitySandboxApiKeyStatus",
    }

    missing_attributes = {
        name
        for name in expected
        if not hasattr(integrations, name)
    }
    exported = set(getattr(integrations, "__all__", ()))
    missing_all = expected - exported

    assert not missing_attributes, (
        "missing R10 integration attributes: "
        f"{sorted(missing_attributes)}"
    )
    assert not missing_all, (
        "missing R10 __all__ exports: "
        f"{sorted(missing_all)}"
    )


def test_r10_document_declares_identity_status_and_purpose() -> None:
    document = _document()

    assert document.startswith("# EXTERNAL-CONNECTIVITY-R10")
    assert "## Status" in document
    assert "## Purpose" in document
    assert "## Implemented scope" in document


def test_r10_document_lists_exact_implementation_scope() -> None:
    normalized = _normalized_document()
    required_paths = {
        "docs/integrations/external_connectivity_r10.md",
        "processual_api/integrations/external_connectivity_cases.py",
        "processual_api/integrations/__init__.py",
        "processual_api/services/external_connectivity_case_store.py",
        "processual_api/services/external_connectivity_qualification.py",
        "processual_api/schemas/external_connectivity.py",
        "processual_api/schemas/__init__.py",
        "processual_api/main.py",
        "tests/test_external_connectivity_key_contracts_r10.py",
        "tests/test_external_connectivity_qualification_service_r10.py",
        "tests/test_external_connectivity_key_lifecycle_r10.py",
        "tests/test_external_connectivity_key_routes_r10.py",
        "tests/test_external_connectivity_r10_document_and_exports.py",
    }

    assert required_paths.issubset(normalized.split())


def test_r10_document_records_routes_and_lifecycle() -> None:
    normalized = _normalized_document()
    required_markers = {
        "qualification_key_one_time=true",
        "qualification_key_client_bound=true",
        "qualification_key_attestation_bound=true",
        "raw_qualification_key_persisted=false",
        "sandbox_api_key_one_time=true",
        "sandbox_key_connector_bound=true",
        "sandbox_key_scope_bound=true",
        "sandbox_key_case_bound=true",
        "raw_sandbox_key_persisted=false",
        "unsupported_connector_scope_rejected=true",
    }
    assert required_markers.issubset(normalized.split())

    required_routes = {
        (
            "post /settings/admin/external-connectivity/"
            "cases/{case_id}/qualification-key"
        ),
        (
            "post /settings/admin/external-connectivity/"
            "cases/{case_id}/qualification-key/"
            "{qualification_key_id}/revoke"
        ),
        (
            "post /settings/client/external-connectivity/"
            "qualification/redeem"
        ),
        (
            "post /settings/admin/external-connectivity/"
            "cases/{case_id}/sandbox-api-key"
        ),
        (
            "post /settings/admin/external-connectivity/"
            "cases/{case_id}/sandbox-api-key/"
            "{sandbox_api_key_id}/suspend"
        ),
        (
            "post /settings/admin/external-connectivity/"
            "cases/{case_id}/sandbox-api-key/"
            "{sandbox_api_key_id}/revoke"
        ),
    }

    assert all(route in normalized for route in required_routes)


def test_r10_document_records_security_and_non_authority() -> None:
    normalized = _normalized_document()
    required_markers = {
        "supervisor_write_guard_enabled=true",
        "canonical_case_store_used=true",
        "parallel_key_store_created=false",
        "connector_scope_binding=true",
        "route_case_binding=true",
        "safe_case_response_projection=true",
        "raw_secret_echoed=false",
        "network_access_performed=false",
        "external_http_enabled=false",
        "socket_access_enabled=false",
        "dns_resolution_performed=false",
        "credentials_resolved=false",
        "provider_sdk_invoked=false",
        "sandbox_transport_invoked=false",
        "runtime_connector_enabled=false",
        "production_allowed=false",
    }

    assert required_markers.issubset(normalized.split())


def test_r10_document_records_regression_and_phase_boundary() -> None:
    document = _document()
    normalized = document.lower()

    assert "## Regression coverage" in document
    assert "## Acceptance criteria" in document
    assert "## Phase 3 boundary" in document
    assert "r10_pre_document_tests=28_passed" in normalized
    assert "r8_r9_compatibility_tests=117_passed" in normalized
    assert "combined_pre_document_tests=145_passed" in normalized
    assert "phase_1_readiness_completed=true" in normalized
    assert "phase_2_qualification_completed=true" in normalized
    assert "phase_3_real_sandbox_started=false" in normalized
    assert "real_sandbox_connection_attempted=false" in normalized
    assert "production_connectivity_enabled=false" in normalized
