from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from processual_api.admin_marketplace.persistence.errors import (
    AdminMarketplaceConflictError,
)
from processual_api.admin_marketplace.persistence.protocols import (
    AdminMarketplaceUnitOfWork,
)
from processual_api.admin_marketplace.persistence.repositories import (
    SqlAlchemyChannelEligibilityRepository,
    SqlAlchemyChannelSelectionRepository,
    SqlAlchemyCommercialAuditRepository,
    SqlAlchemyCommercialDecisionRepository,
    SqlAlchemyContractRepository,
    SqlAlchemyEntitlementActivationRepository,
    SqlAlchemyInvoiceRepository,
    SqlAlchemyOfferRepository,
    SqlAlchemyOrderRepository,
    SqlAlchemyPaymentVerificationRepository,
    SqlAlchemyPlanRepository,
    SqlAlchemySubscriptionRepository,
    SqlAlchemyTrialRepository,
)
from processual_api.admin_marketplace.persistence.unit_of_work import (
    SqlAlchemyAdminMarketplaceUnitOfWork,
)


class FakeAsyncSession:
    def __init__(self) -> None:
        self.commit_calls = 0
        self.rollback_calls = 0
        self.close_calls = 0
        self.commit_error: Exception | None = None

    async def commit(self) -> None:
        self.commit_calls += 1

        if self.commit_error is not None:
            raise self.commit_error

    async def rollback(self) -> None:
        self.rollback_calls += 1

    async def close(self) -> None:
        self.close_calls += 1


def _session_from(repository: object) -> object:
    return repository._session  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_unit_of_work_constructs_all_repositories() -> None:
    session = FakeAsyncSession()
    unit_of_work = SqlAlchemyAdminMarketplaceUnitOfWork(
        lambda: session,  # type: ignore[arg-type]
    )

    async with unit_of_work:
        assert isinstance(
            unit_of_work.plans,
            SqlAlchemyPlanRepository,
        )
        assert isinstance(
            unit_of_work.offers,
            SqlAlchemyOfferRepository,
        )
        assert isinstance(
            unit_of_work.subscriptions,
            SqlAlchemySubscriptionRepository,
        )
        assert isinstance(
            unit_of_work.trials,
            SqlAlchemyTrialRepository,
        )
        assert isinstance(
            unit_of_work.orders,
            SqlAlchemyOrderRepository,
        )
        assert isinstance(
            unit_of_work.contracts,
            SqlAlchemyContractRepository,
        )
        assert isinstance(
            unit_of_work.payment_verifications,
            SqlAlchemyPaymentVerificationRepository,
        )
        assert isinstance(
            unit_of_work.invoices,
            SqlAlchemyInvoiceRepository,
        )
        assert isinstance(
            unit_of_work.entitlement_activations,
            SqlAlchemyEntitlementActivationRepository,
        )
        assert isinstance(
            unit_of_work.channel_eligibilities,
            SqlAlchemyChannelEligibilityRepository,
        )
        assert isinstance(
            unit_of_work.channel_selections,
            SqlAlchemyChannelSelectionRepository,
        )
        assert isinstance(
            unit_of_work.commercial_decisions,
            SqlAlchemyCommercialDecisionRepository,
        )
        assert isinstance(
            unit_of_work.commercial_audit,
            SqlAlchemyCommercialAuditRepository,
        )


@pytest.mark.asyncio
async def test_all_repositories_share_one_session() -> None:
    session = FakeAsyncSession()
    unit_of_work = SqlAlchemyAdminMarketplaceUnitOfWork(
        lambda: session,  # type: ignore[arg-type]
    )

    async with unit_of_work:
        repositories = (
            unit_of_work.plans,
            unit_of_work.offers,
            unit_of_work.subscriptions,
            unit_of_work.trials,
            unit_of_work.orders,
            unit_of_work.contracts,
            unit_of_work.payment_verifications,
            unit_of_work.invoices,
            unit_of_work.entitlement_activations,
            unit_of_work.channel_eligibilities,
            unit_of_work.channel_selections,
            unit_of_work.commercial_decisions,
            unit_of_work.commercial_audit,
        )

        assert {id(_session_from(repository)) for repository in repositories} == {id(session)}


@pytest.mark.asyncio
async def test_commit_commits_and_prevents_exit_rollback() -> None:
    session = FakeAsyncSession()
    unit_of_work = SqlAlchemyAdminMarketplaceUnitOfWork(
        lambda: session,  # type: ignore[arg-type]
    )

    async with unit_of_work:
        await unit_of_work.commit()

    assert session.commit_calls == 1
    assert session.rollback_calls == 0
    assert session.close_calls == 1


@pytest.mark.asyncio
async def test_exit_without_commit_rolls_back() -> None:
    session = FakeAsyncSession()
    unit_of_work = SqlAlchemyAdminMarketplaceUnitOfWork(
        lambda: session,  # type: ignore[arg-type]
    )

    async with unit_of_work:
        pass

    assert session.commit_calls == 0
    assert session.rollback_calls == 1
    assert session.close_calls == 1


@pytest.mark.asyncio
async def test_exception_rolls_back_and_closes() -> None:
    session = FakeAsyncSession()
    unit_of_work = SqlAlchemyAdminMarketplaceUnitOfWork(
        lambda: session,  # type: ignore[arg-type]
    )

    with pytest.raises(ValueError, match="failure"):
        async with unit_of_work:
            raise ValueError("failure")

    assert session.rollback_calls == 1
    assert session.close_calls == 1


@pytest.mark.asyncio
async def test_explicit_rollback_keeps_exit_safe() -> None:
    session = FakeAsyncSession()
    unit_of_work = SqlAlchemyAdminMarketplaceUnitOfWork(
        lambda: session,  # type: ignore[arg-type]
    )

    async with unit_of_work:
        await unit_of_work.rollback()

    assert session.rollback_calls == 2
    assert session.close_calls == 1


@pytest.mark.asyncio
async def test_integrity_error_is_translated() -> None:
    session = FakeAsyncSession()
    session.commit_error = IntegrityError(
        statement="INSERT",
        params={},
        orig=Exception("duplicate"),
    )

    unit_of_work = SqlAlchemyAdminMarketplaceUnitOfWork(
        lambda: session,  # type: ignore[arg-type]
    )

    with pytest.raises(
        AdminMarketplaceConflictError,
        match="Admin Marketplace integrity conflict",
    ):
        async with unit_of_work:
            await unit_of_work.commit()

    assert session.commit_calls == 1
    assert session.rollback_calls == 2
    assert session.close_calls == 1


@pytest.mark.asyncio
async def test_commit_requires_active_unit_of_work() -> None:
    unit_of_work = SqlAlchemyAdminMarketplaceUnitOfWork(
        MagicMock(spec=AsyncSession),
    )

    with pytest.raises(
        RuntimeError,
        match="not active",
    ):
        await unit_of_work.commit()


@pytest.mark.asyncio
async def test_rollback_requires_active_unit_of_work() -> None:
    unit_of_work = SqlAlchemyAdminMarketplaceUnitOfWork(
        MagicMock(spec=AsyncSession),
    )

    with pytest.raises(
        RuntimeError,
        match="not active",
    ):
        await unit_of_work.rollback()


@pytest.mark.asyncio
async def test_unit_of_work_rejects_nested_entry() -> None:
    session = FakeAsyncSession()
    unit_of_work = SqlAlchemyAdminMarketplaceUnitOfWork(
        lambda: session,  # type: ignore[arg-type]
    )

    async with unit_of_work:
        with pytest.raises(
            RuntimeError,
            match="already active",
        ):
            await unit_of_work.__aenter__()


@pytest.mark.asyncio
async def test_unit_of_work_can_be_reused_after_exit() -> None:
    first_session = FakeAsyncSession()
    second_session = FakeAsyncSession()
    sessions = iter((first_session, second_session))

    unit_of_work = SqlAlchemyAdminMarketplaceUnitOfWork(
        lambda: next(sessions),  # type: ignore[arg-type]
    )

    async with unit_of_work:
        first_repository_session = _session_from(unit_of_work.plans)

    async with unit_of_work:
        second_repository_session = _session_from(unit_of_work.plans)

    assert first_repository_session is first_session
    assert second_repository_session is second_session
    assert first_session.close_calls == 1
    assert second_session.close_calls == 1


@pytest.mark.asyncio
async def test_active_unit_of_work_matches_protocol() -> None:
    session = FakeAsyncSession()
    unit_of_work = SqlAlchemyAdminMarketplaceUnitOfWork(
        lambda: session,  # type: ignore[arg-type]
    )

    async with unit_of_work:
        assert isinstance(
            unit_of_work,
            AdminMarketplaceUnitOfWork,
        )


class FakeDiagnostic:
    def __init__(
        self,
        constraint_name: str | None = None,
    ) -> None:
        self.constraint_name = constraint_name


class FakePostgresError(Exception):
    def __init__(
        self,
        *,
        sqlstate: str,
        constraint_name: str | None = None,
    ) -> None:
        super().__init__("database failure")
        self.sqlstate = sqlstate
        self.diag = FakeDiagnostic(constraint_name)


@pytest.mark.asyncio
async def test_unit_of_work_maps_unique_violation() -> None:
    from processual_api.admin_marketplace.persistence.errors import (
        AdminMarketplaceDuplicateReferenceError,
    )

    session = FakeAsyncSession()
    session.commit_error = IntegrityError(
        statement="INSERT",
        params={},
        orig=FakePostgresError(
            sqlstate="23505",
            constraint_name=("uq_admin_market_orders_order_ref"),
        ),
    )

    unit_of_work = SqlAlchemyAdminMarketplaceUnitOfWork(
        lambda: session,  # type: ignore[arg-type]
    )

    with pytest.raises(
        AdminMarketplaceDuplicateReferenceError,
    ):
        async with unit_of_work:
            await unit_of_work.commit()

    assert session.rollback_calls == 2
    assert session.close_calls == 1


@pytest.mark.asyncio
async def test_unit_of_work_maps_serialization_failure() -> None:
    from sqlalchemy.exc import DBAPIError

    from processual_api.admin_marketplace.persistence.errors import (
        AdminMarketplaceConcurrencyError,
    )

    session = FakeAsyncSession()
    session.commit_error = DBAPIError(
        statement="UPDATE",
        params={},
        orig=FakePostgresError(sqlstate="40001"),
        connection_invalidated=False,
    )

    unit_of_work = SqlAlchemyAdminMarketplaceUnitOfWork(
        lambda: session,  # type: ignore[arg-type]
    )

    with pytest.raises(
        AdminMarketplaceConcurrencyError,
    ):
        async with unit_of_work:
            await unit_of_work.commit()

    assert session.rollback_calls == 2
    assert session.close_calls == 1
