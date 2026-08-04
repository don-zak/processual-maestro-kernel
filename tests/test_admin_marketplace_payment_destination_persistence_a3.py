from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import CheckConstraint, Index, UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

from processual_api.admin_marketplace.models import (
    ADMIN_MARKET_MODELS,
    AdminMarketPaymentDestination,
)
from processual_api.admin_marketplace.persistence import (
    PaymentDestinationRepository,
    SqlAlchemyPaymentDestinationRepository,
)
from processual_api.admin_marketplace.persistence.unit_of_work import (
    SqlAlchemyAdminMarketplaceUnitOfWork,
)


def test_payment_destination_model_is_registered() -> None:
    assert AdminMarketPaymentDestination in ADMIN_MARKET_MODELS
    assert (
        AdminMarketPaymentDestination.__tablename__
        == "admin_market_payment_destinations"
    )


def test_payment_destination_model_has_tunisia_constraints() -> None:
    table = AdminMarketPaymentDestination.__table__

    constraints = {
        constraint.name: constraint
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert "ck_admin_market_payment_destinations_country_tunisia_only" in constraints
    assert "ck_admin_market_payment_destinations_currency_tnd_only" in constraints
    assert (
        "ck_admin_market_payment_destinations_channel_direct"
        in constraints
    )

    assert (
        str(
            constraints[
                "ck_admin_market_payment_destinations_country_tunisia_only"
            ].sqltext
        ).strip()
        == "country_code = 'TN'"
    )
    assert (
        str(
            constraints[
                "ck_admin_market_payment_destinations_currency_tnd_only"
            ].sqltext
        ).strip()
        == "currency = 'TND'"
    )


def test_payment_destination_model_has_unique_reference() -> None:
    table = AdminMarketPaymentDestination.__table__

    unique_constraints = {
        constraint.name: constraint
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    constraint = unique_constraints[
        "uq_admin_market_payment_destinations_destination_ref"
    ]

    assert tuple(column.name for column in constraint.columns) == (
        "destination_ref",
    )

    idempotency_constraint = unique_constraints[
        "uq_admin_market_payment_destinations_create_idem_hash"
    ]
    assert tuple(
        column.name for column in idempotency_constraint.columns
    ) == ("creation_idempotency_key_hash",)


def test_payment_destination_default_index_is_partial_and_unique() -> None:
    table = AdminMarketPaymentDestination.__table__

    indexes = {
        index.name: index
        for index in table.indexes
        if isinstance(index, Index)
    }

    index = indexes[
        "uq_admin_market_payment_destinations_active_default"
    ]

    assert index.unique is True
    assert tuple(column.name for column in index.columns) == (
        "sales_channel",
    )

    predicate = str(
        index.dialect_options["postgresql"]["where"].compile(
            dialect=postgresql.dialect(),
        )
    )

    assert predicate == "is_active AND is_default"


def test_payment_destination_model_does_not_store_plain_identifier() -> None:
    column_names = set(AdminMarketPaymentDestination.__table__.c.keys())

    assert "raw_account_identifier" not in column_names
    assert "normalized_identifier" not in column_names
    assert "identifier_ciphertext" in column_names
    assert "masked_identifier" in column_names


def test_payment_destination_repository_satisfies_protocol() -> None:
    session = MagicMock(spec=AsyncSession)
    repository = SqlAlchemyPaymentDestinationRepository(session)

    assert isinstance(repository, PaymentDestinationRepository)


@pytest.mark.asyncio
async def test_payment_destination_repository_adds_model() -> None:
    session = MagicMock(spec=AsyncSession)
    repository = SqlAlchemyPaymentDestinationRepository(session)

    destination = AdminMarketPaymentDestination(
        id=uuid.uuid4(),
        destination_ref="main-bank",
        display_name="Main Bank",
        destination_type="bank_account",
        institution_name="Institution",
        account_holder_name="Processual Maestro",
        identifier_ciphertext=b"x" * 32,
        identifier_key_version="payment-v1",
        masked_identifier="****************8831",
        country_code="TN",
        currency="TND",
        sales_channel="maestro_direct",
        status="draft",
        is_active=False,
        is_default=False,
    )

    repository.add(destination)

    session.add.assert_called_once_with(destination)


@pytest.mark.asyncio
async def test_payment_destination_repository_lists_safe_models() -> None:
    session = MagicMock(spec=AsyncSession)
    scalars_result = MagicMock()
    scalars_result.all.return_value = []
    session.scalars = AsyncMock(return_value=scalars_result)
    repository = SqlAlchemyPaymentDestinationRepository(session)

    result = await repository.list_all()

    assert result == ()
    session.scalars.assert_awaited_once()


@pytest.mark.asyncio
async def test_unit_of_work_exposes_payment_destination_repository() -> None:
    session = MagicMock(spec=AsyncSession)
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.commit = AsyncMock()

    unit_of_work = SqlAlchemyAdminMarketplaceUnitOfWork(
        lambda: session,
    )

    async with unit_of_work as active:
        assert isinstance(
            active.payment_destinations,
            SqlAlchemyPaymentDestinationRepository,
        )
