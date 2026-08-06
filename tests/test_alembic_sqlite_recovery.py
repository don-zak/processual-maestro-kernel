from __future__ import annotations

import pytest
import sqlalchemy as sa

from alembic.sqlite_recovery import cleanup_orphaned_batch_tables


def test_cleanup_removes_temp_table_when_source_exists() -> None:
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE admin_market_offers (id INTEGER PRIMARY KEY)"))
        connection.execute(sa.text("CREATE TABLE _alembic_tmp_admin_market_offers (id INTEGER PRIMARY KEY)"))

        removed = cleanup_orphaned_batch_tables(connection)

        assert removed == ("_alembic_tmp_admin_market_offers",)
        assert set(sa.inspect(connection).get_table_names()) == {"admin_market_offers"}


def test_cleanup_blocks_when_only_temp_table_exists() -> None:
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE _alembic_tmp_admin_market_offers (id INTEGER PRIMARY KEY)"))

        with pytest.raises(RuntimeError, match="Manual data recovery is required"):
            cleanup_orphaned_batch_tables(connection)

        assert sa.inspect(connection).get_table_names() == [
            "_alembic_tmp_admin_market_offers"
        ]


def test_cleanup_is_noop_without_batch_tables() -> None:
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE admin_market_offers (id INTEGER PRIMARY KEY)"))

        assert cleanup_orphaned_batch_tables(connection) == ()
