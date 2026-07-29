"""No-op Agent identity bridge contract for Maestro M1-R4.

The bridge accepts a reference-only Agent identity carrier and returns a
non-executing receipt. It does not import Agent Runtime, call ``run_agent``,
emit measurements, persist records, or authorize charging.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable

from processual_api.billing.maestro_agent_identity_carrier import (
    MaestroAgentExecutionIdentityCarrier,
)

AGENT_IDENTITY_BRIDGE_VERSION = "maestro-agent-identity-bridge-m1-r4"

DISCOVERY_ONLY = True
RUNTIME_INTEGRATION_ENABLED = False
AGENT_EXECUTION_ENABLED = False
BRIDGE_DISPATCH_ENABLED = False
MEASUREMENT_EMISSION_ENABLED = False
SHADOW_STORE_WRITES_ENABLED = False
COMMERCIAL_ENFORCEMENT_ENABLED = False
APPROVED_FOR_QUOTA = False
APPROVED_FOR_INVOICING = False
APPROVED_FOR_CHECKOUT = False
APPROVED_FOR_SETTLEMENT = False

LLM_CONNECTION_POLICY = "byok_only"
PLATFORM_OWNED_LLM_KEYS_ALLOWED = False
RAW_TASK_CONTENT_ALLOWED = False
RAW_SECRETS_ALLOWED = False
RAW_PROMPTS_ALLOWED = False
RAW_RESPONSES_ALLOWED = False
RAW_AGENT_OUTPUT_ALLOWED = False


class MaestroAgentIdentityBridgeValidationError(ValueError):
    """Raised when a bridge receipt is incomplete or unsafe."""


class MaestroAgentIdentityBridgeOutcome(StrEnum):
    NOOP_DISCONNECTED = "noop_disconnected"


@dataclass(frozen=True, slots=True)
class MaestroAgentIdentityBridgeReceipt:
    """Non-executing receipt returned by a bridge implementation."""

    outcome: MaestroAgentIdentityBridgeOutcome
    execution_id: str
    attempt_id: str
    agent_reference: str
    accepted_for_execution: bool = False
    measurement_emitted: bool = False
    persisted: bool = False

    def __post_init__(self) -> None:
        if not isinstance(
            self.outcome,
            MaestroAgentIdentityBridgeOutcome,
        ):
            raise MaestroAgentIdentityBridgeValidationError("outcome must be MaestroAgentIdentityBridgeOutcome")

        _require_identifier("execution_id", self.execution_id)
        _require_identifier("attempt_id", self.attempt_id)
        _require_identifier("agent_reference", self.agent_reference)

        for field_name in (
            "accepted_for_execution",
            "measurement_emitted",
            "persisted",
        ):
            value = getattr(self, field_name)

            if not isinstance(value, bool):
                raise MaestroAgentIdentityBridgeValidationError(f"{field_name} must be bool")

            if value:
                raise MaestroAgentIdentityBridgeValidationError(f"{field_name} must remain false in M1-R4")


@runtime_checkable
class MaestroAgentIdentityBridge(Protocol):
    """Pure bridge boundary for a future Agent Runtime integration."""

    def accept(
        self,
        carrier: MaestroAgentExecutionIdentityCarrier,
    ) -> MaestroAgentIdentityBridgeReceipt: ...


class NoOpMaestroAgentIdentityBridge:
    """Default disconnected bridge used until runtime integration is approved."""

    def accept(
        self,
        carrier: MaestroAgentExecutionIdentityCarrier,
    ) -> MaestroAgentIdentityBridgeReceipt:
        if not isinstance(
            carrier,
            MaestroAgentExecutionIdentityCarrier,
        ):
            raise MaestroAgentIdentityBridgeValidationError("carrier must be MaestroAgentExecutionIdentityCarrier")

        return MaestroAgentIdentityBridgeReceipt(
            outcome=MaestroAgentIdentityBridgeOutcome.NOOP_DISCONNECTED,
            execution_id=carrier.execution_id,
            attempt_id=carrier.attempt_id,
            agent_reference=carrier.agent_reference,
        )


def _require_identifier(name: str, value: object) -> None:
    if not isinstance(value, str):
        raise MaestroAgentIdentityBridgeValidationError(f"{name} must be str")

    if not value or len(value) > 128:
        raise MaestroAgentIdentityBridgeValidationError(f"{name} must contain between 1 and 128 characters")

    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:-")

    if any(character not in allowed for character in value):
        raise MaestroAgentIdentityBridgeValidationError(f"{name} contains unsupported characters")
