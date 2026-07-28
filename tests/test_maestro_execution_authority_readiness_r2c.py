from dataclasses import FrozenInstanceError, fields

import pytest

from processual_api.billing.maestro_execution_authority import (
    MaestroExecutionAuthorityKind,
)
from processual_api.billing.maestro_execution_authority_readiness import (
    COMMERCIAL_ENFORCEMENT_ENABLED,
    DISCOVERY_ONLY,
    LLM_CONNECTION_POLICY,
    MEASUREMENT_EMISSION_ENABLED,
    PLATFORM_OWNED_LLM_KEYS_ALLOWED,
    RAW_PROMPTS_ALLOWED,
    RAW_RESPONSES_ALLOWED,
    RAW_SECRETS_ALLOWED,
    RUNTIME_INTEGRATION_ENABLED,
    MaestroExecutionAuthorityReadiness,
    MaestroExecutionAuthorityReadinessValidationError,
    MaestroReadinessCapabilityStatus,
)


def make_readiness(
    status: MaestroReadinessCapabilityStatus,
) -> MaestroExecutionAuthorityReadiness:
    return MaestroExecutionAuthorityReadiness(
        authority_kind=MaestroExecutionAuthorityKind.LLM_ADAPTER,
        execution_id=status,
        attempt_id=status,
        retry_ordinal=status,
        idempotency_key=status,
        start_event=status,
        completion_event=status,
        completion_outcomes=status,
        structured_usage=status,
        failure_ownership=status,
        production_classification=status,
        best_effort_observation=status,
        tenant_reference=status,
        credential_profile_reference=status,
    )


def test_r2c_remains_discovery_only() -> None:
    assert DISCOVERY_ONLY is True
    assert RUNTIME_INTEGRATION_ENABLED is False
    assert MEASUREMENT_EMISSION_ENABLED is False
    assert COMMERCIAL_ENFORCEMENT_ENABLED is False


def test_r2c_enforces_byok_only_boundary() -> None:
    assert LLM_CONNECTION_POLICY == "byok_only"
    assert PLATFORM_OWNED_LLM_KEYS_ALLOWED is False
    assert RAW_SECRETS_ALLOWED is False
    assert RAW_PROMPTS_ALLOWED is False
    assert RAW_RESPONSES_ALLOWED is False


def test_readiness_contract_is_frozen() -> None:
    readiness = make_readiness(MaestroReadinessCapabilityStatus.UNKNOWN)

    with pytest.raises(FrozenInstanceError):
        readiness.execution_id = (  # type: ignore[misc]
            MaestroReadinessCapabilityStatus.SUPPORTED
        )


@pytest.mark.parametrize(
    "status",
    [
        MaestroReadinessCapabilityStatus.UNKNOWN,
        MaestroReadinessCapabilityStatus.UNSUPPORTED,
        MaestroReadinessCapabilityStatus.SYNTHETIC_ONLY,
    ],
)
def test_non_supported_capabilities_fail_closed(
    status: MaestroReadinessCapabilityStatus,
) -> None:
    assert make_readiness(status).is_ready is False


def test_all_capabilities_must_be_supported() -> None:
    readiness = make_readiness(MaestroReadinessCapabilityStatus.SUPPORTED)

    assert readiness.is_ready is True


def test_invalid_capability_value_is_rejected() -> None:
    values = {
        field.name: MaestroReadinessCapabilityStatus.SUPPORTED
        for field in fields(MaestroExecutionAuthorityReadiness)
        if field.name != "authority_kind"
    }

    values["execution_id"] = "supported"

    with pytest.raises(MaestroExecutionAuthorityReadinessValidationError):
        MaestroExecutionAuthorityReadiness(
            authority_kind=MaestroExecutionAuthorityKind.LLM_ADAPTER,
            **values,
        )


def test_readiness_contract_has_no_secret_or_payload_fields() -> None:
    forbidden = {
        "api_key",
        "secret",
        "token",
        "authorization",
        "password",
        "cookie",
        "prompt",
        "response",
        "raw_request",
        "raw_response",
    }

    field_names = {field.name.lower() for field in fields(MaestroExecutionAuthorityReadiness)}

    assert field_names.isdisjoint(forbidden)


def test_one_missing_capability_prevents_readiness() -> None:
    readiness = MaestroExecutionAuthorityReadiness(
        authority_kind=MaestroExecutionAuthorityKind.LLM_ADAPTER,
        execution_id=MaestroReadinessCapabilityStatus.SUPPORTED,
        attempt_id=MaestroReadinessCapabilityStatus.SUPPORTED,
        retry_ordinal=MaestroReadinessCapabilityStatus.SUPPORTED,
        idempotency_key=MaestroReadinessCapabilityStatus.SUPPORTED,
        start_event=MaestroReadinessCapabilityStatus.SUPPORTED,
        completion_event=MaestroReadinessCapabilityStatus.SUPPORTED,
        completion_outcomes=MaestroReadinessCapabilityStatus.UNKNOWN,
        structured_usage=MaestroReadinessCapabilityStatus.SUPPORTED,
        failure_ownership=MaestroReadinessCapabilityStatus.SUPPORTED,
        production_classification=(MaestroReadinessCapabilityStatus.SUPPORTED),
        best_effort_observation=(MaestroReadinessCapabilityStatus.SUPPORTED),
        tenant_reference=MaestroReadinessCapabilityStatus.SUPPORTED,
        credential_profile_reference=(MaestroReadinessCapabilityStatus.SUPPORTED),
    )

    assert readiness.is_ready is False
