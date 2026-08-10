from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from processual_api.billing.commercial_event_contracts import (
    CommercialEvent,
    CommercialIdempotencyKey,
    build_commercial_event_runtime_status,
)
from processual_api.billing.commercial_state_machine import CommercialAggregate
from processual_api.billing.commercial_top_up_order_grant_contracts import TopUpOrderState


def _top_up_key(*, aggregate_id, operation: str = "confirm") -> CommercialIdempotencyKey:
    return CommercialIdempotencyKey(
        aggregate=CommercialAggregate.TOP_UP,
        aggregate_id=aggregate_id,
        operation=operation,
        request_key="request-123",
    )


def _top_up_event(*, operation: str = "confirm") -> CommercialEvent:
    aggregate_id = uuid4()
    return CommercialEvent(
        event_id=uuid4(),
        aggregate=CommercialAggregate.TOP_UP,
        aggregate_id=aggregate_id,
        current_state=TopUpOrderState.DRAFT.value,
        next_state=TopUpOrderState.AWAITING_CONFIRMATION.value,
        operation=operation,
        idempotency_key=_top_up_key(aggregate_id=aggregate_id, operation=operation),
        occurred_at=datetime.now(UTC),
        actor_reference="operator:test",
        evidence_reference="evidence:test",
        payload_digest="sha256:test",
    )


def test_idempotency_key_is_scoped_by_aggregate_operation_and_request() -> None:
    aggregate_id = uuid4()
    key = _top_up_key(aggregate_id=aggregate_id, operation=" Confirm ")

    assert key.canonical == f"top_up:{aggregate_id}:confirm:request-123"


def test_commercial_event_accepts_authorized_transition() -> None:
    event = _top_up_event()

    assert event.aggregate is CommercialAggregate.TOP_UP


def test_commercial_event_rejects_illegal_transition() -> None:
    aggregate_id = uuid4()

    with pytest.raises(ValueError, match="commercial transition is not allowed"):
        CommercialEvent(
            event_id=uuid4(),
            aggregate=CommercialAggregate.TOP_UP,
            aggregate_id=aggregate_id,
            current_state=TopUpOrderState.PAYMENT_PENDING.value,
            next_state=TopUpOrderState.GRANTED.value,
            operation="grant",
            idempotency_key=_top_up_key(aggregate_id=aggregate_id, operation="grant"),
            occurred_at=datetime.now(UTC),
            actor_reference="operator:test",
            evidence_reference="evidence:test",
            payload_digest="sha256:test",
        )


def test_commercial_event_rejects_mismatched_idempotency_scope() -> None:
    aggregate_id = uuid4()

    with pytest.raises(ValueError, match="aggregate_id must match"):
        CommercialEvent(
            event_id=uuid4(),
            aggregate=CommercialAggregate.TOP_UP,
            aggregate_id=aggregate_id,
            current_state=TopUpOrderState.DRAFT.value,
            next_state=TopUpOrderState.AWAITING_CONFIRMATION.value,
            operation="confirm",
            idempotency_key=_top_up_key(aggregate_id=uuid4()),
            occurred_at=datetime.now(UTC),
            actor_reference="operator:test",
            evidence_reference="evidence:test",
            payload_digest="sha256:test",
        )


def test_commercial_event_requires_timezone_aware_timestamp() -> None:
    aggregate_id = uuid4()

    with pytest.raises(ValueError, match="timezone aware"):
        CommercialEvent(
            event_id=uuid4(),
            aggregate=CommercialAggregate.TOP_UP,
            aggregate_id=aggregate_id,
            current_state=TopUpOrderState.DRAFT.value,
            next_state=TopUpOrderState.AWAITING_CONFIRMATION.value,
            operation="confirm",
            idempotency_key=_top_up_key(aggregate_id=aggregate_id),
            occurred_at=datetime.now(),
            actor_reference="operator:test",
            evidence_reference="evidence:test",
            payload_digest="sha256:test",
        )


def test_runtime_status_keeps_storage_disabled() -> None:
    status = build_commercial_event_runtime_status()

    assert status["event_storage_enabled"] is False
    assert status["idempotency_storage_enabled"] is False
    assert status["append_only_ledger_required"] is True
    assert status["unique_idempotency_required"] is True
