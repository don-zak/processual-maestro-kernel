from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from processual_api.integrations.external_connectivity_cases import (
    ExternalConnectivityQualificationKey,
    ExternalConnectivityQualificationKeyStatus,
    ExternalConnectivitySandboxApiKey,
    ExternalConnectivitySandboxApiKeyStatus,
)


def _qualification_key() -> ExternalConnectivityQualificationKey:
    return ExternalConnectivityQualificationKey(
        qualification_key_id="qk_r10_reference",
        case_id="case_r10",
        client_id="client_r10",
        attestation_id="attestation_r10",
        readiness_assessment_id="assessment_r10",
        customer_package_fingerprint="a" * 64,
        key_hash="b" * 64,
        status=ExternalConnectivityQualificationKeyStatus.ISSUED,
        issued_at="2026-07-14T12:00:00+00:00",
        expires_at="2026-07-15T12:00:00+00:00",
        issued_by="supsk_r10_supervisor",
    )


def _sandbox_key() -> ExternalConnectivitySandboxApiKey:
    return ExternalConnectivitySandboxApiKey(
        sandbox_api_key_id="sbk_r10_reference",
        case_id="case_r10",
        client_id="client_r10",
        qualification_key_id="qk_r10_reference",
        connector_id="telecom_ticketing_reference",
        credential_profile_id="telecom_operations_api_reference",
        target_environment="sandbox",
        allowed_scope_ids=("ticketing:read",),
        key_hash="c" * 64,
        status=ExternalConnectivitySandboxApiKeyStatus.ISSUED,
        issued_at="2026-07-14T12:05:00+00:00",
        expires_at="2026-07-15T12:05:00+00:00",
        issued_by="supsk_r10_supervisor",
    )


def test_r10_key_status_catalogs_are_exact() -> None:
    assert {
        item.value
        for item in ExternalConnectivityQualificationKeyStatus
    } == {
        "issued",
        "redeemed",
        "revoked",
        "expired",
    }

    assert {
        item.value
        for item in ExternalConnectivitySandboxApiKeyStatus
    } == {
        "issued",
        "suspended",
        "revoked",
        "expired",
    }


def test_r10_qualification_key_is_frozen_and_default_deny() -> None:
    key = _qualification_key()

    assert key.production_allowed is False
    assert key.external_http_allowed is False
    assert key.secret_resolution_allowed is False
    assert key.sandbox_activation_allowed is False
    assert key.raw_secret_visible is False

    with pytest.raises(FrozenInstanceError):
        key.status = ExternalConnectivityQualificationKeyStatus.REDEEMED


def test_r10_sandbox_key_is_frozen_and_default_deny() -> None:
    key = _sandbox_key()

    assert key.target_environment == "sandbox"
    assert key.runtime_connector_allowed is False
    assert key.production_allowed is False
    assert key.external_http_allowed is False
    assert key.secret_resolution_allowed is False
    assert key.automatic_activation_allowed is False
    assert key.raw_secret_visible is False

    with pytest.raises(FrozenInstanceError):
        key.status = ExternalConnectivitySandboxApiKeyStatus.SUSPENDED


def test_r10_sandbox_key_rejects_non_sandbox_environment() -> None:
    payload = {
        field_name: getattr(_sandbox_key(), field_name)
        for field_name in _sandbox_key().__dataclass_fields__
    }
    payload["target_environment"] = "production"

    with pytest.raises(
        ValueError,
        match="target_environment_must_be_sandbox",
    ):
        ExternalConnectivitySandboxApiKey(**payload)
