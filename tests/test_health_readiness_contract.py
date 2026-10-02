from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from processual_api.cache import redis as redis_module
from processual_api.db import session as db_session
from processual_api.routers import health


async def _true() -> bool:
    return True


async def _false() -> bool:
    return False


def _adapter_ok(_path):
    return SimpleNamespace(ok=True, status="ok", detail="verified")


@pytest.mark.asyncio
async def test_public_readiness_does_not_require_private_cgt(monkeypatch):
    monkeypatch.setattr(health, "_CGT_PRIVATE", False)
    monkeypatch.setattr(health.settings, "require_private_cgt_for_readiness", False)
    monkeypatch.setattr(health.settings, "database_url", "postgresql+asyncpg://configured")
    monkeypatch.setattr(health.settings, "redis_url", "redis://configured")
    monkeypatch.setattr(db_session, "check_db_connection", _true)
    monkeypatch.setattr(redis_module, "check_redis_connection", _true)
    monkeypatch.setattr(health, "check_adapter_config_integrity", _adapter_ok)

    response = await health.health_ready()
    payload = json.loads(response.body)

    assert response.status_code == 200
    assert payload["status"] == "ready"
    assert payload["dependencies"]["cgtlib"] is False
    assert payload["readiness"]["private_cgt_required"] is False
    assert "cgtlib" not in payload["readiness"]["required_dependencies"]


@pytest.mark.asyncio
async def test_private_readiness_requires_private_cgt(monkeypatch):
    monkeypatch.setattr(health, "_CGT_PRIVATE", False)
    monkeypatch.setattr(health.settings, "require_private_cgt_for_readiness", True)
    monkeypatch.setattr(health.settings, "database_url", "postgresql+asyncpg://configured")
    monkeypatch.setattr(health.settings, "redis_url", "redis://configured")
    monkeypatch.setattr(db_session, "check_db_connection", _true)
    monkeypatch.setattr(redis_module, "check_redis_connection", _true)
    monkeypatch.setattr(health, "check_adapter_config_integrity", _adapter_ok)

    response = await health.health_ready()
    payload = json.loads(response.body)

    assert response.status_code == 503
    assert payload["status"] == "degraded"
    assert payload["readiness"]["private_cgt_required"] is True
    assert "cgtlib" in payload["readiness"]["required_dependencies"]


@pytest.mark.asyncio
async def test_required_dependency_failure_returns_503(monkeypatch):
    monkeypatch.setattr(health, "_CGT_PRIVATE", True)
    monkeypatch.setattr(health.settings, "require_private_cgt_for_readiness", True)
    monkeypatch.setattr(health.settings, "database_url", "postgresql+asyncpg://configured")
    monkeypatch.setattr(health.settings, "redis_url", "redis://configured")
    monkeypatch.setattr(db_session, "check_db_connection", _false)
    monkeypatch.setattr(redis_module, "check_redis_connection", _true)
    monkeypatch.setattr(health, "check_adapter_config_integrity", _adapter_ok)

    response = await health.health_ready()
    payload = json.loads(response.body)

    assert response.status_code == 503
    assert payload["status"] == "degraded"
    assert payload["dependencies"]["database"] is False
