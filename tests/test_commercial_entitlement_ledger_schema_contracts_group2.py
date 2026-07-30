import pytest

from processual_api.billing.commercial_entitlement_ledger_schema_contracts import (
    BALANCES_TABLE,
    ENTITLEMENT_LEDGER_DATABASE_CREATION_ENABLED,
    ENTITLEMENT_LEDGER_MIGRATION_ENABLED,
    ENTITLEMENT_LEDGER_MODELS_ENABLED,
    ENTITLEMENT_LEDGER_RUNTIME_PERSISTENCE_ENABLED,
    LEDGER_ENTRIES_TABLE,
    RESERVATION_LOCKS_TABLE,
    ColumnContract,
    ColumnNullability,
    ConstraintContract,
    ConstraintKind,
    IndexContract,
    SchemaContractError,
    TableContract,
    build_balances_table_contract,
    build_entitlement_schema_contracts,
    build_ledger_entries_table_contract,
    build_reservation_locks_table_contract,
    entitlement_schema_review_payload,
)


def column_names(
    table: TableContract,
) -> set[str]:
    return {
        column.name
        for column in table.columns
    }


def constraint_names(
    table: TableContract,
) -> set[str]:
    return {
        constraint.name
        for constraint in table.constraints
    }


def index_names(
    table: TableContract,
) -> set[str]:
    return {
        index.name
        for index in table.indexes
    }


def test_schema_creation_remains_disabled() -> None:
    payload = entitlement_schema_review_payload()

    assert ENTITLEMENT_LEDGER_MODELS_ENABLED is False
    assert ENTITLEMENT_LEDGER_MIGRATION_ENABLED is False
    assert ENTITLEMENT_LEDGER_DATABASE_CREATION_ENABLED is False
    assert ENTITLEMENT_LEDGER_RUNTIME_PERSISTENCE_ENABLED is False

    assert payload["status"] == "draft_review"
    assert payload["models_enabled"] is False
    assert payload["migration_enabled"] is False
    assert payload["database_creation_enabled"] is False
    assert payload["runtime_persistence_enabled"] is False


def test_schema_contains_three_canonical_tables() -> None:
    tables = build_entitlement_schema_contracts()

    assert tuple(
        table.name
        for table in tables
    ) == (
        LEDGER_ENTRIES_TABLE,
        BALANCES_TABLE,
        RESERVATION_LOCKS_TABLE,
    )


def test_all_constraint_and_index_names_are_globally_unique() -> None:
    tables = build_entitlement_schema_contracts()

    all_constraint_names = [
        constraint.name
        for table in tables
        for constraint in table.constraints
    ]
    all_index_names = [
        index.name
        for table in tables
        for index in table.indexes
    ]

    assert len(all_constraint_names) == len(
        set(all_constraint_names)
    )
    assert len(all_index_names) == len(
        set(all_index_names)
    )


def test_ledger_entry_table_has_required_identity_columns() -> None:
    table = build_ledger_entries_table_contract()

    assert {
        "entry_id",
        "tenant_id",
        "subscription_id",
        "entry_type",
        "units",
        "idempotency_key",
        "source_reference",
        "occurred_at",
    }.issubset(column_names(table))


def test_ledger_idempotency_is_scoped_by_tenant_and_subscription() -> None:
    table = build_ledger_entries_table_contract()

    unique_constraints = [
        constraint
        for constraint in table.constraints
        if constraint.kind is ConstraintKind.UNIQUE
    ]

    assert any(
        constraint.columns
        == (
            "tenant_id",
            "subscription_id",
            "idempotency_key",
        )
        for constraint in unique_constraints
    )


def test_ledger_units_must_be_positive() -> None:
    table = build_ledger_entries_table_contract()

    assert any(
        constraint.expression == "units > 0"
        for constraint in table.constraints
        if constraint.kind is ConstraintKind.CHECK
    )


def test_related_entry_foreign_key_is_explicitly_named() -> None:
    table = build_ledger_entries_table_contract()

    foreign_keys = [
        constraint
        for constraint in table.constraints
        if constraint.kind is ConstraintKind.FOREIGN_KEY
    ]

    assert len(foreign_keys) == 1
    assert foreign_keys[0].columns == ("related_entry_id",)
    assert foreign_keys[0].references == (
        "commercial_entitlement_ledger_entries.entry_id"
    )


def test_reservation_index_is_partial() -> None:
    table = build_ledger_entries_table_contract()

    reservation_indexes = [
        index
        for index in table.indexes
        if "reservation" in index.name
    ]

    assert len(reservation_indexes) == 1
    assert reservation_indexes[0].predicate == (
        "reservation_id IS NOT NULL"
    )


def test_balance_table_uses_composite_scope_primary_key() -> None:
    table = build_balances_table_contract()

    primary_keys = [
        constraint
        for constraint in table.constraints
        if constraint.kind is ConstraintKind.PRIMARY_KEY
    ]

    assert len(primary_keys) == 1
    assert primary_keys[0].columns == (
        "tenant_id",
        "subscription_id",
    )


def test_balance_values_and_version_are_nonnegative() -> None:
    table = build_balances_table_contract()

    expressions = {
        constraint.expression
        for constraint in table.constraints
        if constraint.kind is ConstraintKind.CHECK
    }

    assert {
        "available_units >= 0",
        "reserved_units >= 0",
        "committed_units >= 0",
        "version >= 0",
    }.issubset(expressions)


def test_balance_version_defaults_to_zero() -> None:
    table = build_balances_table_contract()

    version = next(
        column
        for column in table.columns
        if column.name == "version"
    )

    assert version.server_default == "0"
    assert version.nullability is ColumnNullability.REQUIRED


def test_reservation_lock_uses_composite_scope_primary_key() -> None:
    table = build_reservation_locks_table_contract()

    primary_key = next(
        constraint
        for constraint in table.constraints
        if constraint.kind is ConstraintKind.PRIMARY_KEY
    )

    assert primary_key.columns == (
        "tenant_id",
        "subscription_id",
        "reservation_id",
    )


def test_reservation_lock_owner_must_be_nonblank() -> None:
    table = build_reservation_locks_table_contract()

    assert any(
        constraint.expression
        == "length(trim(owner_token)) > 0"
        for constraint in table.constraints
        if constraint.kind is ConstraintKind.CHECK
    )


def test_timestamps_are_timezone_aware() -> None:
    tables = build_entitlement_schema_contracts()

    timestamp_columns = [
        column
        for table in tables
        for column in table.columns
        if column.name.endswith("_at")
    ]

    assert timestamp_columns
    assert all(
        column.sql_type == "TIMESTAMP WITH TIME ZONE"
        for column in timestamp_columns
    )


def test_table_contract_rejects_duplicate_columns() -> None:
    duplicate = ColumnContract(
        name="entry_id",
        sql_type="UUID",
        nullability=ColumnNullability.REQUIRED,
    )

    with pytest.raises(
        SchemaContractError,
        match="duplicate column names",
    ):
        TableContract(
            name="invalid_table",
            columns=(duplicate, duplicate),
            constraints=(),
            indexes=(),
        )


def test_table_contract_rejects_unknown_constraint_column() -> None:
    with pytest.raises(
        SchemaContractError,
        match="constraint references an unknown column",
    ):
        TableContract(
            name="invalid_table",
            columns=(
                ColumnContract(
                    name="entry_id",
                    sql_type="UUID",
                    nullability=ColumnNullability.REQUIRED,
                ),
            ),
            constraints=(
                ConstraintContract(
                    name="pk_invalid_table",
                    kind=ConstraintKind.PRIMARY_KEY,
                    columns=("missing_column",),
                ),
            ),
            indexes=(),
        )


def test_table_contract_rejects_unknown_index_column() -> None:
    with pytest.raises(
        SchemaContractError,
        match="index references an unknown column",
    ):
        TableContract(
            name="invalid_table",
            columns=(
                ColumnContract(
                    name="entry_id",
                    sql_type="UUID",
                    nullability=ColumnNullability.REQUIRED,
                ),
            ),
            constraints=(),
            indexes=(
                IndexContract(
                    name="ix_invalid_table_missing",
                    columns=("missing_column",),
                ),
            ),
        )


def test_check_constraint_requires_expression() -> None:
    with pytest.raises(
        SchemaContractError,
        match="requires an expression",
    ):
        ConstraintContract(
            name="ck_invalid",
            kind=ConstraintKind.CHECK,
            columns=("units",),
        )


def test_foreign_key_requires_reference() -> None:
    with pytest.raises(
        SchemaContractError,
        match="requires references",
    ):
        ConstraintContract(
            name="fk_invalid",
            kind=ConstraintKind.FOREIGN_KEY,
            columns=("related_entry_id",),
        )


def test_all_schema_names_fit_postgresql_identifier_limit() -> None:
    tables = build_entitlement_schema_contracts()

    names = [
        table.name
        for table in tables
    ]
    names.extend(
        constraint.name
        for table in tables
        for constraint in table.constraints
    )
    names.extend(
        index.name
        for table in tables
        for index in table.indexes
    )

    assert all(
        len(name) <= 63
        for name in names
    ), [
        name
        for name in names
        if len(name) > 63
    ]


def test_contract_name_helpers_return_expected_names() -> None:
    ledger = build_ledger_entries_table_contract()
    balances = build_balances_table_contract()
    locks = build_reservation_locks_table_contract()

    assert ledger.name == LEDGER_ENTRIES_TABLE
    assert balances.name == BALANCES_TABLE
    assert locks.name == RESERVATION_LOCKS_TABLE

    assert constraint_names(ledger)
    assert constraint_names(balances)
    assert constraint_names(locks)
    assert index_names(ledger)
