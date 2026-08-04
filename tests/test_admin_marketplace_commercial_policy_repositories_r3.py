from __future__ import annotations

import inspect
import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

from processual_api.admin_marketplace.models import (
    AdminMarketChannelEligibility,
    AdminMarketChannelSelection,
    AdminMarketCommercialDecision,
)
from processual_api.admin_marketplace.persistence.protocols import (
    ChannelEligibilityRepository,
    ChannelSelectionRepository,
    CommercialDecisionRepository,
)
from processual_api.admin_marketplace.persistence.repositories import (
    SqlAlchemyChannelEligibilityRepository,
    SqlAlchemyChannelSelectionRepository,
    SqlAlchemyCommercialDecisionRepository,
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


REPOSITORIES = (
    (
        SqlAlchemyChannelEligibilityRepository,
        AdminMarketChannelEligibility,
        "admin_market_channel_eligibilities",
    ),
    (
        SqlAlchemyChannelSelectionRepository,
        AdminMarketChannelSelection,
        "admin_market_channel_selections",
    ),
    (
        SqlAlchemyCommercialDecisionRepository,
        AdminMarketCommercialDecision,
        "admin_market_commercial_decisions",
    ),
)


@pytest.mark.parametrize(
    ("repository_type", "model_type", "table_name"),
    REPOSITORIES,
)
@pytest.mark.asyncio
async def test_commercial_policy_repository_adds_and_reads(
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
    ("repository_type", "_model_type", "table_name"),
    REPOSITORIES,
)
@pytest.mark.asyncio
async def test_commercial_policy_repository_supports_locking(
    repository_type: type,
    _model_type: type,
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


@pytest.mark.asyncio
async def test_channel_eligibility_repository_reads_by_customer_ref() -> None:
    session = FakeAsyncSession()
    repository = SqlAlchemyChannelEligibilityRepository(session)

    row = MagicMock(spec=AdminMarketChannelEligibility)
    session.scalar_result = row

    result = await repository.get_by_customer_ref("customer_001")

    assert result is row
    assert len(session.scalar_statements) == 1

    sql = _compile_postgresql(session.scalar_statements[0])

    assert "FROM admin_market_channel_eligibilities" in sql
    assert "customer_ref" in sql
    assert "FOR UPDATE" not in sql


@pytest.mark.asyncio
async def test_channel_eligibility_repository_customer_lookup_supports_locking() -> None:
    session = FakeAsyncSession()
    repository = SqlAlchemyChannelEligibilityRepository(session)

    await repository.get_by_customer_ref(
        "customer_001",
        for_update=True,
    )

    assert len(session.scalar_statements) == 1

    sql = _compile_postgresql(session.scalar_statements[0])

    assert "FROM admin_market_channel_eligibilities" in sql
    assert "customer_ref" in sql
    assert "FOR UPDATE" in sql


@pytest.mark.parametrize(
    ("implementation", "protocol"),
    (
        (
            SqlAlchemyChannelEligibilityRepository,
            ChannelEligibilityRepository,
        ),
        (
            SqlAlchemyChannelSelectionRepository,
            ChannelSelectionRepository,
        ),
        (
            SqlAlchemyCommercialDecisionRepository,
            CommercialDecisionRepository,
        ),
    ),
)
def test_commercial_policy_repository_matches_protocol(
    implementation: type,
    protocol: type,
) -> None:
    repository = implementation(MagicMock(spec=AsyncSession))

    assert isinstance(repository, protocol)


@pytest.mark.parametrize(
    "repository_type",
    (
        SqlAlchemyChannelEligibilityRepository,
        SqlAlchemyChannelSelectionRepository,
        SqlAlchemyCommercialDecisionRepository,
    ),
)
def test_commercial_policy_repositories_do_not_own_transactions(
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
        SqlAlchemyChannelEligibilityRepository,
        SqlAlchemyChannelSelectionRepository,
        SqlAlchemyCommercialDecisionRepository,
    ),
)
def test_commercial_policy_repositories_have_no_authority_api(
    repository_type: type,
) -> None:
    methods = _public_methods(repository_type)

    assert methods.isdisjoint(
        {
            "allow_delegated_supervisor",
            "assert_platform_admin",
            "authorize",
            "bypass_authority",
            "check_mfa",
            "elevate_role",
            "override_authority",
        }
    )


@pytest.mark.parametrize(
    "repository_type",
    (
        SqlAlchemyChannelEligibilityRepository,
        SqlAlchemyChannelSelectionRepository,
        SqlAlchemyCommercialDecisionRepository,
    ),
)
def test_commercial_policy_repositories_have_no_policy_engine_api(
    repository_type: type,
) -> None:
    methods = _public_methods(repository_type)

    assert methods.isdisjoint(
        {
            "calculate_eligibility",
            "choose_channel",
            "decide",
            "evaluate",
            "override_channel",
            "select_best_channel",
        }
    )


@pytest.mark.parametrize(
    "repository_type",
    (
        SqlAlchemyChannelEligibilityRepository,
        SqlAlchemyChannelSelectionRepository,
        SqlAlchemyCommercialDecisionRepository,
    ),
)
def test_commercial_policy_repositories_have_no_generic_mutation_api(
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
