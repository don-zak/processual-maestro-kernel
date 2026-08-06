from __future__ import annotations

from datetime import UTC, datetime
from types import MappingProxyType

import pytest

from processual_api.admin_marketplace.lemon_squeezy_inbox import (
    LemonSqueezyWebhookInboxEntry,
    ingest_verified_lemon_squeezy_webhook,
)
from processual_api.admin_marketplace.lemon_squeezy_webhooks import (
    LemonSqueezyWebhookError,
    VerifiedLemonSqueezyWebhook,
)

NOW = datetime(2026, 8, 6, 9, 0, tzinfo=UTC)


class FakeInboxRepository:
    def __init__(self) -> None:
        self.by_identity: dict[str, LemonSqueezyWebhookInboxEntry] = {}
        self.by_payload: dict[str, LemonSqueezyWebhookInboxEntry] = {}
        self.added: list[LemonSqueezyWebhookInboxEntry] = []

    async def get_by_event_identity_hash(
        self,
        event_identity_hash: str,
        *,
        for_update: bool = False,
    ) -> LemonSqueezyWebhookInboxEntry | None:
        return self.by_identity.get(event_identity_hash)

    async def get_by_payload_digest(
        self,
        payload_digest: str,
        *,
        for_update: bool = False,
    ) -> LemonSqueezyWebhookInboxEntry | None:
        return self.by_payload.get(payload_digest)

    def add(self, entry: LemonSqueezyWebhookInboxEntry) -> None:
        self.added.append(entry)
        self.by_identity[entry.event_identity_hash] = entry
        self.by_payload[entry.payload_digest] = entry


def _webhook(
    *,
    customer_ref: str = "customer_001",
    order_ref: str = "order_001",
    offer_ref: str = "starter_monthly",
) -> VerifiedLemonSqueezyWebhook:
    return VerifiedLemonSqueezyWebhook(
        event_name="subscription_updated",
        resource_type="subscriptions",
        external_resource_id="9001",
        store_id="7001",
        customer_ref=customer_ref,
        order_ref=order_ref,
        offer_ref=offer_ref,
        test_mode=False,
        payload=MappingProxyType({"verified": True}),
    )


@pytest.mark.asyncio
async def test_exact_signed_body_replay_is_idempotent() -> None:
    repository = FakeInboxRepository()
    raw_body = b'{"event":"subscription_updated","status":"active"}'

    first = await ingest_verified_lemon_squeezy_webhook(
        repository=repository,
        webhook=_webhook(),
        raw_body=raw_body,
        received_at=NOW,
    )
    replay = await ingest_verified_lemon_squeezy_webhook(
        repository=repository,
        webhook=_webhook(),
        raw_body=raw_body,
        received_at=NOW,
    )

    assert first.replayed is False
    assert replay.replayed is True
    assert replay.entry.id == first.entry.id
    assert len(repository.added) == 1


@pytest.mark.asyncio
async def test_successive_updates_for_same_subscription_are_distinct_events() -> None:
    repository = FakeInboxRepository()

    first = await ingest_verified_lemon_squeezy_webhook(
        repository=repository,
        webhook=_webhook(),
        raw_body=b'{"event":"subscription_updated","status":"active"}',
        received_at=NOW,
    )
    second = await ingest_verified_lemon_squeezy_webhook(
        repository=repository,
        webhook=_webhook(),
        raw_body=b'{"event":"subscription_updated","status":"paused"}',
        received_at=NOW,
    )

    assert first.replayed is False
    assert second.replayed is False
    assert second.entry.id != first.entry.id
    assert second.entry.event_identity_hash != first.entry.event_identity_hash
    assert len(repository.added) == 2


@pytest.mark.asyncio
async def test_same_payload_cannot_be_rebound_to_different_internal_references() -> None:
    repository = FakeInboxRepository()
    raw_body = b'{"event":"subscription_updated","status":"active"}'

    await ingest_verified_lemon_squeezy_webhook(
        repository=repository,
        webhook=_webhook(),
        raw_body=raw_body,
        received_at=NOW,
    )

    with pytest.raises(
        LemonSqueezyWebhookError,
        match="event identity was replayed with conflicting payload or references",
    ):
        await ingest_verified_lemon_squeezy_webhook(
            repository=repository,
            webhook=_webhook(customer_ref="customer_002"),
            raw_body=raw_body,
            received_at=NOW,
        )

    assert len(repository.added) == 1


@pytest.mark.asyncio
async def test_naive_received_timestamp_is_rejected() -> None:
    repository = FakeInboxRepository()

    with pytest.raises(
        LemonSqueezyWebhookError,
        match="timezone-aware",
    ):
        await ingest_verified_lemon_squeezy_webhook(
            repository=repository,
            webhook=_webhook(),
            raw_body=b'{"event":"subscription_updated","status":"active"}',
            received_at=datetime(2026, 8, 6, 9, 0),
        )

    assert repository.added == []
