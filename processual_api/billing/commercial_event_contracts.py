"""Cross-domain commercial event and idempotency contracts.

The contracts in this module are authority-only. They do not persist events,
mutate commercial aggregates, or enable runtime commercial execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final, Protocol
from uuid import UUID

from processual_api.billing.commercial_state_machine import (
    CommercialAggregate,
    CommercialTransition,
    validate_commercial_transition,
)

COMMERCIAL_EVENT_CONTRACT_VERSION: Final = "2026-08-b2-commercial-event-v1"
COMMERCIAL_EVENT_STORAGE_ENABLED: Final = False
COMMERCIAL_IDEMPOTENCY_STORAGE_ENABLED: Final = False
APPEND_ONLY_COMMERCIAL_LEDGER_REQUIRED: Final = True
UNIQUE_COMMERCIAL_IDEMPOTENCY_REQUIRED: Final = True


@dataclass(frozen=True, slots=True)
class CommercialIdempotencyKey:
    aggregate: CommercialAggregate
    aggregate_id: UUID
    operation: str
    request_key: str

    def __post_init__(self) -> None:
        if not self.operation.strip():
            raise ValueError("operation must not be blank")
        if not self.request_key.strip():
            raise ValueError("request_key must not be blank")

    @property
    def canonical(self) -> str:
        operation = self.operation.strip().lower()
        request_key = self.request_key.strip()
        return f"{self.aggregate.value}:{self.aggregate_id}:{operation}:{request_key}"


@dataclass(frozen=True, slots=True)
class CommercialEvent:
    event_id: UUID
    aggregate: CommercialAggregate
    aggregate_id: UUID
    current_state: str
    next_state: str
    operation: str
    idempotency_key: CommercialIdempotencyKey
    occurred_at: datetime
    actor_reference: str
    evidence_reference: str
    payload_digest: str

    def __post_init__(self) -> None:
        if self.idempotency_key.aggregate is not self.aggregate:
            raise ValueError("idempotency aggregate must match event aggregate")
        if self.idempotency_key.aggregate_id != self.aggregate_id:
            raise ValueError("idempotency aggregate_id must match event aggregate_id")
        if self.idempotency_key.operation.strip().lower() != self.operation.strip().lower():
            raise ValueError("idempotency operation must match event operation")
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone aware")
        if not self.actor_reference.strip():
            raise ValueError("actor_reference must not be blank")
        if not self.evidence_reference.strip():
            raise ValueError("evidence_reference must not be blank")
        if not self.payload_digest.strip():
            raise ValueError("payload_digest must not be blank")

        validate_commercial_transition(
            CommercialTransition(
                aggregate=self.aggregate,
                current_state=self.current_state,
                next_state=self.next_state,
                operation=self.operation,
            )
        )


class CommercialEventRepository(Protocol):
    def get_by_idempotency_key(self, canonical_key: str) -> CommercialEvent | None: ...

    def append(self, event: CommercialEvent) -> None: ...

    def list_for_aggregate(
        self,
        aggregate: CommercialAggregate,
        aggregate_id: UUID,
    ) -> tuple[CommercialEvent, ...]: ...


def build_commercial_event_runtime_status() -> dict[str, bool | str]:
    return {
        "contract_version": COMMERCIAL_EVENT_CONTRACT_VERSION,
        "event_storage_enabled": COMMERCIAL_EVENT_STORAGE_ENABLED,
        "idempotency_storage_enabled": COMMERCIAL_IDEMPOTENCY_STORAGE_ENABLED,
        "append_only_ledger_required": APPEND_ONLY_COMMERCIAL_LEDGER_REQUIRED,
        "unique_idempotency_required": UNIQUE_COMMERCIAL_IDEMPOTENCY_REQUIRED,
    }


__all__ = [
    "APPEND_ONLY_COMMERCIAL_LEDGER_REQUIRED",
    "COMMERCIAL_EVENT_CONTRACT_VERSION",
    "COMMERCIAL_EVENT_STORAGE_ENABLED",
    "COMMERCIAL_IDEMPOTENCY_STORAGE_ENABLED",
    "UNIQUE_COMMERCIAL_IDEMPOTENCY_REQUIRED",
    "CommercialEvent",
    "CommercialEventRepository",
    "CommercialIdempotencyKey",
    "build_commercial_event_runtime_status",
]
