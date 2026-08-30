#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

from sqlalchemy import CheckConstraint, create_engine, inspect
from sqlalchemy.ext.asyncio import create_async_engine

from processual_api.admin_marketplace import models as admin_marketplace_models  # noqa: F401
from processual_api.auth import models as identity_auth_models  # noqa: F401
from processual_api.db.base import Base


def _effective_constraint_name(dialect: Any, logical_name: Any) -> str:
    """Render a SQLAlchemy constraint name exactly as the active dialect will."""
    preparer = dialect.identifier_preparer
    return preparer.truncate_and_render_constraint_name(
        logical_name,
        _alembic_quote=False,
    )


def expected_check_constraint_names(dialect: Any) -> dict[str, set[str]]:
    """Return dialect-rendered model names for focused naming regression tests."""
    expected: dict[str, set[str]] = {}
    for table in Base.metadata.sorted_tables:
        names: set[str] = set()
        for constraint in table.constraints:
            if not isinstance(constraint, CheckConstraint):
                continue
            if not constraint.name:
                raise RuntimeError(
                    f"Unnamed CHECK constraint is not allowed on {table.fullname}"
                )
            names.add(_effective_constraint_name(dialect, constraint.name))
        if names:
            expected[table.name] = names
    return expected


def _normalized_sqltext(value: Any) -> str:
    """Normalize server-reflected CHECK SQL without using constraint names."""
    text = str(value or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def _reflected_signatures(
    inspector: Any,
    table_name: str,
    *,
    schema: str | None = None,
) -> Counter[str]:
    return Counter(
        _normalized_sqltext(row.get("sqltext"))
        for row in inspector.get_check_constraints(table_name, schema=schema)
    )


def _compare_reflected_checks(
    actual_inspector: Any,
    reference_inspector: Any,
    *,
    reference_schema: str | None = None,
) -> dict[str, Any]:
    mismatches: list[dict[str, Any]] = []
    tables_checked = 0
    expected_count = 0

    for table in Base.metadata.sorted_tables:
        model_checks = [
            constraint
            for constraint in table.constraints
            if isinstance(constraint, CheckConstraint)
        ]
        if not model_checks:
            continue
        tables_checked += 1

        actual = _reflected_signatures(actual_inspector, table.name)
        reference = _reflected_signatures(
            reference_inspector,
            table.name,
            schema=reference_schema,
        )
        expected_count += sum(reference.values())

        if actual != reference:
            missing = sorted((reference - actual).elements())
            unexpected = sorted((actual - reference).elements())
            mismatches.append(
                {
                    "table": table.name,
                    "missing_definitions": missing,
                    "unexpected_definitions": unexpected,
                    "actual_count": sum(actual.values()),
                    "reference_count": sum(reference.values()),
                }
            )

    return {
        "tables_checked": tables_checked,
        "expected_check_constraints": expected_count,
        "mismatches": mismatches,
        "ok": not mismatches,
    }


def _inspect_postgresql(connection) -> dict[str, Any]:
    probe_schema = f"deep_integrity_probe_{uuid.uuid4().hex[:12]}"
    connection.exec_driver_sql(f'CREATE SCHEMA "{probe_schema}"')
    try:
        probe_connection = connection.execution_options(
            schema_translate_map={None: probe_schema}
        )
        Base.metadata.create_all(probe_connection)
        result = _compare_reflected_checks(
            inspect(connection),
            inspect(connection),
            reference_schema=probe_schema,
        )
    finally:
        connection.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{probe_schema}" CASCADE')
    result["comparison_mode"] = "postgresql_server_reflected_metadata_probe"
    return result


def _inspect_sqlite(connection) -> dict[str, Any]:
    reference_engine = create_engine("sqlite:///:memory:")
    try:
        Base.metadata.create_all(reference_engine)
        result = _compare_reflected_checks(
            inspect(connection),
            inspect(reference_engine),
        )
    finally:
        reference_engine.dispose()
    result["comparison_mode"] = "sqlite_reflected_metadata_probe"
    return result


def _inspect_sync(connection) -> dict[str, Any]:
    dialect_name = connection.dialect.name
    if dialect_name == "postgresql":
        result = _inspect_postgresql(connection)
    elif dialect_name == "sqlite":
        result = _inspect_sqlite(connection)
    else:
        raise RuntimeError(f"Unsupported dialect for CHECK verification: {dialect_name}")

    result["dialect"] = dialect_name
    return result


async def _run(database_url: str) -> dict[str, Any]:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            return await connection.run_sync(_inspect_sync)
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Verify CHECK constraints by comparing the migrated database with a "
            "fresh metadata-created reference under the same SQL dialect."
        )
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", ""),
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if not args.database_url:
        raise SystemExit("DATABASE_URL is required")

    result = asyncio.run(_run(args.database_url))
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
