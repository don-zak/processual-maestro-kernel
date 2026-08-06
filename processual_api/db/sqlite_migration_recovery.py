from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

_BATCH_TEMP_PREFIX = "_alembic_tmp_"


def cleanup_orphaned_batch_tables(connection: Connection) -> tuple[str, ...]:
    """Remove stale Alembic batch tables only when the source table is intact."""
    if connection.dialect.name != "sqlite":
        return ()

    table_names = set(sa.inspect(connection).get_table_names())
    removed: list[str] = []
    for temporary_name in sorted(
        name for name in table_names if name.startswith(_BATCH_TEMP_PREFIX)
    ):
        source_name = temporary_name.removeprefix(_BATCH_TEMP_PREFIX)
        if not source_name or source_name not in table_names:
            raise RuntimeError(
                "SQLite migration recovery blocked: an Alembic batch table exists "
                "without its source table. Manual data recovery is required."
            )
        quoted_name = connection.dialect.identifier_preparer.quote(temporary_name)
        connection.execute(sa.text(f"DROP TABLE {quoted_name}"))
        removed.append(temporary_name)

    return tuple(removed)


__all__ = ["cleanup_orphaned_batch_tables"]
