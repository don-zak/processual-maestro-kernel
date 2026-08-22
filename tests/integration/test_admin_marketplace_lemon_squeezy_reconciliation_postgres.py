from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from processual_api.admin_marketplace.lemon_squeezy_binding_persistence import (
    AdminMarketLemonSqueezyBinding,
    AdminMarketLemonSqueezyCustomerBinding,
)
from processual_api.admin_marketplace.lemon_squeezy_context_loader import (
    lemon_squeezy_reconciliation_context_loader_factory,
)
from processual_api.admin_marketplace.lemon_squeezy_persistence import (
    AdminMarketLemonSqueezyWebhookInbox,
)
from processual_api.admin_marketplace.lemon_squeezy_reconciliation_persistence import (
    AdminMarketLemonSqueezyReconciliationDecision,
)
from processual_api.admin_marketplace.lemon_squeezy_reconciliation_processor import (
    process_lemon_squeezy_reconciliation_factory,
)
from processual_api.admin_marketplace.lemon_squeezy_webhooks import (
    LemonSqueezyWebhookError,
)
from processual_api.admin_marketplace.models import (
    AdminMarketOffer,
    AdminMarketOrder,
    AdminMarketPlan,
    AdminMarketSubscription,
)
from processual_api.admin_marketplace.persistence.unit_of_work import (
    SqlAlchemyAdminMarketplaceUnitOfWork,
)
from processual_api.admin_marketplace.subscription_runtime_persistence import (
    AdminMarketSubscriptionRuntime,
)
from processual_api.admin_marketplace.subscription_runtime_transition_persistence import (
    AdminMarketSubscriptionRuntimeTransition,
)

DATABASE_URL = os.environ.get("ADMIN_MARKET_INTEGRATION_DATABASE_URL", "")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason=(
        "Set ADMIN_MARKET_INTEGRATION_DATABASE_URL to a migrated PostgreSQL "
        "database to run the Admin Marketplace reconciliation gate."
    ),
)

NOW = datetime(2026, 8, 22, 10, 45, tzinfo=UTC)
EARLIER = NOW - timedelta(hours=1)


def _async_database_url() -> str:
    if DATABASE_URL.startswith("postgresql+asyncpg://"):
        return DATABASE_URL
    return DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)


@pytest.mark.asyncio
async def test_reconciliation_updates_subscription_and_runtime_atomically_and_rolls_back_conflict() -> None:
    engine = create_async_engine(_async_database_url())
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    suffix = uuid.uuid4().hex[:18]
    plan_id = uuid.uuid4()
    offer_id = uuid.uuid4()
    order_id = uuid.uuid4()
    subscription_id = uuid.uuid4()
    runtime_id = uuid.uuid4()
    customer_binding_id = uuid.uuid4()
    provider_binding_id = uuid.uuid4()
    good_inbox_id = uuid.uuid4()
    bad_inbox_id = uuid.uuid4()

    customer_ref = f"pg-rec-customer-{suffix}"
    plan_code = f"pg-rec-plan-{suffix}"
    offer_code = f"pg-rec-offer-{suffix}"
    order_ref = f"pg-rec-order-{suffix}"
    subscription_ref = f"pg-rec-sub-{suffix}"
    provider_customer_id = str(500_000_000 + uuid.uuid4().int % 400_000_000)
    provider_order_id = str(500_000_000 + uuid.uuid4().int % 400_000_000)
    provider_subscription_id = str(500_000_000 + uuid.uuid4().int % 400_000_000)
    variant_id = str(500_000_000 + uuid.uuid4().int % 400_000_000)

    async with session_factory() as session:
        session.add_all(
            [
                AdminMarketPlan(
                    id=plan_id,
                    plan_code=plan_code,
                    display_name="PostgreSQL reconciliation plan",
                    entitlement_profile_ref=f"ent-{suffix}",
                    quota_profile_ref=f"quota-{suffix}",
                    metadata_json={},
                ),
                AdminMarketOffer(
                    id=offer_id,
                    offer_code=offer_code,
                    plan_id=plan_id,
                    display_name="PostgreSQL reconciliation offer",
                    currency="USD",
                    sales_channel="lemon_squeezy",
                    billing_period="monthly",
                    amount=Decimal("10.000"),
                    status="published",
                    effective_at=EARLIER,
                    expires_at=None,
                    customer_specific=False,
                ),
                AdminMarketOrder(
                    id=order_id,
                    order_ref=order_ref,
                    customer_ref=customer_ref,
                    offer_id=offer_id,
                    plan_id=plan_id,
                    billing_period="monthly",
                    selected_channel="lemon_squeezy",
                    country_code="US",
                    currency="USD",
                    subtotal_amount=Decimal("10.000"),
                    tax_amount=Decimal("0.000"),
                    total_amount=Decimal("10.000"),
                    status="activated",
                    contract_status="completed",
                    payment_requirement="required",
                    payment_status="verified",
                    payment_reference=f"pay-{suffix}",
                    payment_destination_snapshot={},
                    offer_snapshot={},
                    creation_idempotency_key_hash=None,
                    completed_at=EARLIER,
                    cancelled_at=None,
                ),
                AdminMarketSubscription(
                    id=subscription_id,
                    subscription_ref=subscription_ref,
                    customer_ref=customer_ref,
                    order_id=order_id,
                    offer_id=offer_id,
                    plan_id=plan_id,
                    status="suspended",
                    starts_at=EARLIER,
                    ends_at=None,
                ),
                AdminMarketLemonSqueezyCustomerBinding(
                    id=customer_binding_id,
                    customer_ref=customer_ref,
                    provider_customer_id=provider_customer_id,
                ),
                AdminMarketLemonSqueezyBinding(
                    id=provider_binding_id,
                    customer_ref=customer_ref,
                    order_id=order_id,
                    offer_id=offer_id,
                    subscription_id=subscription_id,
                    provider_customer_id=provider_customer_id,
                    provider_order_id=provider_order_id,
                    provider_subscription_id=provider_subscription_id,
                    variant_id=variant_id,
                    currency="USD",
                    total_amount="10.000",
                    last_provider_effective_at=EARLIER,
                ),
                AdminMarketSubscriptionRuntime(
                    id=runtime_id,
                    subscription_id=subscription_id,
                    customer_ref=customer_ref,
                    entitlement_profile_ref=f"ent-{suffix}",
                    quota_profile_ref=f"quota-{suffix}",
                    access_stage="suspended",
                    version=2,
                    effective_at=EARLIER,
                    grace_until=None,
                    suspended_at=EARLIER,
                    terminated_at=None,
                ),
                AdminMarketLemonSqueezyWebhookInbox(
                    id=good_inbox_id,
                    event_identity_hash=("a" + uuid.uuid4().hex * 2)[:64],
                    payload_digest=("b" + uuid.uuid4().hex * 2)[:64],
                    event_name="subscription_updated",
                    resource_type="subscriptions",
                    external_resource_id=provider_subscription_id,
                    store_id="7001",
                    customer_ref=customer_ref,
                    order_ref=order_ref,
                    offer_ref=offer_code,
                    test_mode=False,
                    processing_status="received",
                    attempt_count=0,
                    evidence_schema_version=1,
                    provider_customer_id=provider_customer_id,
                    provider_order_id=provider_order_id,
                    provider_subscription_id=provider_subscription_id,
                    variant_id=variant_id,
                    currency=None,
                    subtotal_amount=None,
                    total_amount=None,
                    refunded_amount=None,
                    provider_status="active",
                    provider_effective_at=NOW,
                    last_error_code=None,
                    received_at=NOW,
                    claimed_at=None,
                    processed_at=None,
                    rejected_at=None,
                ),
            ]
        )
        await session.commit()

    uow_factory = lambda: SqlAlchemyAdminMarketplaceUnitOfWork(session_factory)
    process = process_lemon_squeezy_reconciliation_factory(
        uow_factory=uow_factory,
        context_loader=lemon_squeezy_reconciliation_context_loader_factory(
            production_mode=True,
        ),
    )

    try:
        first = await process(inbox_id=good_inbox_id, decided_at=NOW)
        assert first.action == "reconcile"
        assert first.reason_code == "verified_evidence_requires_reconciliation"

        async with session_factory() as session:
            subscription = await session.get(AdminMarketSubscription, subscription_id)
            runtime = await session.get(AdminMarketSubscriptionRuntime, runtime_id)
            inbox = await session.get(AdminMarketLemonSqueezyWebhookInbox, good_inbox_id)
            decision = await session.scalar(
                select(AdminMarketLemonSqueezyReconciliationDecision).where(
                    AdminMarketLemonSqueezyReconciliationDecision.inbox_id == good_inbox_id
                )
            )
            transition = await session.scalar(
                select(AdminMarketSubscriptionRuntimeTransition).where(
                    AdminMarketSubscriptionRuntimeTransition.reconciliation_decision_id == first.id
                )
            )

            assert subscription is not None and subscription.status == "active"
            assert runtime is not None and runtime.access_stage == "active"
            assert runtime.version == 3
            assert runtime.effective_at == NOW
            assert runtime.suspended_at is None
            assert inbox is not None and inbox.processing_status == "processed"
            assert inbox.attempt_count == 1
            assert inbox.processed_at == NOW
            assert decision is not None and decision.action == "reconcile"
            assert transition is not None
            assert transition.from_stage == "suspended"
            assert transition.to_stage == "active"
            assert transition.event_name == "subscription_updated"

        replay = await process(inbox_id=good_inbox_id, decided_at=NOW + timedelta(minutes=1))
        assert replay.id == first.id

        async with session_factory() as session:
            runtime = await session.get(AdminMarketSubscriptionRuntime, runtime_id)
            transitions = (
                await session.scalars(
                    select(AdminMarketSubscriptionRuntimeTransition).where(
                        AdminMarketSubscriptionRuntimeTransition.subscription_id == subscription_id
                    )
                )
            ).all()
            assert runtime is not None and runtime.version == 3
            assert len(transitions) == 1

        async with session_factory() as session:
            session.add(
                AdminMarketLemonSqueezyWebhookInbox(
                    id=bad_inbox_id,
                    event_identity_hash=("c" + uuid.uuid4().hex * 2)[:64],
                    payload_digest=("d" + uuid.uuid4().hex * 2)[:64],
                    event_name="subscription_updated",
                    resource_type="subscriptions",
                    external_resource_id=provider_subscription_id,
                    store_id="7001",
                    customer_ref=customer_ref,
                    order_ref=order_ref,
                    offer_ref=offer_code,
                    test_mode=False,
                    processing_status="received",
                    attempt_count=0,
                    evidence_schema_version=1,
                    provider_customer_id="999999999",
                    provider_order_id=provider_order_id,
                    provider_subscription_id=provider_subscription_id,
                    variant_id=variant_id,
                    currency=None,
                    subtotal_amount=None,
                    total_amount=None,
                    refunded_amount=None,
                    provider_status="active",
                    provider_effective_at=NOW + timedelta(minutes=2),
                    last_error_code=None,
                    received_at=NOW + timedelta(minutes=2),
                    claimed_at=None,
                    processed_at=None,
                    rejected_at=None,
                )
            )
            await session.commit()

        with pytest.raises(LemonSqueezyWebhookError):
            await process(
                inbox_id=bad_inbox_id,
                decided_at=NOW + timedelta(minutes=2),
            )

        async with session_factory() as session:
            bad_inbox = await session.get(AdminMarketLemonSqueezyWebhookInbox, bad_inbox_id)
            bad_decision = await session.scalar(
                select(AdminMarketLemonSqueezyReconciliationDecision).where(
                    AdminMarketLemonSqueezyReconciliationDecision.inbox_id == bad_inbox_id
                )
            )
            runtime = await session.get(AdminMarketSubscriptionRuntime, runtime_id)
            subscription = await session.get(AdminMarketSubscription, subscription_id)

            assert bad_inbox is not None
            assert bad_inbox.processing_status == "received"
            assert bad_inbox.attempt_count == 0
            assert bad_inbox.claimed_at is None
            assert bad_inbox.processed_at is None
            assert bad_inbox.rejected_at is None
            assert bad_decision is None
            assert runtime is not None and runtime.access_stage == "active"
            assert runtime.version == 3
            assert subscription is not None and subscription.status == "active"
    finally:
        async with session_factory() as session:
            await session.execute(
                delete(AdminMarketSubscriptionRuntimeTransition).where(
                    AdminMarketSubscriptionRuntimeTransition.subscription_id == subscription_id
                )
            )
            await session.execute(
                delete(AdminMarketLemonSqueezyReconciliationDecision).where(
                    AdminMarketLemonSqueezyReconciliationDecision.inbox_id.in_(
                        [good_inbox_id, bad_inbox_id]
                    )
                )
            )
            await session.execute(
                delete(AdminMarketLemonSqueezyWebhookInbox).where(
                    AdminMarketLemonSqueezyWebhookInbox.id.in_([good_inbox_id, bad_inbox_id])
                )
            )
            await session.execute(
                delete(AdminMarketSubscriptionRuntime).where(
                    AdminMarketSubscriptionRuntime.subscription_id == subscription_id
                )
            )
            await session.execute(
                delete(AdminMarketLemonSqueezyBinding).where(
                    AdminMarketLemonSqueezyBinding.id == provider_binding_id
                )
            )
            await session.execute(
                delete(AdminMarketLemonSqueezyCustomerBinding).where(
                    AdminMarketLemonSqueezyCustomerBinding.id == customer_binding_id
                )
            )
            await session.execute(
                delete(AdminMarketSubscription).where(
                    AdminMarketSubscription.id == subscription_id
                )
            )
            await session.execute(delete(AdminMarketOrder).where(AdminMarketOrder.id == order_id))
            await session.execute(delete(AdminMarketOffer).where(AdminMarketOffer.id == offer_id))
            await session.execute(delete(AdminMarketPlan).where(AdminMarketPlan.id == plan_id))
            await session.commit()
        await engine.dispose()
