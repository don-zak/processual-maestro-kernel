from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from processual_api.admin_marketplace.lemon_squeezy_inbox import (
    LemonSqueezyWebhookInboxEntry,
)
from processual_api.admin_marketplace.lemon_squeezy_inbox_lifecycle import (
    claim_lemon_squeezy_webhook,
    mark_lemon_squeezy_webhook_processed,
    mark_lemon_squeezy_webhook_rejected,
)
from processual_api.admin_marketplace.lemon_squeezy_webhooks import (
    LemonSqueezyWebhookError,
)


NOW = datetime(2026, 8, 5, 18, 0, tzinfo=timezone.utc)


def _entry(*, status: str = "received") -> LemonSqueezyWebhookInboxEntry:
    return LemonSqueezyWebhookInboxEntry(
        id=uuid.uuid4(),
        event_identity_hash="a" * 64,
        payload_digest="b" * 64,
        event_name="subscription_created",
        resource_type="subscriptions",
        external_resource_id="123",
        store_id="42",
        customer_ref="customer-1",
        order_ref="order-1",
        offer_ref="offer-1",
        test_mode=False,
        processing_status=status,
        attempt_count=0,
        received_at=NOW,
    )


def test_received_webhook_can_be_claimed_once() -> None:
    entry = _entry()

    claim_lemon_squeezy_webhook(entry, claimed_at=NOW + timedelta(seconds=1))

    assert entry.processing_status == "processing"
    assert entry.attempt_count == 1
    assert entry.claimed_at == NOW + timedelta(seconds=1)
    assert entry.last_error_code is None

    with pytest.raises(LemonSqueezyWebhookError):
        claim_lemon_squeezy_webhook(entry, claimed_at=NOW + timedelta(seconds=2))


def test_processed_transition_requires_claim_and_is_idempotent_after_success() -> None:
    entry = _entry()

    with pytest.raises(LemonSqueezyWebhookError):
        mark_lemon_squeezy_webhook_processed(entry, processed_at=NOW)

    claim_lemon_squeezy_webhook(entry, claimed_at=NOW + timedelta(seconds=1))
    mark_lemon_squeezy_webhook_processed(
        entry,
        processed_at=NOW + timedelta(seconds=2),
    )

    assert entry.processing_status == "processed"
    assert entry.processed_at == NOW + timedelta(seconds=2)
    assert entry.rejected_at is None
    assert entry.last_error_code is None

    mark_lemon_squeezy_webhook_processed(
        entry,
        processed_at=NOW + timedelta(days=1),
    )
    assert entry.processed_at == NOW + timedelta(seconds=2)


def test_rejected_transition_requires_claim_and_stable_error_code() -> None:
    entry = _entry()

    with pytest.raises(LemonSqueezyWebhookError):
        mark_lemon_squeezy_webhook_rejected(
            entry,
            error_code="binding_mismatch",
            rejected_at=NOW,
        )

    claim_lemon_squeezy_webhook(entry, claimed_at=NOW + timedelta(seconds=1))
    mark_lemon_squeezy_webhook_rejected(
        entry,
        error_code="BINDING_MISMATCH",
        rejected_at=NOW + timedelta(seconds=2),
    )

    assert entry.processing_status == "rejected"
    assert entry.rejected_at == NOW + timedelta(seconds=2)
    assert entry.processed_at is None
    assert entry.last_error_code == "binding_mismatch"

    mark_lemon_squeezy_webhook_rejected(
        entry,
        error_code="binding_mismatch",
        rejected_at=NOW + timedelta(days=1),
    )
    assert entry.rejected_at == NOW + timedelta(seconds=2)

    with pytest.raises(LemonSqueezyWebhookError):
        mark_lemon_squeezy_webhook_rejected(
            entry,
            error_code="different_reason",
            rejected_at=NOW + timedelta(days=1),
        )


def test_terminal_timestamp_cannot_precede_claim() -> None:
    entry = _entry()
    claim_lemon_squeezy_webhook(entry, claimed_at=NOW + timedelta(seconds=10))

    with pytest.raises(LemonSqueezyWebhookError):
        mark_lemon_squeezy_webhook_processed(
            entry,
            processed_at=NOW + timedelta(seconds=9),
        )

    with pytest.raises(LemonSqueezyWebhookError):
        mark_lemon_squeezy_webhook_rejected(
            entry,
            error_code="processor_failed",
            rejected_at=NOW + timedelta(seconds=9),
        )


def test_naive_lifecycle_timestamps_are_rejected() -> None:
    entry = _entry()

    with pytest.raises(LemonSqueezyWebhookError):
        claim_lemon_squeezy_webhook(
            entry,
            claimed_at=datetime(2026, 8, 5, 18, 0),
        )


def test_invalid_error_codes_are_rejected_without_mutating_entry() -> None:
    entry = _entry()
    claim_lemon_squeezy_webhook(entry, claimed_at=NOW + timedelta(seconds=1))

    with pytest.raises(LemonSqueezyWebhookError):
        mark_lemon_squeezy_webhook_rejected(
            entry,
            error_code="contains spaces",
            rejected_at=NOW + timedelta(seconds=2),
        )

    assert entry.processing_status == "processing"
    assert entry.rejected_at is None
    assert entry.last_error_code is None


def test_inconsistent_existing_timestamps_fail_closed() -> None:
    entry = _entry()
    entry.processed_at = NOW

    with pytest.raises(LemonSqueezyWebhookError):
        claim_lemon_squeezy_webhook(entry, claimed_at=NOW + timedelta(seconds=1))
