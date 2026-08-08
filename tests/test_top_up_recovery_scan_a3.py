from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from processual_api.admin_marketplace.top_up_recovery_scan import (
    scan_top_up_recovery_candidates,
)


class OrderRepo:
    def __init__(self, orders: tuple[object, ...]) -> None:
        self.orders = orders

    async def list_recovery_candidates(self, *, limit: int = 100):
        return self.orders[:limit]


class ReversalRepo:
    def __init__(self, reversals: tuple[object, ...]) -> None:
        self.reversals = reversals

    async def list_manual_review(self, *, limit: int = 100):
        return self.reversals[:limit]


class FakeUow:
    def __init__(self, *, orders: tuple[object, ...], reversals: tuple[object, ...]) -> None:
        self.top_up_orders = OrderRepo(orders)
        self.subscription_top_up_reversals = ReversalRepo(reversals)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None


@pytest.mark.asyncio
async def test_scan_classifies_uncertain_checkout_verified_payment_and_manual_review() -> None:
    uncertain_id = uuid.uuid4()
    verified_id = uuid.uuid4()
    review_id = uuid.uuid4()
    uow = FakeUow(
        orders=(
            SimpleNamespace(
                id=uncertain_id,
                checkout_creation_status="uncertain",
                state="awaiting_payment",
                provider_variant_id="9001",
                channel="lemon_squeezy",
            ),
            SimpleNamespace(
                id=verified_id,
                checkout_creation_status="ready",
                state="payment_verified",
                provider_variant_id="9001",
                channel="local_tunisia",
            ),
        ),
        reversals=(
            SimpleNamespace(
                order_id=review_id,
                provider_event_ref="manual:chargeback:1",
                reason_code="units_already_consumed",
            ),
        ),
    )

    result = await scan_top_up_recovery_candidates(
        unit_of_work_factory=lambda: uow,
        limit=10,
    )

    assert result.count == 3
    assert [candidate.kind for candidate in result.candidates] == [
        "checkout_recovery",
        "grant_recovery",
        "reversal_review",
    ]
    assert result.candidates[0].order_id == uncertain_id
    assert result.candidates[1].order_id == verified_id
    assert result.candidates[2].order_id == review_id


@pytest.mark.asyncio
async def test_scan_is_bounded_and_does_not_mutate_records() -> None:
    order = SimpleNamespace(
        id=uuid.uuid4(),
        checkout_creation_status="uncertain",
        state="payment_verified",
        provider_variant_id=None,
        channel="lemon_squeezy",
    )
    uow = FakeUow(orders=(order,), reversals=())

    result = await scan_top_up_recovery_candidates(
        unit_of_work_factory=lambda: uow,
        limit=1,
    )

    assert result.count == 1
    assert order.checkout_creation_status == "uncertain"
    assert order.state == "payment_verified"
