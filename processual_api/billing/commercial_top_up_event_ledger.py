"""Transactional commercial-event ledger authority for Top-up execution.

The ledger port is designed to be enlisted in the same unit of work as payment,
grant, order-state, and audit writes. This module does not provide storage or
commit transactions itself and therefore cannot enable production execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Protocol

from processual_api.billing.commercial_event_contracts import CommercialEvent
from processual_api.billing.commercial_top_up_transition_authority import (
    validate_top_up_transition_chain,
)

TOP_UP_EVENT_LEDGER_VERSION: Final = "2026-08-b2-top-up-event-ledger-v1"
TOP_UP_EVENT_LEDGER_STORAGE_ENABLED: Final = False
ATOMIC_TOP_UP_EVENT_LEDGER_REQUIRED: Final = True


class TopUpEventLedgerConflictError(RuntimeError):
    """Raised when a replay does not match the already recorded event."""


class TopUpEventLedgerRepository(Protocol):
    async def get_by_idempotency_key(
        self,
        canonical_key: str,
    ) -> CommercialEvent | None: ...

    def append(self, event: CommercialEvent) -> None: ...


@dataclass(frozen=True, slots=True)
class TopUpEventLedgerStageResult:
    appended: tuple[CommercialEvent, ...]
    replayed: tuple[CommercialEvent, ...]

    @property
    def mutated(self) -> bool:
        return bool(self.appended)


def _same_event(left: CommercialEvent, right: CommercialEvent) -> bool:
    return (
        left.event_id == right.event_id
        and left.aggregate is right.aggregate
        and left.aggregate_id == right.aggregate_id
        and left.current_state == right.current_state
        and left.next_state == right.next_state
        and left.operation == right.operation
        and left.idempotency_key.canonical == right.idempotency_key.canonical
        and left.actor_reference == right.actor_reference
        and left.evidence_reference == right.evidence_reference
        and left.payload_digest == right.payload_digest
    )


async def stage_top_up_events(
    *,
    repository: TopUpEventLedgerRepository,
    events: tuple[CommercialEvent, ...],
) -> TopUpEventLedgerStageResult:
    """Stage an authoritative chain, failing closed on partial/conflicting replay."""

    validate_top_up_transition_chain(events)
    appended: list[CommercialEvent] = []
    replayed: list[CommercialEvent] = []
    seen_new_event = False

    for event in events:
        existing = await repository.get_by_idempotency_key(event.idempotency_key.canonical)
        if existing is None:
            if replayed:
                raise TopUpEventLedgerConflictError(
                    "top-up event chain is partially replayed; atomic ledger is incomplete"
                )
            seen_new_event = True
            repository.append(event)
            appended.append(event)
            continue

        if seen_new_event:
            raise TopUpEventLedgerConflictError(
                "top-up event chain mixes new events with an existing suffix"
            )
        if not _same_event(existing, event):
            raise TopUpEventLedgerConflictError(
                "top-up event idempotency key conflicts with existing event"
            )
        replayed.append(existing)

    return TopUpEventLedgerStageResult(
        appended=tuple(appended),
        replayed=tuple(replayed),
    )


def build_top_up_event_ledger_status() -> dict[str, bool | str]:
    return {
        "version": TOP_UP_EVENT_LEDGER_VERSION,
        "storage_enabled": TOP_UP_EVENT_LEDGER_STORAGE_ENABLED,
        "atomic_ledger_required": ATOMIC_TOP_UP_EVENT_LEDGER_REQUIRED,
        "partial_replay_fails_closed": True,
        "conflicting_replay_fails_closed": True,
    }


__all__ = [
    "ATOMIC_TOP_UP_EVENT_LEDGER_REQUIRED",
    "TOP_UP_EVENT_LEDGER_STORAGE_ENABLED",
    "TOP_UP_EVENT_LEDGER_VERSION",
    "TopUpEventLedgerConflictError",
    "TopUpEventLedgerRepository",
    "TopUpEventLedgerStageResult",
    "build_top_up_event_ledger_status",
    "stage_top_up_events",
]
