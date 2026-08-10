"""Authority adapter between top-up execution and the commercial event ledger.

This module derives the explicit authoritative transition path for a verified
Top-up payment and grant. It does not persist events, mutate an order, call a
provider, or enable commercial execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Final
from uuid import UUID, uuid5

from processual_api.billing.commercial_event_contracts import (
    CommercialEvent,
    CommercialIdempotencyKey,
)
from processual_api.billing.commercial_state_machine import CommercialAggregate
from processual_api.billing.commercial_top_up_order_grant_contracts import TopUpOrderState

TOP_UP_TRANSITION_AUTHORITY_VERSION: Final = "2026-08-b2-top-up-transition-authority-v1"
TOP_UP_TRANSITION_EVENT_PERSISTENCE_ENABLED: Final = False
_EVENT_NAMESPACE: Final = UUID("f264367b-3109-4ad3-af87-d59e3cf8ca43")


@dataclass(frozen=True, slots=True)
class TopUpTransitionEvidence:
    order_id: UUID
    provider_reference: str
    actor_reference: str
    evidence_reference: str
    occurred_at: datetime
    payment_payload_digest: str
    grant_payload_digest: str

    def __post_init__(self) -> None:
        if not self.provider_reference.strip():
            raise ValueError("provider_reference must not be blank")
        if not self.actor_reference.strip():
            raise ValueError("actor_reference must not be blank")
        if not self.evidence_reference.strip():
            raise ValueError("evidence_reference must not be blank")
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone aware")
        if not self.payment_payload_digest.strip():
            raise ValueError("payment_payload_digest must not be blank")
        if not self.grant_payload_digest.strip():
            raise ValueError("grant_payload_digest must not be blank")


def _event_id(canonical_key: str, current_state: str, next_state: str) -> UUID:
    return uuid5(_EVENT_NAMESPACE, f"{canonical_key}:{current_state}->{next_state}")


def _digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def build_verified_payment_grant_events(
    evidence: TopUpTransitionEvidence,
) -> tuple[CommercialEvent, ...]:
    """Build the deterministic authoritative path from payment wait to grant."""

    steps = (
        (
            TopUpOrderState.AWAITING_PAYMENT.value,
            TopUpOrderState.PAYMENT_PENDING.value,
            "record_payment",
            evidence.payment_payload_digest,
        ),
        (
            TopUpOrderState.PAYMENT_PENDING.value,
            TopUpOrderState.PAYMENT_VERIFIED.value,
            "verify_payment",
            evidence.payment_payload_digest,
        ),
        (
            TopUpOrderState.PAYMENT_VERIFIED.value,
            TopUpOrderState.GRANT_PENDING.value,
            "request_grant",
            evidence.grant_payload_digest,
        ),
        (
            TopUpOrderState.GRANT_PENDING.value,
            TopUpOrderState.GRANTED.value,
            "apply_grant",
            evidence.grant_payload_digest,
        ),
    )

    events: list[CommercialEvent] = []
    for current_state, next_state, operation, payload_digest in steps:
        request_key = _digest(
            f"{evidence.provider_reference}:{operation}:{payload_digest}"
        )
        idempotency_key = CommercialIdempotencyKey(
            aggregate=CommercialAggregate.TOP_UP,
            aggregate_id=evidence.order_id,
            operation=operation,
            request_key=request_key,
        )
        events.append(
            CommercialEvent(
                event_id=_event_id(idempotency_key.canonical, current_state, next_state),
                aggregate=CommercialAggregate.TOP_UP,
                aggregate_id=evidence.order_id,
                current_state=current_state,
                next_state=next_state,
                operation=operation,
                idempotency_key=idempotency_key,
                occurred_at=evidence.occurred_at,
                actor_reference=evidence.actor_reference,
                evidence_reference=evidence.evidence_reference,
                payload_digest=payload_digest,
            )
        )
    return tuple(events)


def validate_top_up_transition_chain(events: tuple[CommercialEvent, ...]) -> None:
    if not events:
        raise ValueError("top-up transition chain must not be empty")
    for previous, current in zip(events, events[1:], strict=False):
        if previous.aggregate is not CommercialAggregate.TOP_UP:
            raise ValueError("top-up transition chain contains another aggregate")
        if previous.aggregate_id != current.aggregate_id:
            raise ValueError("top-up transition chain changes aggregate_id")
        if previous.next_state != current.current_state:
            raise ValueError("top-up transition chain contains a state gap")
    if events[-1].aggregate is not CommercialAggregate.TOP_UP:
        raise ValueError("top-up transition chain contains another aggregate")


def build_top_up_transition_authority_status() -> dict[str, bool | str]:
    return {
        "version": TOP_UP_TRANSITION_AUTHORITY_VERSION,
        "event_persistence_enabled": TOP_UP_TRANSITION_EVENT_PERSISTENCE_ENABLED,
        "deterministic_event_ids": True,
        "canonical_idempotency_keys": True,
        "explicit_transition_chain_required": True,
    }


__all__ = [
    "TOP_UP_TRANSITION_AUTHORITY_VERSION",
    "TOP_UP_TRANSITION_EVENT_PERSISTENCE_ENABLED",
    "TopUpTransitionEvidence",
    "build_top_up_transition_authority_status",
    "build_verified_payment_grant_events",
    "validate_top_up_transition_chain",
]
