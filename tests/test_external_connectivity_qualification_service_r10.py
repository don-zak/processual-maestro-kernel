from __future__ import annotations

import inspect

from processual_api.services.external_connectivity_qualification import (
    EXTERNAL_CONNECTIVITY_QUALIFICATION_SCHEMA_VERSION,
    ExternalConnectivityQualificationError,
    issue_external_connectivity_qualification_key,
    issue_external_connectivity_sandbox_api_key,
    redeem_external_connectivity_qualification_key,
    revoke_external_connectivity_qualification_key,
    revoke_external_connectivity_sandbox_api_key,
    suspend_external_connectivity_sandbox_api_key,
)

from processual_api.services.external_connectivity_case_store import (
    ExternalConnectivityCaseStoreSnapshot,
)


def test_r10_qualification_schema_version_is_fixed() -> None:
    assert EXTERNAL_CONNECTIVITY_QUALIFICATION_SCHEMA_VERSION == (
        "external-connectivity-qualification/v1"
    )


def test_r10_canonical_store_owns_both_key_collections() -> None:
    snapshot = ExternalConnectivityCaseStoreSnapshot()

    assert snapshot.qualification_keys == ()
    assert snapshot.sandbox_api_keys == ()


def test_r10_service_exports_complete_lifecycle() -> None:
    callables = (
        issue_external_connectivity_qualification_key,
        redeem_external_connectivity_qualification_key,
        revoke_external_connectivity_qualification_key,
        issue_external_connectivity_sandbox_api_key,
        suspend_external_connectivity_sandbox_api_key,
        revoke_external_connectivity_sandbox_api_key,
    )

    assert all(callable(item) for item in callables)
    assert issubclass(
        ExternalConnectivityQualificationError,
        ValueError,
    )


def test_r10_mutations_require_revision_time_and_canonical_path() -> None:
    mutation_functions = (
        issue_external_connectivity_qualification_key,
        redeem_external_connectivity_qualification_key,
        revoke_external_connectivity_qualification_key,
        issue_external_connectivity_sandbox_api_key,
        suspend_external_connectivity_sandbox_api_key,
        revoke_external_connectivity_sandbox_api_key,
    )

    for function in mutation_functions:
        parameters = inspect.signature(function).parameters

        assert "expected_revision" in parameters
        assert "occurred_at" in parameters
        assert "path" in parameters


def test_r10_service_has_no_network_or_provider_clients() -> None:
    import processual_api.services.external_connectivity_qualification as module

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
