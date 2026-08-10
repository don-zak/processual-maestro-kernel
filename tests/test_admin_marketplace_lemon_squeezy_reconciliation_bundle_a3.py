from __future__ import annotations

import inspect
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

from processual_api.admin_marketplace.lemon_squeezy_inbox import LemonSqueezyWebhookInboxEntry
from processual_api.admin_marketplace.lemon_squeezy_reconciliation_gate import (
    LemonSqueezyReconciliationContext,
)
from processual_api.admin_marketplace.lemon_squeezy_reconciliation_persistence import (
    AdminMarketLemonSqueezyReconciliationDecision,
    LemonSqueezyReconciliationDecisionRecord,
    SqlAlchemyLemonSqueezyReconciliationDecisionRepository,
)
from processual_api.admin_marketplace.lemon_squeezy_reconciliation_processor import (
    process_lemon_squeezy_reconciliation_factory,
)
from processual_api.admin_marketplace.lemon_squeezy_webhooks import LemonSqueezyWebhookError

NOW = datetime(2026, 8, 5, 20, 0, tzinfo=timezone.utc)


def _inbox() -> LemonSqueezyWebhookInboxEntry:
    return LemonSqueezyWebhookInboxEntry(
        id=uuid.uuid4(),
        event_identity_hash="a" * 64,
        payload_digest="b" * 64,
        event_name="subscription_payment_success",
        resource_type="subscription-invoices",
        external_resource_id="9001",
        store_id="42",
        customer_ref="customer-1",
        order_ref="order-1",
        offer_ref="offer-1",
        test_mode=False,
        processing_status="received",
        attempt_count=0,
        received_at=NOW,
        evidence_schema_version=1,
        provider_customer_id="5001",
        provider_subscription_id="8001",
        currency="USD",
        total_amount="1999",
        provider_status="paid",
        provider_effective_at=NOW,
    )


def _context(**overrides) -> LemonSqueezyReconciliationContext:
    values = {
        "expected_customer_ref": "customer-1",
        "expected_order_ref": "order-1",
        "expected_offer_ref": "offer-1",
        "order_sales_channel": "lemon_squeezy",
        "offer_sales_channel": "lemon_squeezy",
        "production_mode": True,
        "expected_provider_customer_id": "5001",
    }
    values.update(overrides)
    return LemonSqueezyReconciliationContext(**values)


class Repo:
    def __init__(self, value=None) -> None:
        self.value = value
        self.added = []
        self.calls = []

    async def get_by_id(self, value, *, for_update=False):
        self.calls.append(("id", value, for_update))
        return self.value

    async def get_by_inbox_id(self, value, *, for_update=False):
        self.calls.append(("inbox", value, for_update))
        return self.value

    def add(self, value) -> None:
        self.added.append(value)


class Uow:
    def __init__(self, inbox, existing=None) -> None:
        self.lemon_squeezy_webhook_inbox = Repo(inbox)
        self.lemon_squeezy_reconciliation_decisions = Repo(existing)
        self.commits = 0
        self.exits = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        self.exits.append(exc_type)

    async def commit(self):
        self.commits += 1


@pytest.mark.asyncio
async def test_trusted_event_is_decided_and_committed_once() -> None:
    inbox = _inbox()
    uow = Uow(inbox)

    async def loader(value):
        assert value is inbox
        return _context()

    process = process_lemon_squeezy_reconciliation_factory(
        uow_factory=lambda: uow,
        context_loader=loader,
    )
    result = await process(inbox_id=inbox.id, decided_at=NOW)

    assert result.action == "reconcile"
    assert result.reason_code == "verified_evidence_requires_reconciliation"
    assert inbox.processing_status == "processed"
    assert inbox.attempt_count == 1
    assert uow.commits == 1
    assert len(uow.lemon_squeezy_reconciliation_decisions.added) == 1
    assert uow.lemon_squeezy_webhook_inbox.calls == [("id", inbox.id, True)]
    assert uow.lemon_squeezy_reconciliation_decisions.calls == [("inbox", inbox.id, True)]


@pytest.mark.asyncio
async def test_review_decision_rejects_inbox_without_subscription_mutation_api() -> None:
    inbox = _inbox()
    uow = Uow(inbox)

    async def loader(_):
        return _context(expected_provider_customer_id="5002")

    process = process_lemon_squeezy_reconciliation_factory(
        uow_factory=lambda: uow,
        context_loader=loader,
    )
    result = await process(inbox_id=inbox.id, decided_at=NOW)

    assert result.action == "requires_review"
    assert inbox.processing_status == "rejected"
    assert inbox.last_error_code == "provider_customer_mismatch"
    assert uow.commits == 1
    assert not any("subscription" in name or "entitlement" in name for name in dir(process))


@pytest.mark.asyncio
async def test_existing_decision_is_replayed_without_commit_or_context_reload() -> None:
    inbox = _inbox()
    inbox.processing_status = "processed"
    inbox.claimed_at = NOW
    inbox.processed_at = NOW
    existing = SimpleNamespace(
        id=uuid.uuid4(),
        inbox_id=inbox.id,
        event_identity_hash=inbox.event_identity_hash,
        customer_ref=inbox.customer_ref,
        order_ref=inbox.order_ref,
        offer_ref=inbox.offer_ref,
        action="reconcile",
        reason_code="verified_evidence_requires_reconciliation",
        decided_at=NOW,
    )
    uow = Uow(inbox, existing)

    async def loader(_):
        raise AssertionError("context must not be reloaded for immutable replay")

    process = process_lemon_squeezy_reconciliation_factory(
        uow_factory=lambda: uow,
        context_loader=loader,
    )
    result = await process(inbox_id=inbox.id, decided_at=NOW)

    assert result.id == existing.id
    assert uow.commits == 0
    assert uow.lemon_squeezy_reconciliation_decisions.added == []


@pytest.mark.asyncio
async def test_existing_decision_with_cross_account_binding_fails_closed() -> None:
    inbox = _inbox()
    existing = SimpleNamespace(
        id=uuid.uuid4(),
        inbox_id=inbox.id,
        event_identity_hash=inbox.event_identity_hash,
        customer_ref="customer-other",
        order_ref=inbox.order_ref,
        offer_ref=inbox.offer_ref,
        action="reconcile",
        reason_code="verified_evidence_requires_reconciliation",
        decided_at=NOW,
    )
    uow = Uow(inbox, existing)
    process = process_lemon_squeezy_reconciliation_factory(
        uow_factory=lambda: uow,
        context_loader=lambda _: None,
    )

    with pytest.raises(LemonSqueezyWebhookError):
        await process(inbox_id=inbox.id, decided_at=NOW)

    assert uow.commits == 0
    assert inbox.processing_status == "received"


@pytest.mark.asyncio
async def test_missing_inbox_and_naive_time_fail_without_commit() -> None:
    uow = Uow(None)
    process = process_lemon_squeezy_reconciliation_factory(
        uow_factory=lambda: uow,
        context_loader=lambda _: None,
    )

    with pytest.raises(LemonSqueezyWebhookError):
        await process(inbox_id=uuid.uuid4(), decided_at=NOW)
    assert uow.commits == 0

    with pytest.raises(LemonSqueezyWebhookError):
        await process(inbox_id=uuid.uuid4(), decided_at=datetime(2026, 8, 5))
    assert uow.commits == 0


def test_decision_model_matches_immutable_database_contract() -> None:
    table = AdminMarketLemonSqueezyReconciliationDecision.__table__
    assert table.name == "admin_market_lemon_squeezy_reconciliation_decisions"
    assert {constraint.name for constraint in table.constraints if constraint.__class__.__name__ == "UniqueConstraint"} == {
        "uq_admin_market_ls_reconciliation_inbox",
        "uq_admin_market_ls_reconciliation_event_identity",
    }
    assert {index.name for index in table.indexes} == {
        "ix_admin_market_ls_reconciliation_action_time",
        "ix_admin_market_ls_reconciliation_order_time",
    }


def test_repository_maps_domain_record_and_owns_no_transaction() -> None:
    session = MagicMock(spec=AsyncSession)
    repository = SqlAlchemyLemonSqueezyReconciliationDecisionRepository(session)
    record = LemonSqueezyReconciliationDecisionRecord(
        id=uuid.uuid4(),
        inbox_id=uuid.uuid4(),
        event_identity_hash="a" * 64,
        customer_ref="customer-1",
        order_ref="order-1",
        offer_ref="offer-1",
        action="reconcile",
        reason_code="verified_evidence_requires_reconciliation",
        decided_at=NOW,
    )
    repository.add(record)

    row = session.add.call_args.args[0]
    assert isinstance(row, AdminMarketLemonSqueezyReconciliationDecision)
    assert row.event_identity_hash == record.event_identity_hash
    assert row.customer_ref == record.customer_ref

    methods = {
        name
        for name, value in inspect.getmembers(type(repository))
        if callable(value) and not name.startswith("_")
    }
    assert methods.isdisjoint({"commit", "rollback", "activate_subscription", "reconcile_payment"})


@pytest.mark.asyncio
async def test_repository_uses_for_update_for_decision_lock() -> None:
    class Session:
        def __init__(self):
            self.statement = None
        async def scalar(self, statement):
            self.statement = statement
            return None

    session = Session()
    repository = SqlAlchemyLemonSqueezyReconciliationDecisionRepository(session)  # type: ignore[arg-type]
    await repository.get_by_inbox_id(uuid.uuid4(), for_update=True)
    sql = str(session.statement.compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE" in sql
