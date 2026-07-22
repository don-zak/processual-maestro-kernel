from __future__ import annotations

import os
import uuid
from types import SimpleNamespace

import httpx
import pytest
import redis.asyncio as redis_async
from fastapi import FastAPI
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import processual_api.auth.session_runtime as runtime_module
import processual_api.auth.session_service as service_module
from processual_api.auth.models import AuthRefreshToken, AuthSession, IdentityUser
from processual_api.auth.passwords import PasswordService
from processual_api.auth.session_router import get_session_runtime, router
from processual_api.auth.session_runtime import build_session_runtime

DATABASE_URL = os.environ.get("AUTH_R5B_INTEGRATION_DATABASE_URL", "")
REDIS_URL = os.environ.get("AUTH_R5B_INTEGRATION_REDIS_URL", "")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL or not REDIS_URL,
    reason="Set the AUTH_R5B PostgreSQL and Redis URLs to run the R7 gate.",
)


@pytest.mark.asyncio
async def test_login_refresh_replay_revokes_family_with_real_postgresql_and_redis(monkeypatch):
    database_url = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    redis = redis_async.from_url(REDIS_URL, decode_responses=True)
    suffix = uuid.uuid4().hex
    email = f"auth-r7-{suffix}@example.test"
    user_id = uuid.uuid4()
    config = SimpleNamespace(
        auth_token_pepper=("token-" + suffix)[:32],
        auth_rate_limit_pepper=("rate-limit-" + suffix)[:32],
        auth_trusted_proxy_cidrs=(),
        auth_trusted_proxy_max_hops=8,
        auth_login_min_response_ms=0,
        auth_access_token_seconds=900,
        auth_refresh_token_days=30,
        auth_failed_login_limit=5,
        auth_login_lockout_seconds=900,
    )

    async def actual_redis():
        return redis

    monkeypatch.setattr(runtime_module, "get_redis", actual_redis)
    monkeypatch.setattr(runtime_module, "get_session_factory", lambda: session_factory)
    monkeypatch.setattr(
        service_module,
        "create_access_token",
        lambda **values: f"integration-access:{values['session_id']}",
    )
    runtime = await build_session_runtime(config)
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_session_runtime] = lambda: runtime

    async with session_factory() as session:
        session.add(
            IdentityUser(
                id=user_id,
                email_normalized=email,
                display_name="R7 Integration",
                password_hash=PasswordService().hash_password("integration-password"),
                status="active",
            )
        )
        await session.commit()

    try:
        transport = httpx.ASGITransport(app=app, client=("198.51.100.47", 47003))
        async with httpx.AsyncClient(transport=transport, base_url="https://test") as client:
            login = await client.post(
                "/auth/login",
                json={"email": email, "password": "integration-password"},
            )
            assert login.status_code == 200
            assert "refresh" not in login.text
            old_refresh = client.cookies.get("pmk_refresh_token")
            csrf = client.cookies.get("pmk_csrf_token")
            assert old_refresh and csrf

            refreshed = await client.post(
                "/auth/session/refresh",
                headers={"X-CSRF-Token": csrf},
            )
            assert refreshed.status_code == 200
            assert refreshed.json()["access_token"].startswith("integration-access:")

            replacement_csrf = client.cookies.get("pmk_csrf_token")
            client.cookies.delete("pmk_refresh_token", path="/auth/session")
            client.cookies.set("pmk_refresh_token", old_refresh, path="/auth/session")
            replay = await client.post(
                "/auth/session/refresh",
                headers={"X-CSRF-Token": replacement_csrf},
            )
            assert replay.status_code == 401
            assert old_refresh not in replay.text

        async with session_factory() as session:
            auth_session = await session.scalar(
                select(AuthSession).where(AuthSession.user_id == user_id)
            )
            refresh_tokens = list(
                (
                    await session.scalars(
                        select(AuthRefreshToken)
                        .where(AuthRefreshToken.session_id == auth_session.id)
                        .order_by(AuthRefreshToken.issued_at)
                    )
                ).all()
            )
            assert auth_session.revoke_reason == "refresh_token_reuse"
            assert refresh_tokens[0].reuse_detected_at is not None
            assert all(token.revoked_at is not None for token in refresh_tokens)
    finally:
        async with session_factory() as session:
            await session.execute(delete(IdentityUser).where(IdentityUser.id == user_id))
            await session.commit()
        await redis.aclose()
        await engine.dispose()
