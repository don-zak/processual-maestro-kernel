from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

_BATCH_TEMP_PREFIX = "_alembic_tmp_"
_STALE_VERSION = "20260804_0019"
_RECOVERED_VERSION = "20260806_0030"
_HEAD_TABLES = {
    "admin_market_lemon_squeezy_webhook_inbox",
    "admin_market_lemon_squeezy_reconciliation_decisions",
    "admin_market_subscription_runtime",
    "admin_market_subscription_runtime_transitions",
}


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


def recover_uncommitted_head_version(connection: Connection) -> bool:
    """Repair the exact SQLite state where DDL reached head but version did not."""
    if connection.dialect.name != "sqlite":
        return False

    inspector = sa.inspect(connection)
    table_names = set(inspector.get_table_names())
    if "alembic_version" not in table_names:
        return False

    current = connection.scalar(sa.text("SELECT version_num FROM alembic_version"))
    if current != _STALE_VERSION:
        return False

    offers_columns = {
        column["name"] for column in inspector.get_columns("admin_market_offers")
    }
    present_head_tables = _HEAD_TABLES & table_names
    inbox_uniques = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints(
            "admin_market_lemon_squeezy_webhook_inbox"
        )
        if constraint.get("name")
    } if "admin_market_lemon_squeezy_webhook_inbox" in table_names else set()

    head_complete = (
        present_head_tables == _HEAD_TABLES
        and {"sales_channel", "billing_period"} <= offers_columns
        and "uq_admin_market_ls_webhook_event_identity" in inbox_uniques
        and "uq_admin_market_ls_webhook_payload_digest" in inbox_uniques
        and "uq_admin_market_ls_webhook_resource_binding" not in inbox_uniques
    )
    advanced_schema_present = bool(
        present_head_tables or {"sales_channel", "billing_period"} & offers_columns
    )

    if not head_complete:
        if advanced_schema_present:
            raise RuntimeError(
                "SQLite migration recovery blocked: schema is partially ahead of "
                "alembic_version. Manual inspection is required."
            )
        return False

    connection.execute(
        sa.text("UPDATE alembic_version SET version_num = :version"),
        {"version": _RECOVERED_VERSION},
    )
    return True


__all__ = [
    "cleanup_orphaned_batch_tables",
    "recover_uncommitted_head_version",
]
