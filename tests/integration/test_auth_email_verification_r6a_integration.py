from __future__ import annotations

import base64
import json
import os
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import httpx
import pytest
import redis.asyncio as redis_async
from fastapi import FastAPI
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import processual_api.auth.registration_runtime as runtime_module
from processual_api.auth.delivery_crypto import (
    DeliveryPayloadCipher,
    EncryptedDeliveryPayload,
)
from processual_api.auth.models import AuthActionToken, AuthDeliveryOutbox, IdentityUser
from processual_api.auth.registration_router import get_registration_runtime, router
from processual_api.auth.registration_runtime import build_registration_runtime
from processual_api.middleware.request_id import RequestIDMiddleware

DATABASE_URL = os.environ.get("AUTH_R5B_INTEGRATION_DATABASE_URL", "")
REDIS_URL = os.environ.get("AUTH_R5B_INTEGRATION_REDIS_URL", "")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL or not REDIS_URL,
    reason="Set the AUTH_R5B PostgreSQL and Redis URLs to run the R6A gate.",
)


def _decrypt(cipher, outbox, token) -> str:
    return cipher.decrypt(
        EncryptedDeliveryPayload(
            ciphertext=bytes(outbox.payload_ciphertext),
            key_version=outbox.payload_key_version,
        ),
        outbox_id=str(outbox.id),
        user_id=str(outbox.user_id),
        action_token_id=str(token.id),
        purpose="verify_email",
    )


@pytest.mark.asyncio
async def test_verify_resend_rotation_and_replay_use_real_postgresql_and_redis(monkeypatch):
    database_url = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    redis = redis_async.from_url(REDIS_URL, decode_responses=True)
    suffix = uuid.uuid4().hex
    email = f"auth-r6a-{suffix}@example.test"
    delivery_key = uuid.uuid4().bytes + uuid.uuid4().bytes
    config = SimpleNamespace(
        auth_token_pepper=("token-" + suffix)[:32],
        auth_rate_limit_pepper=("rate-limit-" + suffix)[:32],
        auth_delivery_key_ring_json=json.dumps(
            {"integration-v1": base64.b64encode(delivery_key).decode()}
        ),
        auth_delivery_current_key_version="integration-v1",
        auth_trusted_proxy_cidrs=(),
        auth_trusted_proxy_max_hops=8,
        auth_registration_min_response_ms=0,
    )

    async def actual_redis():
        return redis

    monkeypatch.setattr(runtime_module, "get_redis", actual_redis)
    monkeypatch.setattr(runtime_module, "get_session_factory", lambda: session_factory)
    runtime = await build_registration_runtime(config)
    cipher = DeliveryPayloadCipher(
        current_key_version="integration-v1",
        keys={"integration-v1": delivery_key},
    )
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)
    app.include_router(router)
    app.dependency_overrides[get_registration_runtime] = lambda: runtime
    transport = httpx.ASGITransport(app=app, client=("198.51.100.45", 47001))

    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            registration = await client.post(
                "/auth/register",
                json={
                    "email": email,
                    "full_name": "R6A Integration",
                    "password": "integration-only-password-value",
                    "accepted_terms_version": "2026-07",
                },
            )
            assert registration.status_code == 202

            async with session_factory() as session:
                user = await session.scalar(
                    select(IdentityUser).where(IdentityUser.email_normalized == email)
                )
                original_token = await session.scalar(
                    select(AuthActionToken).where(AuthActionToken.user_id == user.id)
                )
                original_outbox = await session.scalar(
                    select(AuthDeliveryOutbox).where(
                        AuthDeliveryOutbox.action_token_id == original_token.id
                    )
                )
                original_raw = _decrypt(cipher, original_outbox, original_token)
                original_token.created_at = datetime.now(UTC) - timedelta(minutes=2)
                await session.commit()

            resend = await client.post(
                "/auth/verification/resend",
                json={"email": email},
            )
            assert resend.status_code == 202
            assert resend.json() == {"status": "accepted", "next_action": "check_email"}

            async with session_factory() as session:
                tokens = list(
                    (
                        await session.scalars(
                            select(AuthActionToken)
                            .where(AuthActionToken.user_id == user.id)
                            .order_by(AuthActionToken.created_at)
                        )
                    ).all()
                )
                assert len(tokens) == 2
                assert tokens[0].invalidated_at is not None
                assert tokens[1].invalidated_at is None
                replacement_outbox = await session.scalar(
                    select(AuthDeliveryOutbox).where(
                        AuthDeliveryOutbox.action_token_id == tokens[1].id
                    )
                )
                replacement_raw = _decrypt(cipher, replacement_outbox, tokens[1])

            verified = await client.post(
                "/auth/verify-email",
                json={"token": replacement_raw},
            )
            replay = await client.post(
                "/auth/verify-email",
                json={"token": replacement_raw},
            )
            invalidated = await client.post(
                "/auth/verify-email",
                json={"token": original_raw},
            )
            assert verified.status_code == replay.status_code == invalidated.status_code == 200
            assert verified.json() == replay.json() == invalidated.json() == {"status": "processed"}

            async with session_factory() as session:
                persisted_user = await session.get(IdentityUser, user.id)
                replacement = await session.get(AuthActionToken, tokens[1].id)
                assert persisted_user.status == "active"
                assert persisted_user.email_verified_at is not None
                assert replacement.consumed_at is not None

    finally:
        async with session_factory() as session:
            await session.execute(delete(IdentityUser).where(IdentityUser.email_normalized == email))
            await session.commit()
        await redis.aclose()
        await engine.dispose()
