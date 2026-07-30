"""Observe-only commercial runtime telemetry contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum
from typing import Final

COMMERCIAL_OBSERVE_ONLY_VERSION: Final = "2026-07-group2-commercial-observe-only-v1"
COMMERCIAL_OBSERVE_ONLY_STATUS: Final = "draft_review"
COMMERCIAL_OBSERVE_ONLY_ENABLED: Final = False
COMMERCIAL_RUNTIME_WRITES_ENABLED: Final = False
COMMERCIAL_QUOTA_ENFORCEMENT_ENABLED: Final = False
COMMERCIAL_LOAD_SHEDDING_ENABLED: Final = False
COMMERCIAL_AUTOMATIC_ACTIVATION_ENABLED: Final = False


class CommercialObservationKind(StrEnum):
    CHECKOUT_STATE = "checkout_state"
    PAYMENT_EVIDENCE = "payment_evidence"
    ACTIVATION_DECISION = "activation_decision"
    ENTITLEMENT_BALANCE = "entitlement_balance"
    RESERVATION_LIFECYCLE = "reservation_lifecycle"
    RECONCILIATION_MISMATCH = "reconciliation_mismatch"
    ADAPTIVE_CAPACITY = "adaptive_capacity"


@dataclass(frozen=True, slots=True)
class CommercialObservation:
    kind: CommercialObservationKind
    tenant_reference: str
    subscription_reference: str | None
    correlation_reference: str
    observed_at: datetime
    state: str
    metric_value: int | float | None
    sensitive_payload_included: bool = False

    def __post_init__(self) -> None:
        if not self.tenant_reference.strip():
            raise ValueError("tenant_reference must not be blank")
        if not self.correlation_reference.strip():
            raise ValueError("correlation_reference must not be blank")
        if not self.state.strip():
            raise ValueError("state must not be blank")
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if self.sensitive_payload_included:
            raise ValueError("observe-only telemetry must exclude sensitive payloads")

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["kind"] = self.kind.value
        return payload


@dataclass(frozen=True, slots=True)
class CommercialObserveOnlyDecision:
    recorded: bool
    enforcement_applied: bool
    state_mutated: bool
    notification_required: bool
    reason: str

    def __post_init__(self) -> None:
        if self.enforcement_applied:
            raise ValueError("observe-only runtime must not enforce commercial limits")
        if self.state_mutated:
            raise ValueError("observe-only runtime must not mutate commercial state")


def evaluate_observation(
    observation: CommercialObservation,
) -> CommercialObserveOnlyDecision:
    notify = observation.kind is CommercialObservationKind.RECONCILIATION_MISMATCH
    return CommercialObserveOnlyDecision(
        recorded=COMMERCIAL_OBSERVE_ONLY_ENABLED,
        enforcement_applied=False,
        state_mutated=False,
        notification_required=notify,
        reason=("observe-only decision; runtime writes and enforcement remain disabled"),
    )


def build_commercial_observe_only_status() -> dict[str, object]:
    return {
        "version": COMMERCIAL_OBSERVE_ONLY_VERSION,
        "status": COMMERCIAL_OBSERVE_ONLY_STATUS,
        "enabled": COMMERCIAL_OBSERVE_ONLY_ENABLED,
        "runtime_writes_enabled": COMMERCIAL_RUNTIME_WRITES_ENABLED,
        "quota_enforcement_enabled": (COMMERCIAL_QUOTA_ENFORCEMENT_ENABLED),
        "load_shedding_enabled": (COMMERCIAL_LOAD_SHEDDING_ENABLED),
        "automatic_activation_enabled": (COMMERCIAL_AUTOMATIC_ACTIVATION_ENABLED),
        "sensitive_payloads_allowed": False,
        "provider_secrets_allowed": False,
        "ledger_mutation_allowed": False,
        "reconciliation_auto_repair_allowed": False,
    }


__all__ = [
    "COMMERCIAL_AUTOMATIC_ACTIVATION_ENABLED",
    "COMMERCIAL_LOAD_SHEDDING_ENABLED",
    "COMMERCIAL_OBSERVE_ONLY_ENABLED",
    "COMMERCIAL_OBSERVE_ONLY_STATUS",
    "COMMERCIAL_OBSERVE_ONLY_VERSION",
    "COMMERCIAL_QUOTA_ENFORCEMENT_ENABLED",
    "COMMERCIAL_RUNTIME_WRITES_ENABLED",
    "CommercialObservation",
    "CommercialObservationKind",
    "CommercialObserveOnlyDecision",
    "build_commercial_observe_only_status",
    "evaluate_observation",
]
