from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from processual_api.billing.lemon_checkout_order_authority import (
    LemonCheckoutOrderAuthority,
    LemonCheckoutOrderAuthorityError,
)

NOW = datetime(2026, 8, 22, 11, 45, tzinfo=UTC)
OFFER_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
PLAN_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")


class _Orders:
    def __init__(self) -> None:
        self.added = []

    async def get_by_creation_idempotency_key_hash(self, value, *, for_update=False):
        assert for_update is True
        return None

    def add(self, value) -> None:
        self.added.append(value)


class _Offers:
    async def get_by_id(self, value, *, for_update=False):
        assert value == OFFER_ID
        assert for_update is True
        return SimpleNamespace(
            id=OFFER_ID,
            offer_code="starter_monthly",
            plan_id=PLAN_ID,
            status="published",
            sales_channel="lemon_squeezy",
            billing_period="monthly",
            currency="USD",
            amount=Decimal("19.000"),
            display_name="Starter Monthly",
            effective_at=None,
            expires_at=None,
        )


class _Eligibility:
    def __init__(self, *, lemon_status: str, review: bool) -> None:
        self.value = SimpleNamespace(
            country_code="TN",
            lemon_squeezy_status=lemon_status,
            maestro_direct_status="eligible",
            customer_choice_allowed=(lemon_status == "eligible" and not review),
            admin_review_required=review,
        )

    async def get_by_customer_ref(self, value, *, for_update=False):
        assert value == "customer-tn-001"
        assert for_update is True
        return self.value


class _Audit:
    def __init__(self) -> None:
        self.added = []

    def append(self, value) -> None:
        self.added.append(value)


class _Uow:
    def __init__(self, *, lemon_status: str, review: bool) -> None:
        self.orders = _Orders()
        self.offers = _Offers()
        self.channel_eligibilities = _Eligibility(
            lemon_status=lemon_status,
            review=review,
        )
        self.commercial_audit = _Audit()
        self.notification_outbox = None
        self.commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1


def _authority(uow: _Uow) -> LemonCheckoutOrderAuthority:
    return LemonCheckoutOrderAuthority(
        unit_of_work_factory=lambda: uow,
        clock=lambda: NOW,
        id_factory=lambda: uuid.UUID("33333333-3333-4333-8333-333333333333"),
        reference_factory=lambda: uuid.UUID("44444444-4444-4444-8444-444444444444"),
        event_id_factory=lambda: uuid.UUID("55555555-5555-4555-8555-555555555555"),
    )


async def _prepare(authority: LemonCheckoutOrderAuthority):
    return await authority.prepare(
        actor_user_id="user-001",
        actor_session_id="session-001",
        customer_ref="customer-tn-001",
        offer_id=OFFER_ID,
        offer_ref="starter_monthly",
        plan_id=PLAN_ID,
        billing_period="monthly",
        currency="USD",
        amount=Decimal("19.000"),
        display_name="Starter Monthly",
        correlation_id="corr-001",
        idempotency_key="tn-lemon-policy-0001",
    )


@pytest.mark.asyncio
async def test_tunisian_customer_can_choose_lemon_when_eligible() -> None:
    uow = _Uow(lemon_status="eligible", review=False)

    result = await _prepare(_authority(uow))

    assert result.country_code == "TN"
    assert result.offer_ref == "starter_monthly"
    assert result.status == "awaiting_payment"
    assert len(uow.orders.added) == 1
    assert uow.orders.added[0].selected_channel == "lemon_squeezy"
    assert uow.orders.added[0].country_code == "TN"
    assert uow.commits == 1


@pytest.mark.asyncio
async def test_tunisian_customer_is_blocked_only_when_lemon_is_ineligible() -> None:
    uow = _Uow(lemon_status="ineligible", review=False)

    with pytest.raises(
        LemonCheckoutOrderAuthorityError,
        match="not authorized",
    ) as captured:
        await _prepare(_authority(uow))

    assert captured.value.reason_code == "lemon_squeezy_customer_ineligible"
    assert uow.orders.added == []
    assert uow.commits == 0


@pytest.mark.asyncio
async def test_tunisian_customer_review_state_fails_closed() -> None:
    uow = _Uow(lemon_status="eligible", review=True)

    with pytest.raises(LemonCheckoutOrderAuthorityError) as captured:
        await _prepare(_authority(uow))

    assert captured.value.reason_code == "lemon_squeezy_admin_review_required"
    assert uow.orders.added == []
    assert uow.commits == 0
