from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from processual_api.admin_marketplace.lemon_squeezy_webhooks import (
    LemonSqueezyWebhookError,
    VerifiedLemonSqueezyWebhook,
)


@dataclass(slots=True)
class LemonSqueezyWebhookInboxEntry:
    id: uuid.UUID
    event_identity_hash: str
    payload_digest: str
    event_name: str
    resource_type: str
    external_resource_id: str
    store_id: str
    customer_ref: str
    order_ref: str
    offer_ref: str
    test_mode: bool
    processing_status: str
    attempt_count: int
    received_at: datetime
    claimed_at: datetime | None = None
    processed_at: datetime | None = None
    rejected_at: datetime | None = None
    last_error_code: str | None = None


class LemonSqueezyWebhookInboxRepository(Protocol):
    async def get_by_event_identity_hash(
        self,
        event_identity_hash: str,
        *,
        for_update: bool = False,
    ) -> LemonSqueezyWebhookInboxEntry | None: ...

    async def get_by_payload_digest(
        self,
        payload_digest: str,
        *,
        for_update: bool = False,
    ) -> LemonSqueezyWebhookInboxEntry | None: ...

    def add(self, entry: LemonSqueezyWebhookInboxEntry) -> None: ...


@dataclass(frozen=True, slots=True)
class LemonSqueezyWebhookIngestionResult:
    entry: LemonSqueezyWebhookInboxEntry
    replayed: bool


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _event_identity(
    webhook: VerifiedLemonSqueezyWebhook,
    *,
    payload_digest: str,
) -> str:
    canonical = "\x1f".join(
        (
            webhook.store_id,
            webhook.event_name,
            webhook.resource_type,
            webhook.external_resource_id,
            payload_digest,
        )
    ).encode("utf-8")
    return _digest(canonical)


def _same_binding(
    existing: LemonSqueezyWebhookInboxEntry,
    webhook: VerifiedLemonSqueezyWebhook,
) -> bool:
    return (
        existing.event_name == webhook.event_name
        and existing.resource_type == webhook.resource_type
        and existing.external_resource_id == webhook.external_resource_id
        and existing.store_id == webhook.store_id
        and existing.customer_ref == webhook.customer_ref
        and existing.order_ref == webhook.order_ref
        and existing.offer_ref == webhook.offer_ref
        and existing.test_mode is webhook.test_mode
    )


async def ingest_verified_lemon_squeezy_webhook(
    *,
    repository: LemonSqueezyWebhookInboxRepository,
    webhook: VerifiedLemonSqueezyWebhook,
    raw_body: bytes,
    received_at: datetime | None = None,
) -> LemonSqueezyWebhookIngestionResult:
    if not isinstance(raw_body, bytes) or not raw_body:
        raise LemonSqueezyWebhookError("verified webhook raw body is required.")

    payload_digest = _digest(raw_body)
    identity_hash = _event_identity(
        webhook,
        payload_digest=payload_digest,
    )

    existing = await repository.get_by_event_identity_hash(
        identity_hash,
        for_update=True,
    )
    if existing is not None:
        if existing.payload_digest != payload_digest or not _same_binding(existing, webhook):
            raise LemonSqueezyWebhookError(
                "webhook event identity was replayed with conflicting payload or references."
            )
        return LemonSqueezyWebhookIngestionResult(
            entry=existing,
            replayed=True,
        )

    payload_owner = await repository.get_by_payload_digest(
        payload_digest,
        for_update=True,
    )
    if payload_owner is not None:
        raise LemonSqueezyWebhookError(
            "webhook payload was already bound to a different event identity."
        )

    timestamp = received_at or datetime.now(UTC)
    if timestamp.tzinfo is None:
        raise LemonSqueezyWebhookError("received_at must be timezone-aware.")

    entry = LemonSqueezyWebhookInboxEntry(
        id=uuid.uuid4(),
        event_identity_hash=identity_hash,
        payload_digest=payload_digest,
        event_name=webhook.event_name,
        resource_type=webhook.resource_type,
        external_resource_id=webhook.external_resource_id,
        store_id=webhook.store_id,
        customer_ref=webhook.customer_ref,
        order_ref=webhook.order_ref,
        offer_ref=webhook.offer_ref,
        test_mode=webhook.test_mode,
        processing_status="received",
        attempt_count=0,
        received_at=timestamp,
    )
    repository.add(entry)
    return LemonSqueezyWebhookIngestionResult(entry=entry, replayed=False)
