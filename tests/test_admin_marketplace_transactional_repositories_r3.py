from __future__ import annotations

import inspect
import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

from processual_api.admin_marketplace.models import (
    AdminMarketOrder,
    AdminMarketSubscription,
    AdminMarketTrial,
)
from processual_api.admin_marketplace.persistence.protocols import (
    OrderRepository,
    SubscriptionRepository,
    TrialRepository,
)
from processual_api.admin_marketplace.persistence.repositories import (
    SqlAlchemyOrderRepository,
    SqlAlchemySubscriptionRepository,
    SqlAlchemyTrialRepository,
)


class FakeAsyncSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.scalar_statements: list[object] = []
        self.scalar_result: object | None = None

    def add(self, value: object) -> None:
        self.added.append(value)

    async def scalar(self, statement: object) -> object | None:
        self.scalar_statements.append(statement)
        return self.scalar_result


def _compile_postgresql(statement: object) -> str:
    return str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": False},
        )
    )


def _public_methods(repository_type: type) -> set[str]:
    return {name for name, value in inspect.getmembers(repository_type) if callable(value) and not name.startswith("_")}


@pytest.mark.parametrize(
    ("repository_type", "model_type", "table_name"),
    (
        (
            SqlAlchemySubscriptionRepository,
            AdminMarketSubscription,
            "admin_market_subscriptions",
        ),
        (
            SqlAlchemyTrialRepository,
            AdminMarketTrial,
            "admin_market_trials",
        ),
        (
            SqlAlchemyOrderRepository,
            AdminMarketOrder,
            "admin_market_orders",
        ),
    ),
)
@pytest.mark.asyncio
async def test_transactional_repository_adds_and_reads_without_lock(
    repository_type: type,
    model_type: type,
    table_name: str,
) -> None:
    session = FakeAsyncSession()
    repository = repository_type(session)

    row_id = uuid.uuid4()
    row = MagicMock(spec=model_type)
    session.scalar_result = row

    repository.add(row)
    result = await repository.get_by_id(row_id)

    assert session.added == [row]
    assert result is row
    assert len(session.scalar_statements) == 1

    sql = _compile_postgresql(session.scalar_statements[0])

    assert f"FROM {table_name}" in sql
    assert "FOR UPDATE" not in sql


@pytest.mark.parametrize(
    ("repository_type", "table_name"),
    (
        (
            SqlAlchemySubscriptionRepository,
            "admin_market_subscriptions",
        ),
        (
            SqlAlchemyTrialRepository,
            "admin_market_trials",
        ),
        (
            SqlAlchemyOrderRepository,
            "admin_market_orders",
        ),
    ),
)
@pytest.mark.asyncio
async def test_transactional_repository_supports_row_locking(
    repository_type: type,
    table_name: str,
) -> None:
    session = FakeAsyncSession()
    repository = repository_type(session)

    await repository.get_by_id(
        uuid.uuid4(),
        for_update=True,
    )

    assert len(session.scalar_statements) == 1

    sql = _compile_postgresql(session.scalar_statements[0])

    assert f"FROM {table_name}" in sql
    assert "FOR UPDATE" in sql


@pytest.mark.parametrize(
    ("implementation", "protocol"),
    (
        (
            SqlAlchemySubscriptionRepository,
            SubscriptionRepository,
        ),
        (
            SqlAlchemyTrialRepository,
            TrialRepository,
        ),
        (
            SqlAlchemyOrderRepository,
            OrderRepository,
        ),
    ),
)
def test_transactional_repository_matches_protocol(
    implementation: type,
    protocol: type,
) -> None:
    session = MagicMock(spec=AsyncSession)
    repository = implementation(session)

    assert isinstance(repository, protocol)


@pytest.mark.parametrize(
    "repository_type",
    (
        SqlAlchemySubscriptionRepository,
        SqlAlchemyTrialRepository,
        SqlAlchemyOrderRepository,
    ),
)
def test_transactional_repositories_do_not_own_transactions(
    repository_type: type,
) -> None:
    methods = _public_methods(repository_type)

    assert methods.isdisjoint(
        {
            "begin",
            "close",
            "commit",
            "create_session",
            "rollback",
        }
    )


@pytest.mark.parametrize(
    "repository_type",
    (
        SqlAlchemySubscriptionRepository,
        SqlAlchemyTrialRepository,
        SqlAlchemyOrderRepository,
    ),
)
def test_transactional_repositories_have_no_automatic_activation_api(
    repository_type: type,
) -> None:
    methods = _public_methods(repository_type)

    assert methods.isdisjoint(
        {
            "activate_after_payment",
            "activate_entitlements",
            "activate_subscription",
            "auto_activate",
            "verify_and_activate",
        }
    )


@pytest.mark.parametrize(
    "repository_type",
    (
        SqlAlchemySubscriptionRepository,
        SqlAlchemyTrialRepository,
        SqlAlchemyOrderRepository,
    ),
)
def test_transactional_repositories_have_no_generic_mutation_api(
    repository_type: type,
) -> None:
    methods = _public_methods(repository_type)

    assert methods.isdisjoint(
        {
            "delete",
            "patch",
            "save",
            "save_or_update",
            "update",
            "upsert",
        }
    )
