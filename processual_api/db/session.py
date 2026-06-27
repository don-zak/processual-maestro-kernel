from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from ..settings import settings

try:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
except ImportError:
    AsyncSession = None
    async_sessionmaker = None
    create_async_engine = None

_engine = None
_session_factory = None


def _get_database_url() -> str:
    url = settings.database_url
    if not url:
        return ""
    if url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


async def init_db():
    global _engine, _session_factory
    url = _get_database_url()
    if not url or create_async_engine is None:
        return
    _engine = create_async_engine(
        url,
        pool_size=settings.database_pool_min,
        max_overflow=settings.database_pool_max - settings.database_pool_min,
        echo=settings.debug,
    )
    _session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def close_db():
    global _engine, _session_factory
    if _engine is not None:
        try:
            await _engine.dispose()
        except TypeError:
            pass
    _engine = None
    _session_factory = None


async def get_session() -> AsyncGenerator[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("Database not initialized. Set DATABASE_URL and call init_db().")
    async with _session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


@asynccontextmanager
async def session_scope():
    if _session_factory is None:
        raise RuntimeError("Database not initialized. Set DATABASE_URL and call init_db().")
    session = _session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def check_db_connection() -> bool:
    if not settings.database_url or _engine is None:
        return False
    try:
        async with _engine.connect():
            return True
    except Exception:
        return False
