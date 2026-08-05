from __future__ import annotations

import re
from datetime import datetime, timezone

from processual_api.admin_marketplace.lemon_squeezy_inbox import (
    LemonSqueezyWebhookInboxEntry,
)
from processual_api.admin_marketplace.lemon_squeezy_webhooks import (
    LemonSqueezyWebhookError,
)


_ERROR_CODE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")


def _aware_timestamp(value: datetime | None, *, field_name: str) -> datetime:
    timestamp = value or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        raise LemonSqueezyWebhookError(f"{field_name} must be timezone-aware.")
    return timestamp


def _normalized_error_code(value: str) -> str:
    normalized = value.strip().lower()
    if not _ERROR_CODE_PATTERN.fullmatch(normalized):
        raise LemonSqueezyWebhookError("error_code is invalid.")
    return normalized


def claim_lemon_squeezy_webhook(
    entry: LemonSqueezyWebhookInboxEntry,
    *,
    claimed_at: datetime | None = None,
) -> None:
    if entry.processing_status != "received":
        raise LemonSqueezyWebhookError(
            "only a received webhook can be claimed for processing."
        )
    if entry.claimed_at is not None or entry.processed_at is not None or entry.rejected_at is not None:
        raise LemonSqueezyWebhookError("webhook lifecycle timestamps are inconsistent.")

    entry.processing_status = "processing"
    entry.attempt_count += 1
    entry.claimed_at = _aware_timestamp(claimed_at, field_name="claimed_at")
    entry.last_error_code = None


def mark_lemon_squeezy_webhook_processed(
    entry: LemonSqueezyWebhookInboxEntry,
    *,
    processed_at: datetime | None = None,
) -> None:
    if entry.processing_status == "processed":
        return
    if entry.processing_status != "processing":
        raise LemonSqueezyWebhookError(
            "only a processing webhook can be marked processed."
        )
    if entry.claimed_at is None or entry.rejected_at is not None:
        raise LemonSqueezyWebhookError("webhook lifecycle timestamps are inconsistent.")

    timestamp = _aware_timestamp(processed_at, field_name="processed_at")
    if timestamp < entry.claimed_at:
        raise LemonSqueezyWebhookError("processed_at cannot precede claimed_at.")

    entry.processing_status = "processed"
    entry.processed_at = timestamp
    entry.rejected_at = None
    entry.last_error_code = None


def mark_lemon_squeezy_webhook_rejected(
    entry: LemonSqueezyWebhookInboxEntry,
    *,
    error_code: str,
    rejected_at: datetime | None = None,
) -> None:
    if entry.processing_status == "rejected":
        if entry.last_error_code != _normalized_error_code(error_code):
            raise LemonSqueezyWebhookError(
                "rejected webhook cannot be replayed with a different error code."
            )
        return
    if entry.processing_status != "processing":
        raise LemonSqueezyWebhookError(
            "only a processing webhook can be rejected."
        )
    if entry.claimed_at is None or entry.processed_at is not None:
        raise LemonSqueezyWebhookError("webhook lifecycle timestamps are inconsistent.")

    timestamp = _aware_timestamp(rejected_at, field_name="rejected_at")
    if timestamp < entry.claimed_at:
        raise LemonSqueezyWebhookError("rejected_at cannot precede claimed_at.")

    entry.processing_status = "rejected"
    entry.rejected_at = timestamp
    entry.processed_at = None
    entry.last_error_code = _normalized_error_code(error_code)
