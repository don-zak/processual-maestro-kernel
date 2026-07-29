from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime

import pytest

from processual_api.billing.maestro_commercial_execution_identity import (
    APPROVED_FOR_CHECKOUT,
    APPROVED_FOR_INVOICING,
    APPROVED_FOR_QUOTA,
    APPROVED_FOR_SETTLEMENT,
    COMMERCIAL_ENFORCEMENT_ENABLED,
    DISCOVERY_ONLY,
    LLM_CONNECTION_POLICY,
    MEASUREMENT_EMISSION_ENABLED,
    PLATFORM_OWNED_LLM_KEYS_ALLOWED,
    RAW_PROMPTS_ALLOWED,
    RAW_RESPONSES_ALLOWED,
    RAW_SECRETS_ALLOWED,
    RUNTIME_INTEGRATION_ENABLED,
    SHADOW_STORE_WRITES_ENABLED,
    MaestroCommercialExecutionIdentity,
    MaestroCommercialExecutionIdentityValidationError,
    MaestroCredentialOwnership,
)
from processual_api.billing.maestro_execution_authority import (
    MaestroExecutionAttemptContext,
    MaestroExecutionAuthorityKind,
)


def make_context(**overrides):
    values = {
        "execution_id": "execution-001",
        "attempt_id": "attempt-001",
        "authority_kind": MaestroExecutionAuthorityKind.AGENT_RUNTIME,
        "started_at": datetime(2026, 7, 29, tzinfo=UTC),
        "idempotency_key": "maestro-agent-execution-001",
    }
    values.update(overrides)
    return MaestroExecutionAttemptContext(**values)


def make_identity(**overrides):
    values = {
        "context": make_context(),
        "tenant_reference": "tenant-reference-001",
        "credential_profile_reference": "customer-byok-profile-001",
        "workload_family_id": "agent.runtime_adapter",
    }
    values.update(overrides)
    return MaestroCommercialExecutionIdentity(**values)


def test_m1_r2_remains_non_runtime_and_non_commercial() -> None:
    assert DISCOVERY_ONLY is True
    assert RUNTIME_INTEGRATION_ENABLED is False
    assert MEASUREMENT_EMISSION_ENABLED is False
    assert SHADOW_STORE_WRITES_ENABLED is False
    assert COMMERCIAL_ENFORCEMENT_ENABLED is False
    assert APPROVED_FOR_QUOTA is False
    assert APPROVED_FOR_INVOICING is False
    assert APPROVED_FOR_CHECKOUT is False
    assert APPROVED_FOR_SETTLEMENT is False


def test_m1_r2_preserves_byok_and_sensitive_payload_boundaries() -> None:
    assert LLM_CONNECTION_POLICY == "byok_only"
    assert PLATFORM_OWNED_LLM_KEYS_ALLOWED is False
    assert RAW_SECRETS_ALLOWED is False
    assert RAW_PROMPTS_ALLOWED is False
    assert RAW_RESPONSES_ALLOWED is False


def test_identity_is_frozen() -> None:
    identity = make_identity()
    with pytest.raises(FrozenInstanceError):
        identity.tenant_reference = "changed"  # type: ignore[misc]


def test_identity_exposes_existing_attempt_authority_fields() -> None:
    identity = make_identity()
    assert identity.execution_id == "execution-001"
    assert identity.attempt_id == "attempt-001"
    assert identity.authority_kind is MaestroExecutionAuthorityKind.AGENT_RUNTIME
    assert identity.retry_ordinal == 0
    assert identity.idempotency_key == "maestro-agent-execution-001"
    assert identity.parent_execution_id is None


def test_identity_requires_agent_runtime_in_m1_r2() -> None:
    with pytest.raises(
        MaestroCommercialExecutionIdentityValidationError,
        match="not approved",
    ):
        make_identity(
            context=make_context(
                authority_kind=MaestroExecutionAuthorityKind.LLM_ADAPTER
            )
        )


def test_identity_requires_idempotency_for_first_attempt() -> None:
    with pytest.raises(
        MaestroCommercialExecutionIdentityValidationError,
        match="requires idempotency_key",
    ):
        make_identity(context=make_context(idempotency_key=None))


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("tenant_reference", ""),
        ("credential_profile_reference", "raw secret value"),
        ("workload_family_id", ""),
    ],
)
def test_identity_requires_safe_references(field_name, value) -> None:
    with pytest.raises(MaestroCommercialExecutionIdentityValidationError):
        make_identity(**{field_name: value})


def test_identity_defaults_to_customer_byok() -> None:
    assert (
        make_identity().credential_ownership
        is MaestroCredentialOwnership.CUSTOMER_BYOK
    )


def test_identity_rejects_untyped_credential_ownership() -> None:
    with pytest.raises(
        MaestroCommercialExecutionIdentityValidationError,
        match="MaestroCredentialOwnership",
    ):
        replace(
            make_identity(),
            credential_ownership="customer_byok",  # type: ignore[arg-type]
        )


def test_stable_attempt_key_is_reference_only() -> None:
    assert make_identity().stable_attempt_key == (
        "tenant-reference-001",
        "execution-001",
        "attempt-001",
    )


def test_retry_identity_preserves_parent_and_idempotency() -> None:
    identity = make_identity(
        context=make_context(
            attempt_id="attempt-002",
            retry_ordinal=1,
            idempotency_key="maestro-agent-execution-001",
            parent_execution_id="execution-parent-001",
        )
    )
    assert identity.retry_ordinal == 1
    assert identity.idempotency_key == "maestro-agent-execution-001"
    assert identity.parent_execution_id == "execution-parent-001"
