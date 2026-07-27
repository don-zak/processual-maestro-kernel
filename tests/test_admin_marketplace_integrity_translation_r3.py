from __future__ import annotations

from dataclasses import dataclass

import pytest
from sqlalchemy.exc import DBAPIError, IntegrityError

from processual_api.admin_marketplace.persistence.errors import (
    AdminMarketplaceConcurrencyError,
    AdminMarketplaceConflictError,
    AdminMarketplaceDuplicateReferenceError,
)
from processual_api.admin_marketplace.persistence.integrity import (
    extract_constraint_name,
    extract_sqlstate,
    translate_database_error,
)


@dataclass
class FakeDiagnostic:
    constraint_name: str | None = None


class FakeDatabaseError(Exception):
    def __init__(
        self,
        *,
        sqlstate: str | None = None,
        pgcode: str | None = None,
        constraint_name: str | None = None,
    ) -> None:
        super().__init__("database failure")
        self.sqlstate = sqlstate
        self.pgcode = pgcode
        self.diag = FakeDiagnostic(
            constraint_name=constraint_name,
        )


def _integrity_error(
    *,
    sqlstate: str | None = None,
    pgcode: str | None = None,
    constraint_name: str | None = None,
) -> IntegrityError:
    return IntegrityError(
        statement="INSERT",
        params={},
        orig=FakeDatabaseError(
            sqlstate=sqlstate,
            pgcode=pgcode,
            constraint_name=constraint_name,
        ),
    )


def _dbapi_error(*, sqlstate: str) -> DBAPIError:
    return DBAPIError(
        statement="UPDATE",
        params={},
        orig=FakeDatabaseError(sqlstate=sqlstate),
        connection_invalidated=False,
    )


def test_extracts_sqlstate_attribute() -> None:
    error = _integrity_error(sqlstate="23505")

    assert extract_sqlstate(error) == "23505"


def test_falls_back_to_pgcode() -> None:
    error = _integrity_error(pgcode="23505")

    assert extract_sqlstate(error) == "23505"


def test_extracts_constraint_name() -> None:
    error = _integrity_error(
        sqlstate="23505",
        constraint_name="uq_admin_market_orders_order_ref",
    )

    assert extract_constraint_name(error) == ("uq_admin_market_orders_order_ref")


@pytest.mark.parametrize(
    "constraint_name",
    (
        "uq_admin_market_plans_plan_code",
        "uq_admin_market_offers_offer_code",
        "uq_admin_market_subscriptions_subscription_ref",
        "uq_admin_market_trials_trial_ref",
        "uq_admin_market_orders_order_ref",
        ("uq_admin_market_payment_verifications_verification_ref"),
        "uq_admin_market_invoices_invoice_ref",
        ("uq_admin_market_entitlement_activations_activation_ref"),
        ("uq_admin_market_channel_eligibilities_customer_ref"),
        ("uq_admin_market_commercial_decisions_decision_ref"),
        "uq_admin_market_audit_records_event_ref",
    ),
)
def test_unique_violation_maps_to_duplicate_reference(
    constraint_name: str,
) -> None:
    translated = translate_database_error(
        _integrity_error(
            sqlstate="23505",
            constraint_name=constraint_name,
        )
    )

    assert isinstance(
        translated,
        AdminMarketplaceDuplicateReferenceError,
    )
    assert constraint_name in str(translated)


@pytest.mark.parametrize(
    "sqlstate",
    (
        "40001",
        "40P01",
    ),
)
def test_concurrent_failure_maps_to_concurrency(
    sqlstate: str,
) -> None:
    translated = translate_database_error(_dbapi_error(sqlstate=sqlstate))

    assert isinstance(
        translated,
        AdminMarketplaceConcurrencyError,
    )


@pytest.mark.parametrize(
    "sqlstate",
    (
        "23502",
        "23503",
        "23514",
    ),
)
def test_other_integrity_failures_map_to_conflict(
    sqlstate: str,
) -> None:
    translated = translate_database_error(
        _integrity_error(
            sqlstate=sqlstate,
            constraint_name="ck_admin_market_example",
        )
    )

    assert type(translated) is AdminMarketplaceConflictError


def test_unknown_integrity_error_maps_to_conflict() -> None:
    translated = translate_database_error(
        IntegrityError(
            statement="INSERT",
            params={},
            orig=Exception("unknown integrity failure"),
        )
    )

    assert type(translated) is AdminMarketplaceConflictError


def test_unknown_dbapi_error_maps_to_conflict() -> None:
    translated = translate_database_error(_dbapi_error(sqlstate="08006"))

    assert type(translated) is AdminMarketplaceConflictError
