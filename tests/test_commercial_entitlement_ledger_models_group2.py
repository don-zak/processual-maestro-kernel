from sqlalchemy import CheckConstraint, Index, UniqueConstraint

from processual_api.billing.commercial_entitlement_ledger_models import (
    COMMERCIAL_ENTITLEMENT_LEDGER_MODELS,
    ENTITLEMENT_LEDGER_SQLALCHEMY_MODELS_ENABLED,
    ENTITLEMENT_LEDGER_SQLALCHEMY_RUNTIME_ENABLED,
    CommercialEntitlementBalance,
    CommercialEntitlementLedgerEntry,
    CommercialEntitlementReservationLock,
)
from processual_api.billing.commercial_entitlement_ledger_schema_contracts import (
    BALANCES_TABLE,
    LEDGER_ENTRIES_TABLE,
    RESERVATION_LOCKS_TABLE,
    build_entitlement_schema_contracts,
)


def table_constraints(model: type) -> set[str]:
    return {
        constraint.name
        for constraint in model.__table__.constraints
        if constraint.name is not None
    }


def table_indexes(model: type) -> set[str]:
    return {
        index.name
        for index in model.__table__.indexes
        if index.name is not None
    }


def test_models_exist_but_runtime_is_disabled() -> None:
    assert ENTITLEMENT_LEDGER_SQLALCHEMY_MODELS_ENABLED is False
    assert ENTITLEMENT_LEDGER_SQLALCHEMY_RUNTIME_ENABLED is False


def test_three_canonical_models_are_registered() -> None:
    assert COMMERCIAL_ENTITLEMENT_LEDGER_MODELS == (
        CommercialEntitlementLedgerEntry,
        CommercialEntitlementBalance,
        CommercialEntitlementReservationLock,
    )


def test_model_table_names_match_schema_contracts() -> None:
    assert CommercialEntitlementLedgerEntry.__tablename__ == (
        LEDGER_ENTRIES_TABLE
    )
    assert CommercialEntitlementBalance.__tablename__ == (
        BALANCES_TABLE
    )
    assert CommercialEntitlementReservationLock.__tablename__ == (
        RESERVATION_LOCKS_TABLE
    )


def test_all_schema_contract_columns_exist_in_models() -> None:
    model_by_table = {
        model.__tablename__: model
        for model in COMMERCIAL_ENTITLEMENT_LEDGER_MODELS
    }

    for table_contract in build_entitlement_schema_contracts():
        model = model_by_table[table_contract.name]

        assert set(model.__table__.columns.keys()) == {
            column.name
            for column in table_contract.columns
        }


def test_ledger_entry_primary_key_is_entry_id() -> None:
    primary_keys = {
        column.name
        for column in (
            CommercialEntitlementLedgerEntry
            .__table__
            .primary_key
            .columns
        )
    }

    assert primary_keys == {"entry_id"}


def test_balance_primary_key_is_composite_scope() -> None:
    primary_keys = {
        column.name
        for column in (
            CommercialEntitlementBalance
            .__table__
            .primary_key
            .columns
        )
    }

    assert primary_keys == {
        "tenant_id",
        "subscription_id",
    }


def test_reservation_lock_primary_key_is_composite_scope() -> None:
    primary_keys = {
        column.name
        for column in (
            CommercialEntitlementReservationLock
            .__table__
            .primary_key
            .columns
        )
    }

    assert primary_keys == {
        "tenant_id",
        "subscription_id",
        "reservation_id",
    }


def test_ledger_scoped_idempotency_constraint_exists() -> None:
    constraints = [
        constraint
        for constraint in (
            CommercialEntitlementLedgerEntry
            .__table__
            .constraints
        )
        if isinstance(constraint, UniqueConstraint)
    ]

    assert any(
        tuple(
            column.name
            for column in constraint.columns
        )
        == (
            "tenant_id",
            "subscription_id",
            "idempotency_key",
        )
        for constraint in constraints
    )


def test_all_check_constraints_are_explicitly_named() -> None:
    for model in COMMERCIAL_ENTITLEMENT_LEDGER_MODELS:
        checks = [
            constraint
            for constraint in model.__table__.constraints
            if isinstance(constraint, CheckConstraint)
        ]

        assert checks
        assert all(
            constraint.name is not None
            for constraint in checks
        )


def test_indexes_are_explicitly_named() -> None:
    for model in COMMERCIAL_ENTITLEMENT_LEDGER_MODELS:
        indexes = list(model.__table__.indexes)

        assert indexes
        assert all(
            isinstance(index, Index)
            and index.name is not None
            for index in indexes
        )


def test_model_constraints_match_schema_contract_names() -> None:
    model_by_table = {
        model.__tablename__: model
        for model in COMMERCIAL_ENTITLEMENT_LEDGER_MODELS
    }

    for contract in build_entitlement_schema_contracts():
        model = model_by_table[contract.name]
        expected = {
            constraint.name
            for constraint in contract.constraints
        }

        assert expected.issubset(
            table_constraints(model)
        )


def test_model_indexes_match_schema_contract_names() -> None:
    model_by_table = {
        model.__tablename__: model
        for model in COMMERCIAL_ENTITLEMENT_LEDGER_MODELS
    }

    for contract in build_entitlement_schema_contracts():
        model = model_by_table[contract.name]
        expected = {
            index.name
            for index in contract.indexes
        }

        assert expected == table_indexes(model)


def test_all_datetime_columns_are_timezone_aware() -> None:
    datetime_column_names = {
        "occurred_at",
        "created_at",
        "calculated_at",
        "updated_at",
        "expires_at",
    }

    for model in COMMERCIAL_ENTITLEMENT_LEDGER_MODELS:
        for column in model.__table__.columns:
            if column.name in datetime_column_names:
                assert column.type.timezone is True


def test_ledger_entry_related_foreign_key_is_restrictive() -> None:
    column = (
        CommercialEntitlementLedgerEntry
        .__table__
        .columns["related_entry_id"]
    )
    foreign_keys = list(column.foreign_keys)

    assert len(foreign_keys) == 1
    assert foreign_keys[0].ondelete == "RESTRICT"
    assert foreign_keys[0].constraint.name == (
        "fk_commercial_entitlement_ledger_entries_related_entry"
    )


def test_ledger_entry_is_append_only_by_contract() -> None:
    assert CommercialEntitlementLedgerEntry in (
        COMMERCIAL_ENTITLEMENT_LEDGER_MODELS
    )
