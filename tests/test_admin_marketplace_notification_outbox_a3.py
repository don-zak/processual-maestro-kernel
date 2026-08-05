import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from processual_api.admin_marketplace.notification_outbox import (
    CommercialNotificationClaim,
    CommercialNotificationDispatcher,
    enqueue_commercial_notification,
)
from processual_api.admin_marketplace.router import CommercialNotificationReadResponse

NOW = datetime(2026, 8, 5, 17, 0, tzinfo=UTC)


class Writer:
    def __init__(self):
        self.items = []

    def add(self, item):
        self.items.append(item)


def test_enqueue_is_safe_and_deduplicated():
    writer = Writer()
    event = enqueue_commercial_notification(
        SimpleNamespace(notification_outbox=writer),
        event_type="payment_verified",
        aggregate_type="order",
        aggregate_ref="ord_001",
        customer_ref="customer_001",
        payload={"order_ref": "ord_001", "status": "verified", "currency": "TND"},
        deduplication_material="verification-idempotency-hash",
        occurred_at=NOW,
        id_factory=lambda: uuid.UUID("10000000-0000-0000-0000-000000000001"),
    )
    assert writer.items == [event]
    assert len(event.deduplication_key_hash) == 64
    assert event.payload_json["currency"] == "TND"


@pytest.mark.parametrize("key", ["account_identifier", "iban", "payload_ciphertext", "transfer_reference"])
def test_sensitive_payload_keys_are_rejected(key):
    with pytest.raises(ValueError, match="Sensitive"):
        enqueue_commercial_notification(
            SimpleNamespace(notification_outbox=Writer()),
            event_type="payment_instructions_ready",
            aggregate_type="order",
            aggregate_ref="ord_001",
            customer_ref="customer_001",
            payload={key: "forbidden"},
            deduplication_material="contract-hash",
            occurred_at=NOW,
        )


class Repository:
    def __init__(self, claim):
        self.claim, self.delivered, self.failed = claim, [], []

    async def claim_batch(self, **kwargs):
        return (self.claim,)

    async def mark_delivered(self, **kwargs):
        self.delivered.append(kwargs)
        return True

    async def mark_failed(self, **kwargs):
        self.failed.append(kwargs)
        return True


def _claim(attempt=1):
    return CommercialNotificationClaim(
        uuid.uuid4(),
        uuid.uuid4(),
        "cno_001",
        "order_created",
        "order",
        "ord_001",
        "customer_001",
        {"order_ref": "ord_001"},
        attempt,
    )


@pytest.mark.asyncio
async def test_dispatcher_delivers_outside_transaction():
    repository = Repository(_claim())

    class Adapter:
        async def deliver(self, claim):
            pass

    result = await CommercialNotificationDispatcher(
        repository=repository, adapter=Adapter(), clock=lambda: NOW
    ).dispatch_once()
    assert result.delivered == 1
    assert repository.delivered


@pytest.mark.asyncio
async def test_dispatcher_dead_letters_with_generic_error():
    repository = Repository(_claim(5))

    class Adapter:
        async def deliver(self, claim):
            raise RuntimeError("sensitive provider text")

    result = await CommercialNotificationDispatcher(
        repository=repository, adapter=Adapter(), clock=lambda: NOW, max_attempts=5
    ).dispatch_once()
    assert result.dead_lettered == 1
    assert repository.failed[0]["error_code"] == "notification_delivery_failed"


def test_admin_status_dto_excludes_payload():
    fields = set(CommercialNotificationReadResponse.model_fields)
    assert {"delivery_status", "attempt_count"} <= fields
    assert "payload_json" not in fields
