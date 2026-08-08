from __future__ import annotations

import pytest
import sqlalchemy as sa

from processual_api.db.sqlite_migration_recovery import (
    cleanup_orphaned_batch_tables,
    recover_uncommitted_head_version,
)


def test_cleanup_removes_temp_table_when_source_exists() -> None:
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            sa.text("CREATE TABLE admin_market_offers (id INTEGER PRIMARY KEY)")
        )
        connection.execute(
            sa.text(
                "CREATE TABLE _alembic_tmp_admin_market_offers "
                "(id INTEGER PRIMARY KEY)"
            )
        )

        removed = cleanup_orphaned_batch_tables(connection)

        assert removed == ("_alembic_tmp_admin_market_offers",)
        assert set(sa.inspect(connection).get_table_names()) == {
            "admin_market_offers"
        }


def test_cleanup_blocks_when_only_temp_table_exists() -> None:
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "CREATE TABLE _alembic_tmp_admin_market_offers "
                "(id INTEGER PRIMARY KEY)"
            )
        )

        with pytest.raises(RuntimeError, match="Manual data recovery is required"):
            cleanup_orphaned_batch_tables(connection)

        assert sa.inspect(connection).get_table_names() == [
            "_alembic_tmp_admin_market_offers"
        ]


def test_cleanup_is_noop_without_batch_tables() -> None:
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            sa.text("CREATE TABLE admin_market_offers (id INTEGER PRIMARY KEY)")
        )

        assert cleanup_orphaned_batch_tables(connection) == ()


def _create_recoverable_head_schema(connection: sa.Connection) -> None:
    connection.execute(
        sa.text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
    )
    connection.execute(
        sa.text("INSERT INTO alembic_version VALUES ('20260804_0019')")
    )
    connection.execute(
        sa.text(
            "CREATE TABLE admin_market_offers ("
            "id INTEGER PRIMARY KEY, sales_channel VARCHAR(32), "
            "billing_period VARCHAR(16))"
        )
    )
    connection.execute(
        sa.text(
            "CREATE TABLE admin_market_lemon_squeezy_webhook_inbox ("
            "id INTEGER PRIMARY KEY, event_identity_hash VARCHAR(64), "
            "payload_digest VARCHAR(64), "
            "CONSTRAINT uq_admin_market_ls_webhook_event_identity "
            "UNIQUE (event_identity_hash), "
            "CONSTRAINT uq_admin_market_ls_webhook_payload_digest "
            "UNIQUE (payload_digest))"
        )
    )
    for table_name in (
        "admin_market_lemon_squeezy_reconciliation_decisions",
        "admin_market_subscription_runtime",
        "admin_market_subscription_runtime_transitions",
    ):
        connection.execute(
            sa.text(f"CREATE TABLE {table_name} (id INTEGER PRIMARY KEY)")
        )


def test_recover_uncommitted_head_version_for_exact_complete_schema() -> None:
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        _create_recoverable_head_schema(connection)

        assert recover_uncommitted_head_version(connection) is True
        assert connection.scalar(
            sa.text("SELECT version_num FROM alembic_version")
        ) == "20260806_0030"


def test_recover_uncommitted_head_version_blocks_partial_schema() -> None:
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            sa.text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        )
        connection.execute(
            sa.text("INSERT INTO alembic_version VALUES ('20260804_0019')")
        )
        connection.execute(
            sa.text(
                "CREATE TABLE admin_market_offers ("
                "id INTEGER PRIMARY KEY, sales_channel VARCHAR(32))"
            )
        )

        with pytest.raises(RuntimeError, match="partially ahead"):
            recover_uncommitted_head_version(connection)


def test_recover_uncommitted_head_version_is_noop_for_other_version() -> None:
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        _create_recoverable_head_schema(connection)
        connection.execute(
            sa.text(
                "UPDATE alembic_version SET version_num = '20260806_0030'"
            )
        )

        assert recover_uncommitted_head_version(connection) is False
