from datetime import UTC, datetime
from uuid import uuid4

import pytest

from processual_api.billing.commercial_event_contracts import CommercialEvent
from processual_api.billing.commercial_top_up_event_ledger import (
    TopUpEventLedgerConflictError,
    build_top_up_event_ledger_status,
    stage_top_up_events,
)
from processual_api.billing.commercial_top_up_transition_authority import (
    TopUpTransitionEvidence,
    build_verified_payment_grant_events,
)


class FakeTopUpEventLedgerRepository:
    def __init__(self) -> None:
        self.items: dict[str, CommercialEvent] = {}
        self.appended: list[CommercialEvent] = []

    async def get_by_idempotency_key(self, canonical_key: str) -> CommercialEvent | None:
        return self.items.get(canonical_key)

    def append(self, event: CommercialEvent) -> None:
        self.items[event.idempotency_key.canonical] = event
        self.appended.append(event)


def _events(*, payment_digest: str = "sha256:payment", grant_digest: str = "sha256:grant") -> tuple[CommercialEvent, ...]:
    return build_verified_payment_grant_events(
        TopUpTransitionEvidence(
            order_id=uuid4(),
            provider_reference="provider-payment-001",
            actor_reference="payment-verifier:test",
            evidence_reference="audit://payment/001",
            occurred_at=datetime(2026, 8, 10, 10, 30, tzinfo=UTC),
            payment_payload_digest=payment_digest,
            grant_payload_digest=grant_digest,
        )
    )


@pytest.mark.asyncio
async def test_fresh_chain_appends_all_events_once() -> None:
    repository = FakeTopUpEventLedgerRepository()
    events = _events()

    result = await stage_top_up_events(repository=repository, events=events)

    assert result.mutated is True
    assert result.appended == events
    assert result.replayed == ()
    assert repository.appended == list(events)


@pytest.mark.asyncio
async def test_full_replay_is_idempotent_without_second_append() -> None:
    repository = FakeTopUpEventLedgerRepository()
    events = _events()
    await stage_top_up_events(repository=repository, events=events)

    replay = await stage_top_up_events(repository=repository, events=events)

    assert replay.mutated is False
    assert replay.appended == ()
    assert replay.replayed == events
    assert repository.appended == list(events)


@pytest.mark.asyncio
async def test_partial_replay_fails_closed_before_appending_new_suffix() -> None:
    repository = FakeTopUpEventLedgerRepository()
    events = _events()
    repository.items[events[0].idempotency_key.canonical] = events[0]

    with pytest.raises(TopUpEventLedgerConflictError, match="partially replayed"):
        await stage_top_up_events(repository=repository, events=events)

    assert repository.appended == []


@pytest.mark.asyncio
async def test_conflicting_replay_fails_closed() -> None:
    repository = FakeTopUpEventLedgerRepository()
    events = _events()
    conflicting = _events(payment_digest="sha256:different")
    existing = CommercialEvent(
        event_id=events[0].event_id,
        aggregate=events[0].aggregate,
        aggregate_id=events[0].aggregate_id,
        current_state=events[0].current_state,
        next_state=events[0].next_state,
        operation=events[0].operation,
        idempotency_key=events[0].idempotency_key,
        occurred_at=events[0].occurred_at,
        actor_reference=events[0].actor_reference,
        evidence_reference=events[0].evidence_reference,
        payload_digest=conflicting[0].payload_digest,
    )
    repository.items[events[0].idempotency_key.canonical] = existing

    with pytest.raises(TopUpEventLedgerConflictError, match="conflicts"):
        await stage_top_up_events(repository=repository, events=events)

    assert repository.appended == []


def test_runtime_storage_remains_disabled() -> None:
    status = build_top_up_event_ledger_status()

    assert status["storage_enabled"] is False
    assert status["atomic_ledger_required"] is True
    assert status["partial_replay_fails_closed"] is True
    assert status["conflicting_replay_fails_closed"] is True
