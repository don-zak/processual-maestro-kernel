from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from processual_api.billing.commercial_state_machine import CommercialAggregate
from processual_api.billing.commercial_top_up_transition_authority import (
    TopUpTransitionEvidence,
    build_top_up_transition_authority_status,
    build_verified_payment_grant_events,
    validate_top_up_transition_chain,
)


def evidence() -> TopUpTransitionEvidence:
    return TopUpTransitionEvidence(
        order_id=uuid.UUID("b10662c7-50de-4f93-aa31-bce16ab541f0"),
        provider_reference="provider-payment-001",
        actor_reference="payment-verifier:test",
        evidence_reference="audit://payment/001",
        occurred_at=datetime(2026, 8, 10, 10, 30, tzinfo=UTC),
        payment_payload_digest="payment-digest-001",
        grant_payload_digest="grant-digest-001",
    )


def test_verified_payment_grant_path_is_explicit_and_gap_free() -> None:
    events = build_verified_payment_grant_events(evidence())

    assert [(event.current_state, event.next_state) for event in events] == [
        ("awaiting_payment", "payment_pending"),
        ("payment_pending", "payment_verified"),
        ("payment_verified", "grant_pending"),
        ("grant_pending", "granted"),
    ]
    assert all(event.aggregate is CommercialAggregate.TOP_UP for event in events)
    validate_top_up_transition_chain(events)


def test_replay_builds_same_event_ids_and_idempotency_keys() -> None:
    first = build_verified_payment_grant_events(evidence())
    second = build_verified_payment_grant_events(evidence())

    assert [event.event_id for event in first] == [event.event_id for event in second]
    assert [event.idempotency_key.canonical for event in first] == [
        event.idempotency_key.canonical for event in second
    ]


def test_payload_change_changes_only_relevant_idempotency_scope() -> None:
    first = build_verified_payment_grant_events(evidence())
    changed = TopUpTransitionEvidence(
        order_id=evidence().order_id,
        provider_reference=evidence().provider_reference,
        actor_reference=evidence().actor_reference,
        evidence_reference=evidence().evidence_reference,
        occurred_at=evidence().occurred_at,
        payment_payload_digest="payment-digest-CHANGED",
        grant_payload_digest=evidence().grant_payload_digest,
    )
    second = build_verified_payment_grant_events(changed)

    assert [item.idempotency_key.canonical for item in first[:2]] != [
        item.idempotency_key.canonical for item in second[:2]
    ]
    assert [item.idempotency_key.canonical for item in first[2:]] == [
        item.idempotency_key.canonical for item in second[2:]
    ]


def test_chain_validator_rejects_state_gap() -> None:
    events = build_verified_payment_grant_events(evidence())

    with pytest.raises(ValueError, match="state gap"):
        validate_top_up_transition_chain((events[0], events[2]))


def test_naive_timestamp_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone aware"):
        TopUpTransitionEvidence(
            order_id=uuid.uuid4(),
            provider_reference="provider-payment-001",
            actor_reference="payment-verifier:test",
            evidence_reference="audit://payment/001",
            occurred_at=datetime(2026, 8, 10, 10, 30),
            payment_payload_digest="payment-digest-001",
            grant_payload_digest="grant-digest-001",
        )


def test_transition_authority_runtime_remains_storage_disabled() -> None:
    status = build_top_up_transition_authority_status()

    assert status["event_persistence_enabled"] is False
    assert status["deterministic_event_ids"] is True
    assert status["canonical_idempotency_keys"] is True
    assert status["explicit_transition_chain_required"] is True
