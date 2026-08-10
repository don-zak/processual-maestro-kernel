from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from processual_api.admin_marketplace.lemon_squeezy_evidence import (
    LemonSqueezyVerifiedEvidence,
)
from processual_api.admin_marketplace.lemon_squeezy_inbox import (
    LemonSqueezyWebhookInboxEntry,
    ingest_verified_lemon_squeezy_webhook,
)
from processual_api.admin_marketplace.lemon_squeezy_webhooks import (
    LemonSqueezyWebhookError,
    VerifiedLemonSqueezyWebhook,
)


class FakeRepository:
    def __init__(self) -> None:
        self.by_identity: dict[str, LemonSqueezyWebhookInboxEntry] = {}
        self.by_payload: dict[str, LemonSqueezyWebhookInboxEntry] = {}
        self.added: list[LemonSqueezyWebhookInboxEntry] = []
        self.identity_reads: list[tuple[str, bool]] = []
        self.payload_reads: list[tuple[str, bool]] = []

    async def get_by_event_identity_hash(
        self,
        event_identity_hash: str,
        *,
        for_update: bool = False,
    ) -> LemonSqueezyWebhookInboxEntry | None:
        self.identity_reads.append((event_identity_hash, for_update))
        return self.by_identity.get(event_identity_hash)

    async def get_by_payload_digest(
        self,
        payload_digest: str,
        *,
        for_update: bool = False,
    ) -> LemonSqueezyWebhookInboxEntry | None:
        self.payload_reads.append((payload_digest, for_update))
        return self.by_payload.get(payload_digest)

    def add(self, entry: LemonSqueezyWebhookInboxEntry) -> None:
        self.added.append(entry)
        self.by_identity[entry.event_identity_hash] = entry
        self.by_payload[entry.payload_digest] = entry


def _webhook(**overrides: object) -> VerifiedLemonSqueezyWebhook:
    values: dict[str, object] = {
        "event_name": "subscription_created",
        "resource_type": "subscriptions",
        "external_resource_id": "901",
        "store_id": "77",
        "customer_ref": "customer-1",
        "order_ref": "order-1",
        "offer_ref": "offer-1",
        "test_mode": False,
        "evidence": LemonSqueezyVerifiedEvidence(
            schema_version=1,
            provider_customer_id="501",
            provider_order_id="601",
            provider_subscription_id="901",
            variant_id="701",
            currency=None,
            subtotal_amount=None,
            total_amount=None,
            refunded_amount=None,
            status="active",
            effective_at=datetime(2026, 8, 5, 18, 0, tzinfo=timezone.utc),
        ),
        "payload": {},
    }
    values.update(overrides)
    return VerifiedLemonSqueezyWebhook(**values)  # type: ignore[arg-type]


def _body(**overrides: object) -> bytes:
    payload: dict[str, object] = {
        "meta": {"event_name": "subscription_created"},
        "data": {"id": "901", "type": "subscriptions"},
    }
    payload.update(overrides)
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


@pytest.mark.asyncio
async def test_first_verified_event_is_added_once_as_received() -> None:
    repository = FakeRepository()
    received_at = datetime(2026, 8, 5, 18, 0, tzinfo=timezone.utc)

    result = await ingest_verified_lemon_squeezy_webhook(
        repository=repository,
        webhook=_webhook(),
        raw_body=_body(),
        received_at=received_at,
    )

    assert result.replayed is False
    assert repository.added == [result.entry]
    assert result.entry.processing_status == "received"
    assert result.entry.attempt_count == 0
    assert result.entry.received_at == received_at
    assert len(result.entry.event_identity_hash) == 64
    assert len(result.entry.payload_digest) == 64
    assert repository.identity_reads == [(result.entry.event_identity_hash, True)]
    assert repository.payload_reads == [(result.entry.payload_digest, True)]


@pytest.mark.asyncio
async def test_exact_replay_returns_existing_entry_without_adding() -> None:
    repository = FakeRepository()
    webhook = _webhook()
    raw_body = _body()

    first = await ingest_verified_lemon_squeezy_webhook(
        repository=repository,
        webhook=webhook,
        raw_body=raw_body,
    )
    second = await ingest_verified_lemon_squeezy_webhook(
        repository=repository,
        webhook=webhook,
        raw_body=raw_body,
    )

    assert second.replayed is True
    assert second.entry is first.entry
    assert repository.added == [first.entry]
    assert len(repository.payload_reads) == 1


@pytest.mark.asyncio
async def test_same_event_identity_with_different_customer_is_rejected() -> None:
    repository = FakeRepository()
    raw_body = _body()

    await ingest_verified_lemon_squeezy_webhook(
        repository=repository,
        webhook=_webhook(),
        raw_body=raw_body,
    )

    with pytest.raises(LemonSqueezyWebhookError, match="conflicting payload or references"):
        await ingest_verified_lemon_squeezy_webhook(
            repository=repository,
            webhook=_webhook(customer_ref="customer-2"),
            raw_body=raw_body,
        )

    assert len(repository.added) == 1


@pytest.mark.asyncio
async def test_same_event_identity_with_mutated_payload_is_rejected() -> None:
    repository = FakeRepository()

    await ingest_verified_lemon_squeezy_webhook(
        repository=repository,
        webhook=_webhook(),
        raw_body=_body(),
    )

    with pytest.raises(LemonSqueezyWebhookError, match="conflicting payload or references"):
        await ingest_verified_lemon_squeezy_webhook(
            repository=repository,
            webhook=_webhook(),
            raw_body=_body(extra="mutated"),
        )


@pytest.mark.asyncio
async def test_same_payload_cannot_be_bound_to_different_event_identity() -> None:
    repository = FakeRepository()
    raw_body = _body()

    await ingest_verified_lemon_squeezy_webhook(
        repository=repository,
        webhook=_webhook(),
        raw_body=raw_body,
    )

    with pytest.raises(LemonSqueezyWebhookError, match="already bound"):
        await ingest_verified_lemon_squeezy_webhook(
            repository=repository,
            webhook=_webhook(external_resource_id="902"),
            raw_body=raw_body,
        )


@pytest.mark.asyncio
async def test_test_mode_is_part_of_the_security_binding() -> None:
    repository = FakeRepository()
    raw_body = _body()

    await ingest_verified_lemon_squeezy_webhook(
        repository=repository,
        webhook=_webhook(test_mode=False),
        raw_body=raw_body,
    )

    with pytest.raises(LemonSqueezyWebhookError, match="conflicting payload or references"):
        await ingest_verified_lemon_squeezy_webhook(
            repository=repository,
            webhook=_webhook(test_mode=True),
            raw_body=raw_body,
        )


@pytest.mark.asyncio
async def test_received_at_must_be_timezone_aware() -> None:
    repository = FakeRepository()

    with pytest.raises(LemonSqueezyWebhookError, match="timezone-aware"):
        await ingest_verified_lemon_squeezy_webhook(
            repository=repository,
            webhook=_webhook(),
            raw_body=_body(),
            received_at=datetime(2026, 8, 5, 18, 0),
        )

    assert repository.added == []


@pytest.mark.asyncio
async def test_raw_body_is_required_even_after_verification() -> None:
    repository = FakeRepository()

    with pytest.raises(LemonSqueezyWebhookError, match="raw body is required"):
        await ingest_verified_lemon_squeezy_webhook(
            repository=repository,
            webhook=_webhook(),
            raw_body=b"",
        )
