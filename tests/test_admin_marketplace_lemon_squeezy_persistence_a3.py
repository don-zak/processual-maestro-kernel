from __future__ import annotations

import inspect
import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

from processual_api.admin_marketplace.lemon_squeezy_persistence import (
    AdminMarketLemonSqueezyWebhookInbox,
    SqlAlchemyLemonSqueezyWebhookInboxRepository,
)


class FakeAsyncSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.scalar_result: object | None = None
        self.scalar_statements: list[object] = []

    def add(self, value: object) -> None:
        self.added.append(value)

    async def scalar(self, statement: object) -> object | None:
        self.scalar_statements.append(statement)
        return self.scalar_result


def _compile(statement: object) -> str:
    return str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": False},
        )
    )


def _public_methods(repository_type: type) -> set[str]:
    return {
        name
        for name, value in inspect.getmembers(repository_type)
        if callable(value) and not name.startswith("_")
    }


def test_webhook_inbox_model_matches_migration_contract() -> None:
    table = AdminMarketLemonSqueezyWebhookInbox.__table__

    assert table.name == "admin_market_lemon_squeezy_webhook_inbox"
    assert {column.name for column in table.columns} == {
        "id",
        "event_identity_hash",
        "payload_digest",
        "event_name",
        "resource_type",
        "external_resource_id",
        "store_id",
        "customer_ref",
        "order_ref",
        "offer_ref",
        "test_mode",
        "processing_status",
        "attempt_count",
        "last_error_code",
        "received_at",
        "claimed_at",
        "processed_at",
        "rejected_at",
        "created_at",
    }

    unique_names = {
        constraint.name
        for constraint in table.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert unique_names == {
        "uq_admin_market_ls_webhook_event_identity",
        "uq_admin_market_ls_webhook_payload_digest",
        "uq_admin_market_ls_webhook_resource_binding",
    }

    index_names = {index.name for index in table.indexes}
    assert index_names == {
        "ix_admin_market_ls_webhook_dispatch",
        "ix_admin_market_ls_webhook_order_time",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "value", "column_name"),
    (
        ("get_by_event_identity_hash", "a" * 64, "event_identity_hash"),
        ("get_by_payload_digest", "b" * 64, "payload_digest"),
        ("get_by_id", uuid.uuid4(), "id"),
    ),
)
async def test_repository_supports_optional_row_locking(
    method_name: str,
    value: object,
    column_name: str,
) -> None:
    session = FakeAsyncSession()
    repository = SqlAlchemyLemonSqueezyWebhookInboxRepository(session)  # type: ignore[arg-type]

    await getattr(repository, method_name)(value, for_update=True)

    assert len(session.scalar_statements) == 1
    sql = _compile(session.scalar_statements[0])
    assert "FROM admin_market_lemon_squeezy_webhook_inbox" in sql
    assert column_name in sql
    assert "FOR UPDATE" in sql


@pytest.mark.asyncio
async def test_repository_reads_without_lock_by_default_and_adds_only() -> None:
    session = FakeAsyncSession()
    repository = SqlAlchemyLemonSqueezyWebhookInboxRepository(session)  # type: ignore[arg-type]
    row = MagicMock(spec=AdminMarketLemonSqueezyWebhookInbox)
    session.scalar_result = row

    result = await repository.get_by_event_identity_hash("a" * 64)
    repository.add(row)

    assert result is row
    assert session.added == [row]
    assert "FOR UPDATE" not in _compile(session.scalar_statements[0])


def test_repository_does_not_own_transactions_or_activation() -> None:
    repository = SqlAlchemyLemonSqueezyWebhookInboxRepository(
        MagicMock(spec=AsyncSession)
    )
    methods = _public_methods(type(repository))

    assert methods.isdisjoint(
        {
            "begin",
            "close",
            "commit",
            "rollback",
            "create_session",
            "activate_subscription",
            "activate_entitlements",
            "verify_and_activate",
            "reconcile_payment",
        }
    )
