from __future__ import annotations

import inspect
import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

from processual_api.admin_marketplace.models import (
    AdminMarketAuditRecord,
    AdminMarketOffer,
    AdminMarketPlan,
)
from processual_api.admin_marketplace.persistence.protocols import (
    CommercialAuditRepository,
    OfferRepository,
    PlanRepository,
)
from processual_api.admin_marketplace.persistence.repositories import (
    SqlAlchemyCommercialAuditRepository,
    SqlAlchemyOfferRepository,
    SqlAlchemyPlanRepository,
)


class FakeScalarResult:
    def __init__(self, values: list[object]) -> None:
        self._values = values

    def all(self) -> list[object]:
        return self._values


class FakeAsyncSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.get_calls: list[tuple[type, uuid.UUID]] = []
        self.scalar_statements: list[object] = []
        self.scalars_statements: list[object] = []
        self.get_result: object | None = None
        self.scalar_result: object | None = None
        self.scalars_result: list[object] = []

    def add(self, value: object) -> None:
        self.added.append(value)

    async def get(
        self,
        model: type,
        row_id: uuid.UUID,
    ) -> object | None:
        self.get_calls.append((model, row_id))
        return self.get_result

    async def scalar(self, statement: object) -> object | None:
        self.scalar_statements.append(statement)
        return self.scalar_result

    async def scalars(self, statement: object) -> FakeScalarResult:
        self.scalars_statements.append(statement)
        return FakeScalarResult(self.scalars_result)


def _compile_postgresql(statement: object) -> str:
    return str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": False},
        )
    )


def _public_methods(repository_type: type) -> set[str]:
    return {name for name, value in inspect.getmembers(repository_type) if callable(value) and not name.startswith("_")}


@pytest.mark.asyncio
async def test_plan_repository_adds_and_reads_by_id() -> None:
    session = FakeAsyncSession()
    repository = SqlAlchemyPlanRepository(session)  # type: ignore[arg-type]

    plan_id = uuid.uuid4()
    plan = MagicMock(spec=AdminMarketPlan)
    session.get_result = plan

    repository.add(plan)
    result = await repository.get_by_id(plan_id)

    assert session.added == [plan]
    assert session.get_calls == [(AdminMarketPlan, plan_id)]
    assert result is plan


@pytest.mark.asyncio
async def test_offer_repository_adds_and_reads_without_lock() -> None:
    session = FakeAsyncSession()
    repository = SqlAlchemyOfferRepository(session)  # type: ignore[arg-type]

    offer_id = uuid.uuid4()
    offer = MagicMock(spec=AdminMarketOffer)
    session.scalar_result = offer

    repository.add(offer)
    result = await repository.get_by_id(offer_id)

    assert session.added == [offer]
    assert result is offer
    assert len(session.scalar_statements) == 1

    sql = _compile_postgresql(session.scalar_statements[0])

    assert "FROM admin_market_offers" in sql
    assert "FOR UPDATE" not in sql


@pytest.mark.asyncio
async def test_offer_repository_supports_row_locking() -> None:
    session = FakeAsyncSession()
    repository = SqlAlchemyOfferRepository(session)  # type: ignore[arg-type]

    await repository.get_by_id(
        uuid.uuid4(),
        for_update=True,
    )

    assert len(session.scalar_statements) == 1

    sql = _compile_postgresql(session.scalar_statements[0])

    assert "FROM admin_market_offers" in sql
    assert "FOR UPDATE" in sql


@pytest.mark.asyncio
async def test_audit_repository_appends_and_reads_by_id() -> None:
    session = FakeAsyncSession()
    repository = SqlAlchemyCommercialAuditRepository(
        session,  # type: ignore[arg-type]
    )

    audit_id = uuid.uuid4()
    audit_record = MagicMock(spec=AdminMarketAuditRecord)
    session.get_result = audit_record

    repository.append(audit_record)
    result = await repository.get_by_id(audit_id)

    assert session.added == [audit_record]
    assert session.get_calls == [
        (
            AdminMarketAuditRecord,
            audit_id,
        )
    ]
    assert result is audit_record


@pytest.mark.asyncio
async def test_audit_repository_lists_resource_history() -> None:
    session = FakeAsyncSession()
    repository = SqlAlchemyCommercialAuditRepository(
        session,  # type: ignore[arg-type]
    )

    first = MagicMock(spec=AdminMarketAuditRecord)
    second = MagicMock(spec=AdminMarketAuditRecord)
    session.scalars_result = [first, second]

    result = await repository.list_by_resource(
        resource_type="offer",
        resource_id="offer-123",
    )

    assert result == (first, second)
    assert len(session.scalars_statements) == 1

    sql = _compile_postgresql(session.scalars_statements[0])

    assert "FROM admin_market_audit_records" in sql
    assert "resource_type" in sql
    assert "resource_id" in sql
    assert "ORDER BY" in sql
    assert "occurred_at ASC" in sql


@pytest.mark.parametrize(
    ("implementation", "protocol"),
    (
        (SqlAlchemyPlanRepository, PlanRepository),
        (SqlAlchemyOfferRepository, OfferRepository),
        (
            SqlAlchemyCommercialAuditRepository,
            CommercialAuditRepository,
        ),
    ),
)
def test_repository_implementations_match_protocols(
    implementation: type,
    protocol: type,
) -> None:
    session = MagicMock(spec=AsyncSession)
    repository = implementation(session)

    assert isinstance(repository, protocol)


@pytest.mark.parametrize(
    "repository_type",
    (
        SqlAlchemyPlanRepository,
        SqlAlchemyOfferRepository,
        SqlAlchemyCommercialAuditRepository,
    ),
)
def test_repositories_do_not_own_transaction_boundary(
    repository_type: type,
) -> None:
    methods = _public_methods(repository_type)

    assert "commit" not in methods
    assert "rollback" not in methods
    assert "close" not in methods
    assert "create_session" not in methods


def test_audit_repository_is_append_only() -> None:
    methods = _public_methods(
        SqlAlchemyCommercialAuditRepository,
    )

    assert {"append", "get_by_id", "list_by_resource"} <= methods

    assert methods.isdisjoint(
        {
            "delete",
            "save",
            "save_or_update",
            "update",
            "upsert",
        }
    )
