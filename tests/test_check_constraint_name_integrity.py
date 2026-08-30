from __future__ import annotations

from sqlalchemy import CheckConstraint, Column, Integer, MetaData, Table
from sqlalchemy.dialects import postgresql, sqlite

from tools.check_check_constraint_names import _effective_constraint_name


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
