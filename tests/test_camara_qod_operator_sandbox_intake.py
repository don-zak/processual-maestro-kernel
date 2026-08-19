from __future__ import annotations

import pytest

from processual_api.integrations.camara_qod_operator_sandbox_intake import (
    CAMARA_QOD_OPERATOR_SANDBOX_INTAKE_CONTRACT,
    CamaraQodOperatorSandboxIntakeStatus,
    CamaraQodOperatorSandboxReferenceSubmission,
    assess_camara_qod_operator_sandbox_intake,
    camara_qod_operator_sandbox_intake_payload,
)


def _submission(**overrides: str) -> CamaraQodOperatorSandboxReferenceSubmission:
    values = {
        "operator_identity_reference": "operator:camara-qod-test",
        "sandbox_base_url_reference": "endpoint-ref:camara-qod-sandbox",
        "auth_contract_reference": "auth-contract:camara-qod-oauth",
        "secret_provider_reference": "secret-provider:customer-vault",
        "credential_reference": "credential-ref:camara-qod-test-client",
        "tls_policy_reference": "tls-policy:outbound-public-v1",
        "outbound_allowlist_reference": "allowlist:camara-qod-sandbox",
        "operator_approval_reference": "operator-approval:pending-live-proof",
        "support_owner_reference": "support-owner:integration-ops",
        "rotation_policy_reference": "rotation-policy:sandbox-client",
        "revocation_policy_reference": "revocation-policy:sandbox-client",
    }
    values.update(overrides)
    return CamaraQodOperatorSandboxReferenceSubmission(**values)


def test_intake_contract_is_reference_only_and_non_authoritative() -> None:
    contract = CAMARA_QOD_OPERATOR_SANDBOX_INTAKE_CONTRACT
    assert contract["environment"] == "sandbox"
    assert contract["reference_only"] is True
    assert contract["raw_endpoint_allowed"] is False
    assert contract["raw_credentials_allowed"] is False
    assert contract["network_io_allowed"] is False
    assert contract["provider_sandbox_proven"] is False
    assert contract["runtime_connector_approved"] is False
    assert contract["production_allowed"] is False
    assert len(contract["runtime_task_ids"]) == 5


def test_missing_submission_remains_pending_and_proves_nothing() -> None:
    result = assess_camara_qod_operator_sandbox_intake(None)
    assert result.status is CamaraQodOperatorSandboxIntakeStatus.PENDING_OPERATOR_INPUT
    assert result.references_complete is False
    assert len(result.missing_reference_names) == 11
    assert result.endpoint_registered is False
    assert result.credentials_resolved is False
    assert result.provider_network_proof is False
    assert result.provider_sandbox_proven is False
    assert result.runtime_connector_approved is False
    assert result.request_execution_allowed is False
    assert result.production_allowed is False


def test_complete_reference_submission_advances_only_to_review() -> None:
    result = assess_camara_qod_operator_sandbox_intake(_submission())
    assert result.status is (
        CamaraQodOperatorSandboxIntakeStatus.REFERENCES_RECEIVED_FOR_REVIEW
    )
    assert result.references_complete is True
    assert result.missing_reference_names == ()
    assert result.endpoint_registered is False
    assert result.credentials_resolved is False
    assert result.provider_network_proof is False
    assert result.provider_sandbox_proven is False
    assert result.runtime_connector_approved is False
    assert result.request_execution_allowed is False
    assert result.production_allowed is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("sandbox_base_url_reference", "https://sandbox.operator.example/qod"),
        ("credential_reference", "token=raw-secret"),
        ("credential_reference", "Bearer abc123"),
        ("secret_provider_reference", "client_secret=unsafe"),
        ("tls_policy_reference", "certificate=raw-material"),
    ],
)
def test_raw_endpoint_or_secret_material_is_rejected(field: str, value: str) -> None:
    with pytest.raises(ValueError, match="reference identifier, not raw material"):
        _submission(**{field: value})


def test_surrounding_whitespace_is_rejected() -> None:
    with pytest.raises(ValueError, match="surrounding whitespace"):
        _submission(operator_identity_reference=" operator:camara-qod-test ")


def test_safe_payload_contains_references_only_and_closed_authority() -> None:
    payload = camara_qod_operator_sandbox_intake_payload(_submission())
    assessment = payload["assessment"]
    assert assessment["references_complete"] is True
    assert assessment["provider_network_proof"] is False
    assert assessment["provider_sandbox_proven"] is False
    assert assessment["runtime_connector_approved"] is False
    assert assessment["request_execution_allowed"] is False
    assert assessment["production_allowed"] is False

    serialized = repr(payload).lower()
    assert "https://" not in serialized
    assert "bearer " not in serialized
    assert "client_secret=" not in serialized
    assert "api_key=" not in serialized
