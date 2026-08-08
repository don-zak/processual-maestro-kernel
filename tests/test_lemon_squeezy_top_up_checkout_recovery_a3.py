from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from processual_api.admin_marketplace.lemon_squeezy_top_up_checkout_recovery import (
    LemonSqueezyCheckoutCandidate,
    LemonSqueezyTopUpCheckoutRecoveryError,
    RecoverTopUpCheckoutCommand,
    recover_lemon_squeezy_top_up_checkout_factory,
)
from processual_api.billing.plan_fulfillment_catalog import (
    PLAN_FULFILLMENT_CATALOG_VERSION,
)

ORDER_ID = uuid.uuid4()
CUSTOMER_REF = "customer_001"
STORE_ID = "1200"
VARIANT_ID = "9001"
CHECKOUT_ID = "a4cdd678-6ed6-42de-a8f7-951565604d62"


class ByIdRepo:
    def __init__(self, value: object | None) -> None:
        self.value = value

    async def get_by_id(self, value_id, *, for_update: bool = False):
        if self.value is None or self.value.id != value_id:
            return None
        return self.value


class FakeUow:
    def __init__(self, order: object) -> None:
        self.top_up_orders = ByIdRepo(order)
        self.commit_count = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

    async def commit(self) -> None:
        self.commit_count += 1


def _order(**overrides: object) -> SimpleNamespace:
    values = {
        "id": ORDER_ID,
        "customer_ref": CUSTOMER_REF,
        "channel": "lemon_squeezy",
        "state": "awaiting_payment",
        "plan_catalog_version": PLAN_FULFILLMENT_CATALOG_VERSION,
        "provider_variant_id": VARIANT_ID,
        "provider_checkout_id": None,
        "checkout_creation_status": "uncertain",
        "total_price_usd": "10.00",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _candidate(*, checkout_id: str = CHECKOUT_ID) -> LemonSqueezyCheckoutCandidate:
    return LemonSqueezyCheckoutCandidate(
        checkout_id=checkout_id,
        url=f"https://store.lemonsqueezy.com/checkout/custom/{checkout_id}",
        store_id=STORE_ID,
        variant_id=VARIANT_ID,
        custom_price=1000,
        custom_data={
            "customer_ref": CUSTOMER_REF,
            "order_ref": str(ORDER_ID),
            "offer_ref": "quota_top_up",
        },
    )


def _command() -> RecoverTopUpCheckoutCommand:
    return RecoverTopUpCheckoutCommand(
        order_id=ORDER_ID,
        customer_ref=CUSTOMER_REF,
        store_id=STORE_ID,
        provider_variant_id=VARIANT_ID,
    )


@pytest.mark.asyncio
async def test_uncertain_checkout_recovers_only_exact_provider_match() -> None:
    order = _order()
    uow = FakeUow(order)

    async def finder(*, store_id: str, variant_id: str):
        assert store_id == STORE_ID
        assert variant_id == VARIANT_ID
        return (_candidate(),)

    recover = recover_lemon_squeezy_top_up_checkout_factory(
        unit_of_work_factory=lambda: uow,
        checkout_finder=finder,
    )
    result = await recover(_command())

    assert result.checkout_id == CHECKOUT_ID
    assert result.recovered is True
    assert result.committed is True
    assert order.provider_checkout_id == CHECKOUT_ID
    assert order.checkout_creation_status == "ready"
    assert uow.commit_count == 1


@pytest.mark.asyncio
async def test_recovery_fails_closed_when_multiple_provider_checkouts_match() -> None:
    order = _order()
    uow = FakeUow(order)
    second_checkout_id = "7e8445aa-f3be-4d40-b057-feaba359fd91"

    async def finder(*, store_id: str, variant_id: str):
        return (_candidate(), _candidate(checkout_id=second_checkout_id))

    recover = recover_lemon_squeezy_top_up_checkout_factory(
        unit_of_work_factory=lambda: uow,
        checkout_finder=finder,
    )

    with pytest.raises(LemonSqueezyTopUpCheckoutRecoveryError):
        await recover(_command())

    assert order.provider_checkout_id is None
    assert order.checkout_creation_status == "uncertain"
    assert uow.commit_count == 0


@pytest.mark.asyncio
async def test_recovery_rejects_matching_metadata_with_tampered_price() -> None:
    order = _order()
    uow = FakeUow(order)
    candidate = _candidate()
    tampered = LemonSqueezyCheckoutCandidate(
        checkout_id=candidate.checkout_id,
        url=candidate.url,
        store_id=candidate.store_id,
        variant_id=candidate.variant_id,
        custom_price=1,
        custom_data=candidate.custom_data,
    )

    async def finder(*, store_id: str, variant_id: str):
        return (tampered,)

    recover = recover_lemon_squeezy_top_up_checkout_factory(
        unit_of_work_factory=lambda: uow,
        checkout_finder=finder,
    )

    with pytest.raises(LemonSqueezyTopUpCheckoutRecoveryError):
        await recover(_command())

    assert uow.commit_count == 0
