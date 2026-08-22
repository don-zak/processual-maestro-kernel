from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from processual_api.admin_marketplace.models import (
    AdminMarketOffer,
    AdminMarketOrder,
    AdminMarketPlan,
)
from processual_api.billing.lemon_checkout_binding import (
    AdminMarketLemonCheckoutBinding,
)
from processual_api.billing.lemon_subscription_checkout import (
    CreateSubscriptionCheckoutCommand,
    LemonSubscriptionCheckoutError,
    LemonSubscriptionCheckoutResponse,
    create_lemon_subscription_checkout_factory,
)

DATABASE_URL = os.environ.get("ADMIN_MARKET_INTEGRATION_DATABASE_URL", "")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason=(
        "Set ADMIN_MARKET_INTEGRATION_DATABASE_URL to a migrated PostgreSQL "
        "database to run the Lemon checkout binding gate."
    ),
)

NOW = datetime(2026, 8, 22, 13, 0, tzinfo=UTC)


def _async_database_url() -> str:
    if DATABASE_URL.startswith("postgresql+asyncpg://"):
        return DATABASE_URL
    return DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)


def _order(
    *,
    order_id: uuid.UUID,
    order_ref: str,
    customer_ref: str,
    offer: AdminMarketOffer,
    key_hash: str,
) -> AdminMarketOrder:
    return AdminMarketOrder(
        id=order_id,
        order_ref=order_ref,
        customer_ref=customer_ref,
        offer_id=offer.id,
        plan_id=offer.plan_id,
        billing_period="monthly",
        selected_channel="lemon_squeezy",
        country_code="TN",
        currency="USD",
        subtotal_amount=Decimal("19.000"),
        tax_amount=Decimal("0.000"),
        total_amount=Decimal("19.000"),
        status="awaiting_payment",
        contract_status="not_required",
        payment_requirement="required",
        payment_status="pending",
        payment_reference=None,
        payment_destination_snapshot={},
        offer_snapshot={
            "offer_ref": offer.offer_code,
            "display_name": offer.display_name,
            "billing_period": "monthly",
            "currency": "USD",
            "amount": "19.000",
            "sales_channel": "lemon_squeezy",
        },
        creation_idempotency_key_hash=key_hash,
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.mark.asyncio
async def test_checkout_binding_ready_uncertain_and_duplicate_states_are_durable() -> None:
    engine = create_async_engine(_async_database_url())
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    suffix = uuid.uuid4().hex[:16]
    plan_id = uuid.uuid4()
    offer_id = uuid.uuid4()
    success_order_id = uuid.uuid4()
    uncertain_order_id = uuid.uuid4()
    success_order_ref = f"ord_pg_success_{suffix}"
    uncertain_order_ref = f"ord_pg_uncertain_{suffix}"
    customer_ref = f"pg-checkout-customer-{suffix}"
    variant_id = str(int(suffix[:8], 16) % 900000 + 100000)
    checkout_id = str(uuid.uuid4())

    plan = AdminMarketPlan(
        id=plan_id,
        plan_code=f"pg-checkout-plan-{suffix}",
        display_name="PostgreSQL checkout plan",
        entitlement_profile_ref=f"ent-{suffix}",
        quota_profile_ref=f"quota-{suffix}",
        metadata_json={},
    )
    offer = AdminMarketOffer(
        id=offer_id,
        offer_code=f"pg_checkout_offer_{suffix}",
        plan_id=plan_id,
        display_name="PostgreSQL checkout offer",
        currency="USD",
        sales_channel="lemon_squeezy",
        billing_period="monthly",
        amount=Decimal("19.000"),
        status="published",
        effective_at=None,
        expires_at=None,
        customer_specific=False,
    )

    async with session_factory() as session:
        session.add(plan)
        await session.flush()
        session.add(offer)
        await session.flush()
        session.add_all(
            [
                _order(
                    order_id=success_order_id,
                    order_ref=success_order_ref,
                    customer_ref=customer_ref,
                    offer=offer,
                    key_hash="1" * 64,
                ),
                _order(
                    order_id=uncertain_order_id,
                    order_ref=uncertain_order_ref,
                    customer_ref=customer_ref,
                    offer=offer,
                    key_hash="2" * 64,
                ),
            ]
        )
        await session.commit()

    success_calls = []

    async def successful_creator(request):
        success_calls.append(request)
        return LemonSubscriptionCheckoutResponse(
            checkout_id=checkout_id,
            url="https://example.lemonsqueezy.com/checkout/test",
        )

    create_success = create_lemon_subscription_checkout_factory(
        session_factory=session_factory,
        checkout_creator=successful_creator,
    )
    success_command = CreateSubscriptionCheckoutCommand(
        order_id=success_order_id,
        customer_ref=customer_ref,
        offer_ref=offer.offer_code,
        provider_variant_id=variant_id,
        store_id="12345",
        success_url="https://example.test/billing/success",
        email="buyer@example.test",
    )

    try:
        result = await create_success(success_command)
        assert result.order_ref == success_order_ref
        assert result.checkout_id == checkout_id
        assert result.committed is True
        assert len(success_calls) == 1
        assert success_calls[0].order_ref == success_order_ref
        assert success_calls[0].customer_ref == customer_ref
        assert success_calls[0].offer_ref == offer.offer_code

        async with session_factory() as session:
            binding = await session.get(
                AdminMarketLemonCheckoutBinding,
                success_order_id,
            )
            if binding is None:
                from sqlalchemy import select

                binding = await session.scalar(
                    select(AdminMarketLemonCheckoutBinding).where(
                        AdminMarketLemonCheckoutBinding.order_id == success_order_id
                    )
                )
            assert binding is not None
            assert binding.checkout_creation_status == "ready"
            assert binding.provider_checkout_id == checkout_id
            assert binding.provider_variant_id == variant_id

        with pytest.raises(LemonSubscriptionCheckoutError, match="already exists"):
            await create_success(success_command)
        assert len(success_calls) == 1

        failure_calls = []

        async def failing_creator(request):
            failure_calls.append(request)
            raise RuntimeError("simulated provider transport failure")

        create_failure = create_lemon_subscription_checkout_factory(
            session_factory=session_factory,
            checkout_creator=failing_creator,
        )
        uncertain_command = CreateSubscriptionCheckoutCommand(
            order_id=uncertain_order_id,
            customer_ref=customer_ref,
            offer_ref=offer.offer_code,
            provider_variant_id=variant_id,
            store_id="12345",
            success_url="https://example.test/billing/success",
            email=None,
        )

        with pytest.raises(LemonSubscriptionCheckoutError, match="uncertain"):
            await create_failure(uncertain_command)
        assert len(failure_calls) == 1

        async with session_factory() as session:
            from sqlalchemy import select

            uncertain = await session.scalar(
                select(AdminMarketLemonCheckoutBinding).where(
                    AdminMarketLemonCheckoutBinding.order_id == uncertain_order_id
                )
            )
            assert uncertain is not None
            assert uncertain.checkout_creation_status == "uncertain"
            assert uncertain.provider_checkout_id is None

        retry_calls = []

        async def retry_creator(request):
            retry_calls.append(request)
            return LemonSubscriptionCheckoutResponse(
                checkout_id=str(uuid.uuid4()),
                url="https://example.lemonsqueezy.com/checkout/retry",
            )

        create_retry = create_lemon_subscription_checkout_factory(
            session_factory=session_factory,
            checkout_creator=retry_creator,
        )
        with pytest.raises(LemonSubscriptionCheckoutError, match="reconciliation"):
            await create_retry(uncertain_command)
        assert retry_calls == []
    finally:
        async with session_factory() as session:
            await session.execute(
                delete(AdminMarketLemonCheckoutBinding).where(
                    AdminMarketLemonCheckoutBinding.order_id.in_(
                        [success_order_id, uncertain_order_id]
                    )
                )
            )
            await session.execute(
                delete(AdminMarketOrder).where(
                    AdminMarketOrder.id.in_([success_order_id, uncertain_order_id])
                )
            )
            await session.execute(
                delete(AdminMarketOffer).where(AdminMarketOffer.id == offer_id)
            )
            await session.execute(
                delete(AdminMarketPlan).where(AdminMarketPlan.id == plan_id)
            )
            await session.commit()
        await engine.dispose()
