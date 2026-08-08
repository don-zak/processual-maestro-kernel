from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from processual_api.admin_marketplace.lemon_squeezy_subscription_reconciliation import (
    apply_lemon_squeezy_subscription_lifecycle,
)
from processual_api.admin_marketplace.lemon_squeezy_webhooks import (
    LemonSqueezyWebhookError,
)

NOW = datetime(2026, 8, 6, 15, 0, tzinfo=UTC)


class SubscriptionRepository:
    def __init__(self, subscription: object | None) -> None:
        self.subscription = subscription
        self.locked = False

    async def get_by_id(self, subscription_id: uuid.UUID, *, for_update: bool = False):
        self.locked = for_update
        if self.subscription is None:
            return None
        return self.subscription if self.subscription.id == subscription_id else None


def _binding() -> SimpleNamespace:
    return SimpleNamespace(
        subscription_id=uuid.uuid4(),
        order_id=uuid.uuid4(),
        offer_id=uuid.uuid4(),
    )


def _subscription(binding: object, *, status: str = "pending") -> SimpleNamespace:
    return SimpleNamespace(
        id=binding.subscription_id,
        customer_ref="customer_001",
        order_id=binding.order_id,
        offer_id=binding.offer_id,
        status=status,
        starts_at=None,
        ends_at=None,
    )


def _inbox(event_name: str) -> SimpleNamespace:
    return SimpleNamespace(
        event_name=event_name,
        customer_ref="customer_001",
        provider_effective_at=NOW,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("event_name", "expected_status"),
    [
        ("subscription_created", "active"),
        ("subscription_paused", "suspended"),
        ("subscription_cancelled", "cancelled"),
        ("subscription_expired", "expired"),
    ],
)
async def test_verified_events_apply_expected_status(
    event_name: str,
    expected_status: str,
) -> None:
    binding = _binding()
    subscription = _subscription(binding)
    repository = SubscriptionRepository(subscription)
    uow = SimpleNamespace(subscriptions=repository)

    await apply_lemon_squeezy_subscription_lifecycle(
        uow=uow,
        binding=binding,
        inbox=_inbox(event_name),
    )

    assert repository.locked is True
    assert subscription.status == expected_status
    if expected_status == "active":
        assert subscription.starts_at == NOW
        assert subscription.ends_at is None
    elif expected_status in {"cancelled", "expired"}:
        assert subscription.ends_at == NOW


@pytest.mark.asyncio
async def test_non_lifecycle_event_is_noop() -> None:
    repository = SubscriptionRepository(None)
    await apply_lemon_squeezy_subscription_lifecycle(
        uow=SimpleNamespace(subscriptions=repository),
        binding=SimpleNamespace(subscription_id=None),
        inbox=_inbox("order_created"),
    )
    assert repository.locked is False


@pytest.mark.asyncio
async def test_terminal_subscription_cannot_be_resurrected() -> None:
    binding = _binding()
    subscription = _subscription(binding, status="cancelled")

    with pytest.raises(
        LemonSqueezyWebhookError,
        match="cannot transition",
    ):
        await apply_lemon_squeezy_subscription_lifecycle(
            uow=SimpleNamespace(
                subscriptions=SubscriptionRepository(subscription),
            ),
            binding=binding,
            inbox=_inbox("subscription_resumed"),
        )

    assert subscription.status == "cancelled"


@pytest.mark.asyncio
async def test_binding_without_internal_subscription_fails_closed() -> None:
    with pytest.raises(
        LemonSqueezyWebhookError,
        match="has no internal subscription",
    ):
        await apply_lemon_squeezy_subscription_lifecycle(
            uow=SimpleNamespace(subscriptions=SubscriptionRepository(None)),
            binding=SimpleNamespace(subscription_id=None),
            inbox=_inbox("subscription_created"),
        )
