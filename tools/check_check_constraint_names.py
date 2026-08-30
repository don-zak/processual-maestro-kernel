#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any

from sqlalchemy import CheckConstraint, inspect
from sqlalchemy.ext.asyncio import create_async_engine

from processual_api.admin_marketplace import models as admin_marketplace_models  # noqa: F401
from processual_api.auth import models as identity_auth_models  # noqa: F401
from processual_api.db.base import Base


def _effective_constraint_name(dialect: Any, logical_name: str) -> str:
    """Render the name exactly as SQLAlchemy will for the active dialect."""
    preparer = dialect.identifier_preparer
    return preparer.truncate_and_render_constraint_name(
        logical_name,
        _alembic_quote=False,
    )


def expected_check_constraint_names(dialect: Any) -> dict[str, set[str]]:
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
            names.add(_effective_constraint_name(dialect, str(constraint.name)))
        if names:
            expected[table.name] = names
    return expected


def _inspect_sync(connection) -> dict[str, Any]:
    inspector = inspect(connection)
    expected = expected_check_constraint_names(connection.dialect)
    mismatches: list[dict[str, Any]] = []

    for table_name, expected_names in sorted(expected.items()):
        reflected_rows = inspector.get_check_constraints(table_name)
        reflected_names = {
            str(row["name"])
            for row in reflected_rows
            if row.get("name") is not None
        }
        missing = sorted(expected_names - reflected_names)
        unexpected = sorted(reflected_names - expected_names)
        if missing or unexpected:
            mismatches.append(
                {
                    "table": table_name,
                    "missing": missing,
                    "unexpected": unexpected,
                }
            )

    return {
        "dialect": connection.dialect.name,
        "tables_checked": len(expected),
        "expected_check_constraints": sum(len(names) for names in expected.values()),
        "mismatches": mismatches,
        "ok": not mismatches,
    }


async def _run(database_url: str) -> dict[str, Any]:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            return await connection.run_sync(_inspect_sync)
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify reflected CHECK-constraint names using dialect-effective SQLAlchemy names."
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
