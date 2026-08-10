from __future__ import annotations

from copy import deepcopy
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


def _entry() -> LemonSqueezyWebhookInboxEntry:
    return LemonSqueezyWebhookInboxEntry(
        id=__import__("uuid").uuid4(),
        event_identity_hash="a" * 64,
        payload_digest="b" * 64,
        event_name="subscription_updated",
        resource_type="subscriptions",
        external_resource_id="123",
        store_id="42",
        customer_ref="customer-1",
        order_ref="order-1",
        offer_ref="offer-1",
        test_mode=False,
        processing_status="received",
        attempt_count=0,
        received_at=NOW,
    )


def _snapshot(entry: LemonSqueezyWebhookInboxEntry) -> dict[str, object]:
    return deepcopy({name: getattr(entry, name) for name in entry.__dataclass_fields__})


@pytest.mark.parametrize(
    "operation",
    (
        lambda entry: claim_lemon_squeezy_webhook(
            entry,
            claimed_at=datetime(2026, 8, 5, 19, 0),
        ),
        lambda entry: mark_lemon_squeezy_webhook_processed(
            entry,
            processed_at=datetime(2026, 8, 5, 19, 0),
        ),
        lambda entry: mark_lemon_squeezy_webhook_rejected(
            entry,
            error_code="invalid code with spaces",
            rejected_at=NOW,
        ),
    ),
)
def test_failed_lifecycle_operations_are_fully_non_mutating(operation) -> None:
    entry = _entry()
    before = _snapshot(entry)

    with pytest.raises(LemonSqueezyWebhookError):
        operation(entry)

    assert _snapshot(entry) == before


def test_terminal_processed_state_cannot_be_rejected_afterward() -> None:
    entry = _entry()
    claim_lemon_squeezy_webhook(entry, claimed_at=NOW)
    mark_lemon_squeezy_webhook_processed(
        entry,
        processed_at=NOW + timedelta(seconds=1),
    )
    before = _snapshot(entry)

    with pytest.raises(LemonSqueezyWebhookError):
        mark_lemon_squeezy_webhook_rejected(
            entry,
            error_code="late_failure",
            rejected_at=NOW + timedelta(seconds=2),
        )

    assert _snapshot(entry) == before


def test_terminal_rejected_state_cannot_be_processed_afterward() -> None:
    entry = _entry()
    claim_lemon_squeezy_webhook(entry, claimed_at=NOW)
    mark_lemon_squeezy_webhook_rejected(
        entry,
        error_code="binding_mismatch",
        rejected_at=NOW + timedelta(seconds=1),
    )
    before = _snapshot(entry)

    with pytest.raises(LemonSqueezyWebhookError):
        mark_lemon_squeezy_webhook_processed(
            entry,
            processed_at=NOW + timedelta(seconds=2),
        )

    assert _snapshot(entry) == before


def test_claim_rejects_overflowed_or_negative_attempt_state_without_mutation() -> None:
    for invalid_attempt_count in (-1, 2_147_483_647):
        entry = _entry()
        entry.attempt_count = invalid_attempt_count
        before = _snapshot(entry)

        with pytest.raises(LemonSqueezyWebhookError):
            claim_lemon_squeezy_webhook(entry, claimed_at=NOW)

        assert _snapshot(entry) == before


def test_terminal_timestamp_equal_to_claim_is_allowed_but_not_earlier() -> None:
    processed = _entry()
    claim_lemon_squeezy_webhook(processed, claimed_at=NOW)
    mark_lemon_squeezy_webhook_processed(processed, processed_at=NOW)
    assert processed.processed_at == NOW

    rejected = _entry()
    claim_lemon_squeezy_webhook(rejected, claimed_at=NOW)
    mark_lemon_squeezy_webhook_rejected(
        rejected,
        error_code="manual_review",
        rejected_at=NOW,
    )
    assert rejected.rejected_at == NOW


def test_error_code_normalization_is_stable_across_replay() -> None:
    entry = _entry()
    claim_lemon_squeezy_webhook(entry, claimed_at=NOW)
    mark_lemon_squeezy_webhook_rejected(
        entry,
        error_code="  CUSTOMER_MISMATCH  ",
        rejected_at=NOW,
    )

    mark_lemon_squeezy_webhook_rejected(
        entry,
        error_code="customer_mismatch",
        rejected_at=NOW + timedelta(seconds=1),
    )

    assert entry.last_error_code == "customer_mismatch"
    assert entry.rejected_at == NOW
