from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime

import pytest

from processual_api.billing.maestro_agent_identity_bridge import (
    AGENT_EXECUTION_ENABLED,
    APPROVED_FOR_CHECKOUT,
    APPROVED_FOR_INVOICING,
    APPROVED_FOR_QUOTA,
    APPROVED_FOR_SETTLEMENT,
    BRIDGE_DISPATCH_ENABLED,
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
    MaestroAgentIdentityBridge,
    MaestroAgentIdentityBridgeOutcome,
    MaestroAgentIdentityBridgeReceipt,
    MaestroAgentIdentityBridgeValidationError,
    NoOpMaestroAgentIdentityBridge,
)
from processual_api.billing.maestro_agent_identity_carrier import (
    MaestroAgentExecutionIdentityCarrier,
)
from processual_api.billing.maestro_commercial_execution_identity import (
    MaestroCommercialExecutionIdentity,
)
from processual_api.billing.maestro_execution_authority import (
    MaestroExecutionAttemptContext,
    MaestroExecutionAuthorityKind,
)


def make_carrier() -> MaestroAgentExecutionIdentityCarrier:
    context = MaestroExecutionAttemptContext(
        execution_id="execution-001",
        attempt_id="attempt-001",
        authority_kind=MaestroExecutionAuthorityKind.AGENT_RUNTIME,
        started_at=datetime(2026, 7, 29, tzinfo=UTC),
        idempotency_key="maestro-agent-execution-001",
    )
    identity = MaestroCommercialExecutionIdentity(
        context=context,
        tenant_reference="tenant-reference-001",
        credential_profile_reference="customer-byok-profile-001",
        workload_family_id="agent.runtime_adapter",
    )
    return MaestroAgentExecutionIdentityCarrier(
        identity=identity,
        agent_reference="agent-reference-001",
        task_reference="task-reference-001",
        requested_at=datetime(2026, 7, 29, 9, 0, tzinfo=UTC),
    )


def test_m1_r4_remains_disconnected_and_non_commercial() -> None:
    assert DISCOVERY_ONLY is True
    assert RUNTIME_INTEGRATION_ENABLED is False
    assert AGENT_EXECUTION_ENABLED is False
    assert BRIDGE_DISPATCH_ENABLED is False
    assert MEASUREMENT_EMISSION_ENABLED is False
    assert SHADOW_STORE_WRITES_ENABLED is False
    assert COMMERCIAL_ENFORCEMENT_ENABLED is False
    assert APPROVED_FOR_QUOTA is False
    assert APPROVED_FOR_INVOICING is False
    assert APPROVED_FOR_CHECKOUT is False
    assert APPROVED_FOR_SETTLEMENT is False


def test_m1_r4_preserves_sensitive_payload_boundaries() -> None:
    assert LLM_CONNECTION_POLICY == "byok_only"
    assert PLATFORM_OWNED_LLM_KEYS_ALLOWED is False
    assert RAW_TASK_CONTENT_ALLOWED is False
    assert RAW_SECRETS_ALLOWED is False
    assert RAW_PROMPTS_ALLOWED is False
    assert RAW_RESPONSES_ALLOWED is False
    assert RAW_AGENT_OUTPUT_ALLOWED is False


def test_noop_bridge_satisfies_protocol() -> None:
    bridge = NoOpMaestroAgentIdentityBridge()

    assert isinstance(bridge, MaestroAgentIdentityBridge)


def test_noop_bridge_returns_disconnected_receipt() -> None:
    receipt = NoOpMaestroAgentIdentityBridge().accept(make_carrier())

    assert receipt == MaestroAgentIdentityBridgeReceipt(
        outcome=MaestroAgentIdentityBridgeOutcome.NOOP_DISCONNECTED,
        execution_id="execution-001",
        attempt_id="attempt-001",
        agent_reference="agent-reference-001",
    )


def test_receipt_is_frozen() -> None:
    receipt = NoOpMaestroAgentIdentityBridge().accept(make_carrier())

    with pytest.raises(FrozenInstanceError):
        receipt.persisted = True  # type: ignore[misc]


@pytest.mark.parametrize(
    "field_name",
    [
        "accepted_for_execution",
        "measurement_emitted",
        "persisted",
    ],
)
def test_receipt_rejects_enabled_side_effect_flags(
    field_name: str,
) -> None:
    receipt = NoOpMaestroAgentIdentityBridge().accept(make_carrier())

    with pytest.raises(
        MaestroAgentIdentityBridgeValidationError,
        match=f"{field_name} must remain false",
    ):
        replace(receipt, **{field_name: True})


def test_receipt_rejects_untyped_outcome() -> None:
    receipt = NoOpMaestroAgentIdentityBridge().accept(make_carrier())

    with pytest.raises(
        MaestroAgentIdentityBridgeValidationError,
        match="MaestroAgentIdentityBridgeOutcome",
    ):
        replace(receipt, outcome="noop_disconnected")  # type: ignore[arg-type]


def test_receipt_rejects_unsafe_reference() -> None:
    receipt = NoOpMaestroAgentIdentityBridge().accept(make_carrier())

    with pytest.raises(
        MaestroAgentIdentityBridgeValidationError,
        match="agent_reference",
    ):
        replace(receipt, agent_reference="raw agent content")


def test_noop_bridge_rejects_non_carrier() -> None:
    with pytest.raises(
        MaestroAgentIdentityBridgeValidationError,
        match="MaestroAgentExecutionIdentityCarrier",
    ):
        NoOpMaestroAgentIdentityBridge().accept(object())  # type: ignore[arg-type]


def test_repeated_accept_is_deterministic() -> None:
    bridge = NoOpMaestroAgentIdentityBridge()
    carrier = make_carrier()

    assert bridge.accept(carrier) == bridge.accept(carrier)
