from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone

import pytest

from processual_api.billing.maestro_agent_identity_carrier import (
    AGENT_EXECUTION_ENABLED,
    APPROVED_FOR_CHECKOUT,
    APPROVED_FOR_INVOICING,
    APPROVED_FOR_QUOTA,
    APPROVED_FOR_SETTLEMENT,
    COMMERCIAL_ENFORCEMENT_ENABLED,
    DISCOVERY_ONLY,
    LLM_CONNECTION_POLICY,
    MEASUREMENT_EMISSION_ENABLED,
    PLATFORM_OWNED_LLM_KEYS_ALLOWED,
    RAW_AGENT_OUTPUT_ALLOWED,
    RAW_PROMPTS_ALLOWED,
    RAW_RESPONSES_ALLOWED,
    RAW_SECRETS_ALLOWED,
    RAW_TASK_CONTENT_ALLOWED,
    RUNTIME_INTEGRATION_ENABLED,
    SHADOW_STORE_WRITES_ENABLED,
    MaestroAgentExecutionIdentityCarrier,
    MaestroAgentIdentityCarrierValidationError,
)
from processual_api.billing.maestro_commercial_execution_identity import (
    MaestroCommercialExecutionIdentity,
)
from processual_api.billing.maestro_execution_authority import (
    MaestroExecutionAttemptContext,
    MaestroExecutionAuthorityKind,
)


def make_identity() -> MaestroCommercialExecutionIdentity:
    context = MaestroExecutionAttemptContext(
        execution_id="execution-001",
        attempt_id="attempt-001",
        authority_kind=MaestroExecutionAuthorityKind.AGENT_RUNTIME,
        started_at=datetime(2026, 7, 29, tzinfo=UTC),
        idempotency_key="maestro-agent-execution-001",
    )
    return MaestroCommercialExecutionIdentity(
        context=context,
        tenant_reference="tenant-reference-001",
        credential_profile_reference="customer-byok-profile-001",
        workload_family_id="agent.runtime_adapter",
    )


def make_carrier(**overrides):
    values = {
        "identity": make_identity(),
        "agent_reference": "agent-reference-001",
        "task_reference": "task-reference-001",
        "requested_at": datetime(2026, 7, 29, 8, 0, tzinfo=UTC),
        "correlation_reference": "correlation-reference-001",
    }
    values.update(overrides)
    return MaestroAgentExecutionIdentityCarrier(**values)


def test_m1_r3_remains_no_op_and_non_commercial() -> None:
    assert DISCOVERY_ONLY is True
    assert RUNTIME_INTEGRATION_ENABLED is False
    assert AGENT_EXECUTION_ENABLED is False
    assert MEASUREMENT_EMISSION_ENABLED is False
    assert SHADOW_STORE_WRITES_ENABLED is False
    assert COMMERCIAL_ENFORCEMENT_ENABLED is False
    assert APPROVED_FOR_QUOTA is False
    assert APPROVED_FOR_INVOICING is False
    assert APPROVED_FOR_CHECKOUT is False
    assert APPROVED_FOR_SETTLEMENT is False


def test_m1_r3_preserves_sensitive_payload_boundaries() -> None:
    assert LLM_CONNECTION_POLICY == "byok_only"
    assert PLATFORM_OWNED_LLM_KEYS_ALLOWED is False
    assert RAW_TASK_CONTENT_ALLOWED is False
    assert RAW_SECRETS_ALLOWED is False
    assert RAW_PROMPTS_ALLOWED is False
    assert RAW_RESPONSES_ALLOWED is False
    assert RAW_AGENT_OUTPUT_ALLOWED is False


def test_carrier_is_frozen() -> None:
    carrier = make_carrier()
    with pytest.raises(FrozenInstanceError):
        carrier.agent_reference = "changed"  # type: ignore[misc]


def test_carrier_exposes_composed_identity_references() -> None:
    carrier = make_carrier()
    assert carrier.execution_id == "execution-001"
    assert carrier.attempt_id == "attempt-001"
    assert carrier.tenant_reference == "tenant-reference-001"
    assert carrier.credential_profile_reference == "customer-byok-profile-001"
    assert carrier.workload_family_id == "agent.runtime_adapter"
    assert carrier.idempotency_key == "maestro-agent-execution-001"


def test_carrier_requires_commercial_identity() -> None:
    with pytest.raises(
        MaestroAgentIdentityCarrierValidationError,
        match="MaestroCommercialExecutionIdentity",
    ):
        make_carrier(identity=object())


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("agent_reference", ""),
        ("task_reference", ""),
        ("agent_reference", "raw task content with spaces"),
        ("task_reference", "secret=value"),
    ],
)
def test_carrier_requires_safe_reference_identifiers(
    field_name: str,
    value: str,
) -> None:
    with pytest.raises(
        MaestroAgentIdentityCarrierValidationError,
        match=field_name,
    ):
        make_carrier(**{field_name: value})


def test_carrier_requires_timezone_aware_requested_at() -> None:
    with pytest.raises(
        MaestroAgentIdentityCarrierValidationError,
        match="timezone-aware",
    ):
        make_carrier(requested_at=datetime(2026, 7, 29, 8, 0))


def test_carrier_requires_utc_requested_at() -> None:
    non_utc = datetime(
        2026,
        7,
        29,
        8,
        0,
        tzinfo=timezone(timedelta(hours=1)),
    )
    with pytest.raises(
        MaestroAgentIdentityCarrierValidationError,
        match="must use UTC",
    ):
        make_carrier(requested_at=non_utc)


def test_correlation_reference_is_optional() -> None:
    assert make_carrier(correlation_reference=None).correlation_reference is None


def test_correlation_reference_must_be_safe() -> None:
    with pytest.raises(
        MaestroAgentIdentityCarrierValidationError,
        match="correlation_reference",
    ):
        make_carrier(correlation_reference="raw correlation content")


def test_stable_carrier_key_is_reference_only() -> None:
    assert make_carrier().stable_carrier_key == (
        "tenant-reference-001",
        "execution-001",
        "attempt-001",
        "agent-reference-001",
    )


def test_reference_payload_contains_only_declared_references() -> None:
    assert make_carrier().to_reference_payload() == {
        "execution_id": "execution-001",
        "attempt_id": "attempt-001",
        "tenant_reference": "tenant-reference-001",
        "credential_profile_reference": "customer-byok-profile-001",
        "workload_family_id": "agent.runtime_adapter",
        "idempotency_key": "maestro-agent-execution-001",
        "agent_reference": "agent-reference-001",
        "task_reference": "task-reference-001",
        "requested_at": "2026-07-29T08:00:00+00:00",
        "correlation_reference": "correlation-reference-001",
    }


def test_replacing_identity_preserves_validation() -> None:
    updated = replace(
        make_carrier(),
        correlation_reference="correlation-reference-002",
    )
    assert updated.correlation_reference == "correlation-reference-002"
