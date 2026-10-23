from __future__ import annotations

import asyncio

import pytest

from processual_api.db import session as db_session


def _set_pool(monkeypatch, *, minimum=2, maximum=10, timeout=30.0, recycle=1800):
    monkeypatch.setattr(db_session.settings, "database_url", "postgresql://user:pw@db:5432/app")
    monkeypatch.setattr(db_session.settings, "database_pool_min", minimum)
    monkeypatch.setattr(db_session.settings, "database_pool_max", maximum)
    monkeypatch.setattr(db_session.settings, "database_pool_timeout_seconds", timeout)
    monkeypatch.setattr(db_session.settings, "database_pool_recycle_seconds", recycle)
    monkeypatch.setattr(db_session.settings, "debug", False)


def test_pool_config_rejects_invalid_bounds(monkeypatch):
    _set_pool(monkeypatch, minimum=0)
    with pytest.raises(RuntimeError, match="DATABASE_POOL_MIN"):
        db_session._validated_pool_config()

    _set_pool(monkeypatch, minimum=5, maximum=4)
    with pytest.raises(RuntimeError, match="DATABASE_POOL_MAX"):
        db_session._validated_pool_config()

    _set_pool(monkeypatch, timeout=0)
    with pytest.raises(RuntimeError, match="DATABASE_POOL_TIMEOUT_SECONDS"):
        db_session._validated_pool_config()

    _set_pool(monkeypatch, recycle=0)
    with pytest.raises(RuntimeError, match="DATABASE_POOL_RECYCLE_SECONDS"):
        db_session._validated_pool_config()


def test_init_db_enables_stale_connection_defense_and_bounded_checkout(monkeypatch):
    _set_pool(monkeypatch, minimum=3, maximum=11, timeout=7.5, recycle=900)
    captured: dict[str, object] = {}
    engine = object()
    factory = object()

    def fake_create_async_engine(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return engine

    def fake_sessionmaker(actual_engine, **kwargs):
        captured["session_engine"] = actual_engine
        captured["session_kwargs"] = kwargs
        return factory

    monkeypatch.setattr(db_session, "create_async_engine", fake_create_async_engine)
    monkeypatch.setattr(db_session, "async_sessionmaker", fake_sessionmaker)
    monkeypatch.setattr(db_session, "AsyncSession", object)
    monkeypatch.setattr(db_session, "_engine", None)
    monkeypatch.setattr(db_session, "_session_factory", None)

    asyncio.run(db_session.init_db())

    assert captured["url"] == "postgresql+asyncpg://user:pw@db:5432/app"
    assert captured["pool_size"] == 3
    assert captured["max_overflow"] == 8
    assert captured["pool_pre_ping"] is True
    assert captured["pool_timeout"] == 7.5
    assert captured["pool_recycle"] == 900
    assert captured["echo"] is False
    assert captured["session_engine"] is engine
    assert db_session._engine is engine
    assert db_session._session_factory is factory
