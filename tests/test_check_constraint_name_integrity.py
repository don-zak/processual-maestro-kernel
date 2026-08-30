from __future__ import annotations

import importlib.util
from pathlib import Path

from sqlalchemy import CheckConstraint, Column, Integer, MetaData, Table
from sqlalchemy.dialects import postgresql, sqlite

from tools.check_check_constraint_names import (
    _effective_constraint_name,
    _normalized_sqltext,
)


def _convention_constraint_name():
    metadata = MetaData(
        naming_convention={"ck": "ck_%(table_name)s_%(constraint_name)s"}
    )
    table = Table(
        "admin_market_assessment_commercial_terms",
        metadata,
        Column("billing_interval", Integer),
        CheckConstraint(
            "billing_interval >= 0",
            name="billing_interval_allowed",
        ),
    )
    constraint = next(
        item for item in table.constraints if isinstance(item, CheckConstraint)
    )
    return constraint.name


def _load_payment_destination_audit_migration():
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "20260804_0018_payment_destination_audit_vocabulary.py"
    )
    spec = importlib.util.spec_from_file_location("payment_destination_audit_0018", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_postgresql_long_check_name_is_rendered_with_deterministic_truncation() -> None:
    logical_name = _convention_constraint_name()
    dialect = postgresql.dialect()

    rendered = _effective_constraint_name(dialect, logical_name)

    assert len(rendered) <= dialect.max_identifier_length
    assert rendered != str(logical_name)
    assert rendered.startswith("ck_admin_market_assessment_commercial_terms_billing_int")
    assert rendered == _effective_constraint_name(dialect, logical_name)


def test_sqlite_keeps_same_logical_check_name_when_within_its_identifier_limit() -> None:
    logical_name = _convention_constraint_name()
    dialect = sqlite.dialect()

    assert _effective_constraint_name(dialect, logical_name) == str(logical_name)


def test_naming_convention_produces_expected_logical_name_before_dialect_rendering() -> None:
    logical_name = _convention_constraint_name()

    assert str(logical_name) == (
        "ck_admin_market_assessment_commercial_terms_billing_interval_allowed"
    )


def test_migration_0018_targets_historical_double_prefixed_audit_names() -> None:
    migration = _load_payment_destination_audit_migration()

    action_name = migration._historical_constraint_name(migration.ACTION_CONSTRAINT)
    resource_name = migration._historical_constraint_name(migration.RESOURCE_CONSTRAINT)

    assert str(action_name) == (
        "ck_admin_market_audit_records_"
        "ck_admin_market_audit_records_action_allowed"
    )
    assert str(resource_name) == (
        "ck_admin_market_audit_records_"
        "ck_admin_market_audit_records_resource_type_allowed"
    )


def test_migration_0018_historical_names_render_deterministically_on_postgresql() -> None:
    migration = _load_payment_destination_audit_migration()
    dialect = postgresql.dialect()

    action_name = migration._historical_constraint_name(migration.ACTION_CONSTRAINT)
    resource_name = migration._historical_constraint_name(migration.RESOURCE_CONSTRAINT)

    rendered_action = _effective_constraint_name(dialect, action_name)
    rendered_resource = _effective_constraint_name(dialect, resource_name)

    assert len(rendered_action) <= dialect.max_identifier_length
    assert len(rendered_resource) <= dialect.max_identifier_length
    assert rendered_action == _effective_constraint_name(dialect, action_name)
    assert rendered_resource == _effective_constraint_name(dialect, resource_name)
    assert rendered_action != migration.ACTION_CONSTRAINT
    assert rendered_resource != migration.RESOURCE_CONSTRAINT


def test_sqltext_normalization_ignores_only_formatting_noise() -> None:
    compact = "status IN ('draft','active') AND (flag = 1 OR flag = 2)"
    spaced = "status IN ( 'draft', 'active' ) AND ( flag = 1 OR flag = 2 )"

    assert _normalized_sqltext(compact) == _normalized_sqltext(spaced)


def test_sqltext_normalization_preserves_literal_semantics() -> None:
    left = "status IN ('Draft','active')"
    right = "status IN ('draft','active')"

    assert _normalized_sqltext(left) != _normalized_sqltext(right)


def test_sqltext_normalization_preserves_quoted_identifier_semantics() -> None:
    left = '"Status" = \'active\''
    right = '"status" = \'active\''

    assert _normalized_sqltext(left) != _normalized_sqltext(right)
