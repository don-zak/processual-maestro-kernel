"""Review-only relational schema contracts for the entitlement ledger.

These contracts define proposed table, column, constraint, and index names.
They do not declare SQLAlchemy models, create database objects, or enable
persistence.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Final

ENTITLEMENT_LEDGER_SCHEMA_VERSION: Final = (
    "2026-07-group2-entitlement-ledger-schema-v1"
)
ENTITLEMENT_LEDGER_SCHEMA_STATUS: Final = "draft_review"

ENTITLEMENT_LEDGER_MODELS_ENABLED: Final = False
ENTITLEMENT_LEDGER_MIGRATION_ENABLED: Final = False
ENTITLEMENT_LEDGER_DATABASE_CREATION_ENABLED: Final = False
ENTITLEMENT_LEDGER_RUNTIME_PERSISTENCE_ENABLED: Final = False

LEDGER_ENTRIES_TABLE: Final = "commercial_entitlement_ledger_entries"
BALANCES_TABLE: Final = "commercial_entitlement_balances"
RESERVATION_LOCKS_TABLE: Final = (
    "commercial_entitlement_reservation_locks"
)


class SchemaContractError(ValueError):
    """Raised when a relational schema contract is invalid."""


class ColumnNullability(StrEnum):
    REQUIRED = "required"
    NULLABLE = "nullable"


class ConstraintKind(StrEnum):
    PRIMARY_KEY = "primary_key"
    UNIQUE = "unique"
    CHECK = "check"
    FOREIGN_KEY = "foreign_key"


@dataclass(frozen=True, slots=True)
class ColumnContract:
    name: str
    sql_type: str
    nullability: ColumnNullability
    server_default: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise SchemaContractError(
                "column name must not be blank"
            )

        if not self.sql_type.strip():
            raise SchemaContractError(
                "column sql_type must not be blank"
            )


@dataclass(frozen=True, slots=True)
class ConstraintContract:
    name: str
    kind: ConstraintKind
    columns: tuple[str, ...]
    expression: str | None = None
    references: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise SchemaContractError(
                "constraint name must not be blank"
            )

        if not self.columns:
            raise SchemaContractError(
                "constraint requires at least one column"
            )

        if self.kind is ConstraintKind.CHECK:
            if not self.expression or not self.expression.strip():
                raise SchemaContractError(
                    "check constraint requires an expression"
                )
        elif self.expression is not None:
            raise SchemaContractError(
                "expression is valid only for check constraints"
            )

        if self.kind is ConstraintKind.FOREIGN_KEY:
            if not self.references or not self.references.strip():
                raise SchemaContractError(
                    "foreign key requires references"
                )
        elif self.references is not None:
            raise SchemaContractError(
                "references is valid only for foreign keys"
            )


@dataclass(frozen=True, slots=True)
class IndexContract:
    name: str
    columns: tuple[str, ...]
    unique: bool = False
    predicate: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise SchemaContractError(
                "index name must not be blank"
            )

        if not self.columns:
            raise SchemaContractError(
                "index requires at least one column"
            )


@dataclass(frozen=True, slots=True)
class TableContract:
    name: str
    columns: tuple[ColumnContract, ...]
    constraints: tuple[ConstraintContract, ...]
    indexes: tuple[IndexContract, ...]

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise SchemaContractError(
                "table name must not be blank"
            )

        column_names = [
            column.name
            for column in self.columns
        ]

        if len(column_names) != len(set(column_names)):
            raise SchemaContractError(
                "table contains duplicate column names"
            )

        constraint_names = [
            constraint.name
            for constraint in self.constraints
        ]

        if len(constraint_names) != len(
            set(constraint_names)
        ):
            raise SchemaContractError(
                "table contains duplicate constraint names"
            )

        index_names = [
            index.name
            for index in self.indexes
        ]

        if len(index_names) != len(set(index_names)):
            raise SchemaContractError(
                "table contains duplicate index names"
            )

        available_columns = set(column_names)

        for constraint in self.constraints:
            if not set(constraint.columns).issubset(
                available_columns
            ):
                raise SchemaContractError(
                    "constraint references an unknown column"
                )

        for index in self.indexes:
            if not set(index.columns).issubset(
                available_columns
            ):
                raise SchemaContractError(
                    "index references an unknown column"
                )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def build_ledger_entries_table_contract() -> TableContract:
    return TableContract(
        name=LEDGER_ENTRIES_TABLE,
        columns=(
            ColumnContract(
                "entry_id",
                "UUID",
                ColumnNullability.REQUIRED,
            ),
            ColumnContract(
                "tenant_id",
                "UUID",
                ColumnNullability.REQUIRED,
            ),
            ColumnContract(
                "subscription_id",
                "UUID",
                ColumnNullability.REQUIRED,
            ),
            ColumnContract(
                "entry_type",
                "VARCHAR(64)",
                ColumnNullability.REQUIRED,
            ),
            ColumnContract(
                "units",
                "BIGINT",
                ColumnNullability.REQUIRED,
            ),
            ColumnContract(
                "idempotency_key",
                "VARCHAR(255)",
                ColumnNullability.REQUIRED,
            ),
            ColumnContract(
                "source_reference",
                "VARCHAR(512)",
                ColumnNullability.REQUIRED,
            ),
            ColumnContract(
                "reservation_id",
                "UUID",
                ColumnNullability.NULLABLE,
            ),
            ColumnContract(
                "related_entry_id",
                "UUID",
                ColumnNullability.NULLABLE,
            ),
            ColumnContract(
                "adjustment_units",
                "BIGINT",
                ColumnNullability.NULLABLE,
            ),
            ColumnContract(
                "reason",
                "TEXT",
                ColumnNullability.NULLABLE,
            ),
            ColumnContract(
                "occurred_at",
                "TIMESTAMP WITH TIME ZONE",
                ColumnNullability.REQUIRED,
            ),
            ColumnContract(
                "created_at",
                "TIMESTAMP WITH TIME ZONE",
                ColumnNullability.REQUIRED,
                server_default="CURRENT_TIMESTAMP",
            ),
        ),
        constraints=(
            ConstraintContract(
                name="pk_commercial_entitlement_ledger_entries",
                kind=ConstraintKind.PRIMARY_KEY,
                columns=("entry_id",),
            ),
            ConstraintContract(
                name=(
                    "uq_commercial_entitlement_ledger_entries_"
                    "scope_idempotency"
                ),
                kind=ConstraintKind.UNIQUE,
                columns=(
                    "tenant_id",
                    "subscription_id",
                    "idempotency_key",
                ),
            ),
            ConstraintContract(
                name=(
                    "ck_commercial_entitlement_ledger_entries_"
                    "units_positive"
                ),
                kind=ConstraintKind.CHECK,
                columns=("units",),
                expression="units > 0",
            ),
            ConstraintContract(
                name=(
                    "fk_commercial_entitlement_ledger_entries_"
                    "related_entry"
                ),
                kind=ConstraintKind.FOREIGN_KEY,
                columns=("related_entry_id",),
                references=(
                    "commercial_entitlement_ledger_entries.entry_id"
                ),
            ),
        ),
        indexes=(
            IndexContract(
                name=(
                    "ix_commercial_entitlement_ledger_entries_"
                    "scope_occurred"
                ),
                columns=(
                    "tenant_id",
                    "subscription_id",
                    "occurred_at",
                ),
            ),
            IndexContract(
                name=(
                    "ix_commercial_entitlement_ledger_entries_"
                    "reservation"
                ),
                columns=(
                    "tenant_id",
                    "subscription_id",
                    "reservation_id",
                ),
                predicate="reservation_id IS NOT NULL",
            ),
            IndexContract(
                name=(
                    "ix_commercial_entitlement_ledger_entries_"
                    "related_entry"
                ),
                columns=("related_entry_id",),
                predicate="related_entry_id IS NOT NULL",
            ),
        ),
    )


def build_balances_table_contract() -> TableContract:
    return TableContract(
        name=BALANCES_TABLE,
        columns=(
            ColumnContract(
                "tenant_id",
                "UUID",
                ColumnNullability.REQUIRED,
            ),
            ColumnContract(
                "subscription_id",
                "UUID",
                ColumnNullability.REQUIRED,
            ),
            ColumnContract(
                "available_units",
                "BIGINT",
                ColumnNullability.REQUIRED,
                server_default="0",
            ),
            ColumnContract(
                "reserved_units",
                "BIGINT",
                ColumnNullability.REQUIRED,
                server_default="0",
            ),
            ColumnContract(
                "committed_units",
                "BIGINT",
                ColumnNullability.REQUIRED,
                server_default="0",
            ),
            ColumnContract(
                "version",
                "BIGINT",
                ColumnNullability.REQUIRED,
                server_default="0",
            ),
            ColumnContract(
                "calculated_at",
                "TIMESTAMP WITH TIME ZONE",
                ColumnNullability.REQUIRED,
            ),
            ColumnContract(
                "updated_at",
                "TIMESTAMP WITH TIME ZONE",
                ColumnNullability.REQUIRED,
                server_default="CURRENT_TIMESTAMP",
            ),
        ),
        constraints=(
            ConstraintContract(
                name="pk_commercial_entitlement_balances",
                kind=ConstraintKind.PRIMARY_KEY,
                columns=(
                    "tenant_id",
                    "subscription_id",
                ),
            ),
            ConstraintContract(
                name=(
                    "ck_commercial_entitlement_balances_"
                    "available_nonnegative"
                ),
                kind=ConstraintKind.CHECK,
                columns=("available_units",),
                expression="available_units >= 0",
            ),
            ConstraintContract(
                name=(
                    "ck_commercial_entitlement_balances_"
                    "reserved_nonnegative"
                ),
                kind=ConstraintKind.CHECK,
                columns=("reserved_units",),
                expression="reserved_units >= 0",
            ),
            ConstraintContract(
                name=(
                    "ck_commercial_entitlement_balances_"
                    "committed_nonnegative"
                ),
                kind=ConstraintKind.CHECK,
                columns=("committed_units",),
                expression="committed_units >= 0",
            ),
            ConstraintContract(
                name=(
                    "ck_commercial_entitlement_balances_"
                    "version_nonnegative"
                ),
                kind=ConstraintKind.CHECK,
                columns=("version",),
                expression="version >= 0",
            ),
        ),
        indexes=(
            IndexContract(
                name=(
                    "ix_commercial_entitlement_balances_"
                    "subscription"
                ),
                columns=("subscription_id",),
            ),
        ),
    )


def build_reservation_locks_table_contract() -> TableContract:
    return TableContract(
        name=RESERVATION_LOCKS_TABLE,
        columns=(
            ColumnContract(
                "tenant_id",
                "UUID",
                ColumnNullability.REQUIRED,
            ),
            ColumnContract(
                "subscription_id",
                "UUID",
                ColumnNullability.REQUIRED,
            ),
            ColumnContract(
                "reservation_id",
                "UUID",
                ColumnNullability.REQUIRED,
            ),
            ColumnContract(
                "owner_token",
                "VARCHAR(255)",
                ColumnNullability.REQUIRED,
            ),
            ColumnContract(
                "expires_at",
                "TIMESTAMP WITH TIME ZONE",
                ColumnNullability.REQUIRED,
            ),
            ColumnContract(
                "created_at",
                "TIMESTAMP WITH TIME ZONE",
                ColumnNullability.REQUIRED,
                server_default="CURRENT_TIMESTAMP",
            ),
            ColumnContract(
                "updated_at",
                "TIMESTAMP WITH TIME ZONE",
                ColumnNullability.REQUIRED,
                server_default="CURRENT_TIMESTAMP",
            ),
        ),
        constraints=(
            ConstraintContract(
                name=(
                    "pk_commercial_entitlement_reservation_locks"
                ),
                kind=ConstraintKind.PRIMARY_KEY,
                columns=(
                    "tenant_id",
                    "subscription_id",
                    "reservation_id",
                ),
            ),
            ConstraintContract(
                name=(
                    "ck_commercial_entitlement_reservation_locks_"
                    "owner_nonblank"
                ),
                kind=ConstraintKind.CHECK,
                columns=("owner_token",),
                expression="length(trim(owner_token)) > 0",
            ),
        ),
        indexes=(
            IndexContract(
                name=(
                    "ix_commercial_entitlement_reservation_locks_"
                    "expires"
                ),
                columns=("expires_at",),
            ),
        ),
    )


def build_entitlement_schema_contracts() -> tuple[
    TableContract,
    ...,
]:
    return (
        build_ledger_entries_table_contract(),
        build_balances_table_contract(),
        build_reservation_locks_table_contract(),
    )


def entitlement_schema_review_payload() -> dict[str, object]:
    tables = build_entitlement_schema_contracts()

    return {
        "version": ENTITLEMENT_LEDGER_SCHEMA_VERSION,
        "status": ENTITLEMENT_LEDGER_SCHEMA_STATUS,
        "models_enabled": ENTITLEMENT_LEDGER_MODELS_ENABLED,
        "migration_enabled": ENTITLEMENT_LEDGER_MIGRATION_ENABLED,
        "database_creation_enabled": (
            ENTITLEMENT_LEDGER_DATABASE_CREATION_ENABLED
        ),
        "runtime_persistence_enabled": (
            ENTITLEMENT_LEDGER_RUNTIME_PERSISTENCE_ENABLED
        ),
        "table_names": tuple(
            table.name
            for table in tables
        ),
        "constraint_names_explicit": True,
        "timezone_aware_timestamps_required": True,
        "scoped_idempotency_required": True,
        "optimistic_balance_version_required": True,
        "reservation_lock_scope_required": True,
    }


__all__ = [
    "BALANCES_TABLE",
    "ColumnContract",
    "ColumnNullability",
    "ConstraintContract",
    "ConstraintKind",
    "ENTITLEMENT_LEDGER_DATABASE_CREATION_ENABLED",
    "ENTITLEMENT_LEDGER_MIGRATION_ENABLED",
    "ENTITLEMENT_LEDGER_MODELS_ENABLED",
    "ENTITLEMENT_LEDGER_RUNTIME_PERSISTENCE_ENABLED",
    "ENTITLEMENT_LEDGER_SCHEMA_STATUS",
    "ENTITLEMENT_LEDGER_SCHEMA_VERSION",
    "IndexContract",
    "LEDGER_ENTRIES_TABLE",
    "RESERVATION_LOCKS_TABLE",
    "SchemaContractError",
    "TableContract",
    "build_balances_table_contract",
    "build_entitlement_schema_contracts",
    "build_ledger_entries_table_contract",
    "build_reservation_locks_table_contract",
    "entitlement_schema_review_payload",
]
