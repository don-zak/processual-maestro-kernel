from __future__ import annotations

import inspect
import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

from processual_api.admin_marketplace.models import (
    AdminMarketEntitlementActivation,
    AdminMarketInvoice,
    AdminMarketPaymentEvidence,
    AdminMarketPaymentVerification,
)
from processual_api.admin_marketplace.persistence.protocols import (
    EntitlementActivationRepository,
    InvoiceRepository,
    PaymentEvidenceRepository,
    PaymentVerificationRepository,
)
from processual_api.admin_marketplace.persistence.repositories import (
    SqlAlchemyEntitlementActivationRepository,
    SqlAlchemyInvoiceRepository,
    SqlAlchemyPaymentEvidenceRepository,
    SqlAlchemyPaymentVerificationRepository,
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
        SqlAlchemyPaymentVerificationRepository,
        AdminMarketPaymentVerification,
        "admin_market_payment_verifications",
    ),
    (
        SqlAlchemyInvoiceRepository,
        AdminMarketInvoice,
        "admin_market_invoices",
    ),
    (
        SqlAlchemyEntitlementActivationRepository,
        AdminMarketEntitlementActivation,
        "admin_market_entitlement_activations",
    ),
)


def test_payment_evidence_repository_matches_protocol_and_has_no_transaction_api() -> None:
    repository = SqlAlchemyPaymentEvidenceRepository(MagicMock(spec=AsyncSession))

    assert isinstance(repository, PaymentEvidenceRepository)
    assert _public_methods(SqlAlchemyPaymentEvidenceRepository).isdisjoint(
        {"begin", "close", "commit", "create_session", "rollback"}
    )


@pytest.mark.asyncio
async def test_payment_evidence_repository_reads_by_safe_reference_with_lock() -> None:
    session = FakeAsyncSession()
    repository = SqlAlchemyPaymentEvidenceRepository(session)
    row = MagicMock(spec=AdminMarketPaymentEvidence)
    session.scalar_result = row

    result = await repository.get_by_ref("pev_001", for_update=True)

    assert result is row
    sql = _compile_postgresql(session.scalar_statements[0])
    assert "FROM admin_market_payment_evidence" in sql
    assert "FOR UPDATE" in sql


@pytest.mark.parametrize(
    ("repository_type", "model_type", "table_name"),
    REPOSITORIES,
)
@pytest.mark.asyncio
async def test_payment_repository_adds_and_reads_without_lock(
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
async def test_payment_repository_supports_row_locking(
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


@pytest.mark.parametrize(
    ("implementation", "protocol"),
    (
        (
            SqlAlchemyPaymentVerificationRepository,
            PaymentVerificationRepository,
        ),
        (
            SqlAlchemyInvoiceRepository,
            InvoiceRepository,
        ),
        (
            SqlAlchemyEntitlementActivationRepository,
            EntitlementActivationRepository,
        ),
    ),
)
def test_payment_repository_matches_protocol(
    implementation: type,
    protocol: type,
) -> None:
    repository = implementation(MagicMock(spec=AsyncSession))

    assert isinstance(repository, protocol)


@pytest.mark.parametrize(
    "repository_type",
    (
        SqlAlchemyPaymentVerificationRepository,
        SqlAlchemyInvoiceRepository,
        SqlAlchemyEntitlementActivationRepository,
    ),
)
def test_payment_repositories_do_not_own_transactions(
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
        SqlAlchemyPaymentVerificationRepository,
        SqlAlchemyInvoiceRepository,
        SqlAlchemyEntitlementActivationRepository,
    ),
)
def test_payment_repositories_have_no_provider_api(
    repository_type: type,
) -> None:
    methods = _public_methods(repository_type)

    assert methods.isdisjoint(
        {
            "call_provider",
            "create_checkout",
            "fetch_provider_payment",
            "lemon_squeezy",
            "process_webhook",
            "verify_provider_payment",
        }
    )


@pytest.mark.parametrize(
    "repository_type",
    (
        SqlAlchemyPaymentVerificationRepository,
        SqlAlchemyInvoiceRepository,
        SqlAlchemyEntitlementActivationRepository,
    ),
)
def test_payment_repositories_have_no_automatic_activation_api(
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


def test_entitlement_activation_repository_records_only() -> None:
    methods = _public_methods(SqlAlchemyEntitlementActivationRepository)

    assert methods == {"add", "get_by_id"}
