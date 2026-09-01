from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from processual_api.admin_marketplace import models as admin_marketplace_models  # noqa: F401
from processual_api.auth import models as identity_auth_models  # noqa: F401
from processual_api.db.base import Base
from processual_api.db.sqlite_migration_recovery import (
    cleanup_orphaned_batch_tables,
    recover_uncommitted_head_version,
)
from processual_api.services import evaluation_runtime_delivery_models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Alembic 1.19 added name-only CHECK-constraint autogeneration. Our naming
# convention intentionally produces descriptive logical names that SQLAlchemy
# deterministically truncates for PostgreSQL's identifier limit. Reflection
# sees the rendered/truncated name, while the new plugin compares it to the
# logical metadata name and reports false drift. CHECK-name parity is therefore
# verified independently by tools/check_check_constraint_names.py using the
# active dialect's own identifier preparer instead of disabling the integrity
# check outright.
AUTOGENERATE_PLUGINS = [
    "alembic.autogenerate.*",
    "~alembic.autogenerate.checkconstraint_byname",
]


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL", config.get_main_option("sqlalchemy.url"))
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        autogenerate_plugins=AUTOGENERATE_PLUGINS,
    )
    with context.begin_transaction():
        context.run_migrations()


def _run_sync_migrations(connection) -> None:
    cleanup_orphaned_batch_tables(connection)
    recovered = recover_uncommitted_head_version(connection)
    if recovered:
        connection.commit()

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        autogenerate_plugins=AUTOGENERATE_PLUGINS,
    )
    with context.begin_transaction():
        context.run_migrations()
    connection.commit()


async def _run_async_migrations() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _database_url()
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(_run_sync_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(_run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
