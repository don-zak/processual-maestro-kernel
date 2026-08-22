from __future__ import annotations

import pytest

from processual_api.integrations.endpoint_source_attestation import (
    TrustedEndpointSourceRecord,
    attest_endpoint_source_identity,
)


@pytest.fixture
def trusted_record() -> TrustedEndpointSourceRecord:
    return TrustedEndpointSourceRecord(
        source_identity_id="provider.customer_api",
        contract_family="generic_enterprise",
        source_reference="customer-api/releases/v1.4.2/openapi.json",
        source_kind="artifact_sha256",
        source_revision="a" * 64,
        source_sha256="a" * 64,
        policy_version="qualification-r1",
    )


def test_default_registry_never_trusts_caller_source_claim() -> None:
    result = attest_endpoint_source_identity(
        source_reference="customer-api/releases/v1.4.2/openapi.json",
        source_kind="artifact_sha256",
        source_revision="a" * 64,
        source_sha256="a" * 64,
        contract_family="generic_enterprise",
    )

    assert result.source_identity_verified is False
    assert result.source_identity_id is None
    assert result.source_identity_verification_method == "unverified"
    assert result.production_allowed is False
    assert result.runtime_connector_approved is False


def test_exact_server_trusted_tuple_attests_source_identity(
    trusted_record: TrustedEndpointSourceRecord,
) -> None:
    result = attest_endpoint_source_identity(
        source_reference=trusted_record.source_reference,
        source_kind=trusted_record.source_kind,
        source_revision=trusted_record.source_revision,
        source_sha256=trusted_record.source_sha256,
        contract_family=trusted_record.contract_family,
        trusted_sources=[trusted_record],
    )

    assert result.source_identity_verified is True
    assert result.source_identity_id == "provider.customer_api"
    assert result.source_identity_policy_version == "qualification-r1"
    assert result.source_identity_verification_method == "server_trusted_exact_tuple"
    assert result.production_allowed is False
    assert result.runtime_connector_approved is False


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_reference", "attacker.example/openapi.json"),
        ("source_revision", "b" * 64),
        ("source_sha256", "b" * 64),
        ("contract_family", "camara"),
        ("source_kind", "git_commit"),
    ],
)
def test_any_source_identity_tuple_drift_fails_closed(
    trusted_record: TrustedEndpointSourceRecord,
    field: str,
    value: str,
) -> None:
    values = {
        "source_reference": trusted_record.source_reference,
        "source_kind": trusted_record.source_kind,
        "source_revision": trusted_record.source_revision,
        "source_sha256": trusted_record.source_sha256,
        "contract_family": trusted_record.contract_family,
    }
    values[field] = value

    result = attest_endpoint_source_identity(
        **values,
        trusted_sources=[trusted_record],
    )

    assert result.source_identity_verified is False
    assert result.source_identity_id is None
    assert result.production_allowed is False
    assert result.runtime_connector_approved is False
