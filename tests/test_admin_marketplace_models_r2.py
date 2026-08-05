from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    UniqueConstraint,
    create_engine,
    inspect,
)

from processual_api.admin_marketplace.models import (
    ADMIN_MARKET_MODELS,
    AdminMarketAuditRecord,
    AdminMarketChannelEligibility,
    AdminMarketContract,
    AdminMarketEntitlementActivation,
    AdminMarketInvoice,
    AdminMarketOffer,
    AdminMarketOrder,
    AdminMarketPaymentVerification,
    AdminMarketSubscription,
)
from processual_api.db.base import Base

EXPECTED_TABLES = {
    "admin_market_plans",
    "admin_market_offers",
    "admin_market_subscriptions",
    "admin_market_trials",
    "admin_market_orders",
    "admin_market_contracts",
    "admin_market_payment_verifications",
    "admin_market_invoices",
    "admin_market_entitlement_activations",
    "admin_market_channel_eligibilities",
    "admin_market_channel_selections",
    "admin_market_commercial_decisions",
    "admin_market_audit_records",
    "admin_market_payment_destinations",
}


def _column_names(model: type[Base]) -> set[str]:
    return {column.name for column in model.__table__.columns}


def _check_sql(model: type[Base]) -> set[str]:
    return {
        str(constraint.sqltext) for constraint in model.__table__.constraints if isinstance(constraint, CheckConstraint)
    }


def test_admin_market_metadata_catalog_is_exact() -> None:
    assert len(ADMIN_MARKET_MODELS) == 14

    assert {model.__tablename__ for model in ADMIN_MARKET_MODELS} == EXPECTED_TABLES

    assert EXPECTED_TABLES.issubset(Base.metadata.tables)


def test_offer_persistence_matches_r1_contract() -> None:
    assert _column_names(AdminMarketOffer) == {
        "id",
        "offer_code",
        "plan_id",
        "display_name",
        "sales_channel",
        "billing_period",
        "currency",
        "amount",
        "status",
        "effective_at",
        "expires_at",
        "customer_specific",
        "created_at",
        "updated_at",
    }

    check_sql = _check_sql(AdminMarketOffer)

    assert any("published" in expression for expression in check_sql)

    assert any("amount >= 0" in expression for expression in check_sql)

    assert any("expires_at > effective_at" in expression for expression in check_sql)


def test_subscription_and_order_status_are_constrained() -> None:
    subscription_checks = _check_sql(AdminMarketSubscription)

    order_checks = _check_sql(AdminMarketOrder)

    assert any(
        "active" in expression and "cancelled" in expression and "expired" in expression
        for expression in subscription_checks
    )

    assert any(
        "awaiting_contract" in expression and "activated" in expression
        for expression in order_checks
    )

    assert any("maestro_direct" in expression and "lemon_squeezy" in expression for expression in order_checks)


def test_commercial_amounts_are_fixed_precision() -> None:
    for model, expected_scale in (
        (AdminMarketOffer, 3),
        (AdminMarketInvoice, 2),
    ):
        amount = model.__table__.columns["amount"]

        assert amount.type.precision == 18
        assert amount.type.scale == expected_scale

        assert any("amount >= 0" in expression for expression in _check_sql(model))


def test_payment_verification_has_no_raw_evidence() -> None:
    columns = _column_names(AdminMarketPaymentVerification)

    forbidden = {
        "payment_evidence",
        "payment_evidence_raw",
        "card_number",
        "cvv",
        "secret",
        "token",
        "authorization",
        "webhook_signature",
    }

    assert columns.isdisjoint(forbidden)
    assert "safe_reference" in columns


def test_contract_completion_record_is_immutable_and_evidence_safe() -> None:
    columns = _column_names(AdminMarketContract)

    assert {
        "order_id",
        "contract_version",
        "accepted_party_ref",
        "acceptance_method",
        "evidence_reference",
        "completion_idempotency_key_hash",
        "completed_at",
    }.issubset(columns)
    assert "updated_at" not in columns
    assert columns.isdisjoint({"signature", "document", "raw_evidence", "ip_address"})


def test_channel_policy_is_preserved_in_database_constraints() -> None:
    check_sql = _check_sql(AdminMarketChannelEligibility)

    assert any(
        "maestro_direct_status" in expression
        and "lemon_squeezy_status" in expression
        and "customer_choice_allowed" in expression
        for expression in check_sql
    )

    assert any(
        "admin_review_required" in expression and "automatic_activation_allowed" in expression
        for expression in check_sql
    )

    assert any("restriction_reason" in expression and "ineligible" in expression for expression in check_sql)


def test_entitlement_activation_defaults_fail_closed() -> None:
    column = AdminMarketEntitlementActivation.__table__.columns["automatic_activation_allowed"]

    assert column.default is not None
    assert column.default.arg is False


def test_audit_table_is_append_only_and_authority_locked() -> None:
    columns = _column_names(AdminMarketAuditRecord)

    assert "created_at" in columns
    assert "updated_at" not in columns

    check_sql = _check_sql(AdminMarketAuditRecord)

    assert any("platform_admin" in expression for expression in check_sql)

    assert any(
        "authority_checked" in expression and "subscription_activation_decided" in expression
        for expression in check_sql
    )


def test_internal_foreign_key_delete_policies_are_explicit() -> None:
    expected = {
        (
            AdminMarketOffer,
            "plan_id",
        ): (
            "admin_market_plans.id",
            "RESTRICT",
        ),
        (
            AdminMarketSubscription,
            "offer_id",
        ): (
            "admin_market_offers.id",
            "RESTRICT",
        ),
        (
            AdminMarketSubscription,
            "plan_id",
        ): (
            "admin_market_plans.id",
            "RESTRICT",
        ),
        (
            AdminMarketOrder,
            "offer_id",
        ): (
            "admin_market_offers.id",
            "RESTRICT",
        ),
        (
            AdminMarketPaymentVerification,
            "order_id",
        ): (
            "admin_market_orders.id",
            "CASCADE",
        ),
        (
            AdminMarketInvoice,
            "order_id",
        ): (
            "admin_market_orders.id",
            "RESTRICT",
        ),
        (
            AdminMarketEntitlementActivation,
            "subscription_id",
        ): (
            "admin_market_subscriptions.id",
            "CASCADE",
        ),
    }

    for (
        model,
        column_name,
    ), expected_value in expected.items():
        foreign_key: ForeignKey = next(iter(model.__table__.columns[column_name].foreign_keys))

        assert (
            foreign_key.target_fullname,
            foreign_key.ondelete,
        ) == expected_value


def test_required_unique_constraints_and_indexes_exist() -> None:
    offer_unique = {
        tuple(column.name for column in constraint.columns)
        for constraint in AdminMarketOffer.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert ("offer_code",) in offer_unique

    audit_indexes = {index.name for index in AdminMarketAuditRecord.__table__.indexes if isinstance(index, Index)}

    assert audit_indexes == {
        "ix_admin_market_audit_correlation",
        "ix_admin_market_audit_resource_time",
    }


def test_metadata_can_create_and_drop_with_foreign_keys() -> None:
    engine = create_engine("sqlite:///:memory:")

    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(connection)

        assert EXPECTED_TABLES.issubset(inspect(connection).get_table_names())

        Base.metadata.drop_all(connection)

        assert EXPECTED_TABLES.isdisjoint(inspect(connection).get_table_names())


def test_postgresql_identifiers_compile_safely() -> None:
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.schema import CreateIndex, CreateTable

    dialect = postgresql.dialect()

    for model in ADMIN_MARKET_MODELS:
        table = model.__table__

        table_sql = str(CreateTable(table).compile(dialect=dialect))

        assert f"CREATE TABLE {table.name}" in table_sql

        for index in table.indexes:
            index_sql = str(CreateIndex(index).compile(dialect=dialect))

            assert index_sql.startswith(("CREATE INDEX", "CREATE UNIQUE INDEX"))
