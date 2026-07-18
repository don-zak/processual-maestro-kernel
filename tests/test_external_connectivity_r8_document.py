from __future__ import annotations

import importlib
from pathlib import Path

DOCUMENT_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "integrations"
    / "EXTERNAL_CONNECTIVITY_R8.md"
)


def _document() -> str:
    assert DOCUMENT_PATH.is_file(), (
        "R8 documentation is missing: "
        f"{DOCUMENT_PATH}"
    )
    return DOCUMENT_PATH.read_text(encoding="utf-8")


def _normalized_document() -> str:
    return _document().lower()


def test_r8_document_declares_identity_status_and_purpose() -> None:
    document = _document()

    assert document.startswith("# EXTERNAL-CONNECTIVITY-R8")
    assert "## Status" in document
    assert "## Purpose" in document


def test_r8_document_lists_exact_implementation_scope() -> None:
    document = _normalized_document()
    required_paths = {
        "processual_api/integrations/external_connectivity_cases.py",
        "processual_api/services/external_connectivity_case_store.py",
        "processual_api/schemas/external_connectivity.py",
        "tests/test_external_connectivity_case_contracts_r8.py",
        "tests/test_external_connectivity_case_store_r8.py",
        "tests/test_external_connectivity_openapi_models_r8.py",
    }

    assert required_paths.issubset(document.split())
    assert "route_implementation_included=false" in document


def test_r8_document_contains_complete_state_catalog() -> None:
    contracts = importlib.import_module(
        "processual_api.integrations.external_connectivity_cases"
    )
    document = _normalized_document()
    states = {state.value for state in contracts.ExternalConnectivityCaseState}

    assert states
    assert all(state in document for state in states)
    assert "state_transitions_allowlisted=true" in document


def test_r8_document_contains_complete_audit_taxonomy() -> None:
    contracts = importlib.import_module(
        "processual_api.integrations.external_connectivity_cases"
    )
    document = _normalized_document()
    event_types = {
        event_type.value
        for event_type in contracts.ExternalConnectivityAuditEventType
    }

    assert event_types
    assert all(event_type in document for event_type in event_types)
    assert "audit_events_redacted=true" in document


def test_r8_document_records_secret_and_network_invariants() -> None:
    document = _normalized_document()
    required_markers = {
        "raw_customer_secret_accepted=false",
        "network_access_performed=false",
        "external_http_enabled=false",
        "socket_access_enabled=false",
        "dns_resolution_performed=false",
        "credentials_resolved=false",
        "provider_binding_created=false",
        "raw_secret_visible=false",
        "runtime_enabled=false",
        "production_allowed=false",
    }

    assert required_markers.issubset(document.split())


def test_r8_document_records_store_and_openapi_boundaries() -> None:
    document = _normalized_document()

    assert "stores_test_isolated=true" in document
    assert "atomic_write_enabled=true" in document
    assert "openapi_models_exposed=true" in document
    assert "raw_secret_properties_exposed=false" in document


def test_r8_document_records_regression_and_r9_boundary() -> None:
    document = _document()
    normalized = document.lower()

    assert "## Regression coverage" in document
    assert "## Acceptance criteria" in document
    assert "## R9 boundary" in document
    assert "direct_tests=71_passed" in normalized
    assert "focused_regression=368_passed" in normalized
    assert "r9_implementation_included=false" in normalized
    assert "secret_resolution_included=false" in normalized
    assert "external_connection_attempted=false" in normalized
