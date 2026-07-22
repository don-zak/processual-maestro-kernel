from __future__ import annotations

import base64
import json
import os
import uuid
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
from processual_api.auth.models import (
    AuthActionToken,
    AuthDeliveryOutbox,
    IdentityOrganization,
    IdentityUser,
    OrganizationMembership,
)
from processual_api.auth.rate_limit import ORGANIZATION_REGISTRATION_RULES, REGISTRATION_RULES
from processual_api.auth.registration_router import get_registration_runtime, router
from processual_api.auth.registration_runtime import build_registration_runtime
from processual_api.auth.token_material import TokenDigester
from processual_api.middleware.request_id import RequestIDMiddleware

DATABASE_URL = os.environ.get("AUTH_R5B_INTEGRATION_DATABASE_URL", "")
REDIS_URL = os.environ.get("AUTH_R5B_INTEGRATION_REDIS_URL", "")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL or not REDIS_URL,
    reason=(
        "Set AUTH_R5B_INTEGRATION_DATABASE_URL and AUTH_R5B_INTEGRATION_REDIS_URL "
        "to run the real PostgreSQL/Redis gate."
    ),
)


@pytest.mark.asyncio
async def test_registration_http_uses_real_postgresql_and_redis(monkeypatch):
    database_url = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    redis = redis_async.from_url(REDIS_URL, decode_responses=True)
    suffix = uuid.uuid4().hex
    email = f"auth-r5b-{suffix}@example.test"
    organization_email = f"auth-r5b-org-{suffix}@example.test"
    token_pepper = ("token-" + suffix)[:32]
    rate_pepper = ("rate-limit-" + suffix)[:32]
    delivery_key = uuid.uuid4().bytes + uuid.uuid4().bytes
    config = SimpleNamespace(
        auth_token_pepper=token_pepper,
        auth_rate_limit_pepper=rate_pepper,
        auth_delivery_key_ring_json=json.dumps({"integration-v1": base64.b64encode(delivery_key).decode()}),
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
    expected_rate_keys = {
        runtime.rate_limiter._key(  # noqa: SLF001 - integration proof of persisted key shape
            action="register_individual",
            rule=rule,
            value="198.51.100.44" if rule.dimension == "ip" else email,
        )
        for rule in REGISTRATION_RULES
    }
    expected_rate_keys.update(
        runtime.rate_limiter._key(  # noqa: SLF001 - integration proof of persisted key shape
            action="register_organization",
            rule=rule,
            value="198.51.100.44" if rule.dimension == "ip" else organization_email,
        )
        for rule in ORGANIZATION_REGISTRATION_RULES
    )

    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)
    app.include_router(router)
    app.dependency_overrides[get_registration_runtime] = lambda: runtime
    transport = httpx.ASGITransport(app=app, client=("198.51.100.44", 47000))

    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/auth/register",
                json={
                    "email": email,
                    "full_name": "R5B Integration",
                    "password": "integration-only-password-value",
                    "accepted_terms_version": "2026-07",
                },
                headers={"X-Request-ID": f"r5b-{suffix}"},
            )

        assert response.status_code == 202
        assert response.json() == {"status": "accepted", "next_action": "check_email"}

        async with session_factory() as session:
            row = (
                await session.execute(
                    select(IdentityUser, AuthActionToken, AuthDeliveryOutbox)
                    .join(AuthActionToken, AuthActionToken.user_id == IdentityUser.id)
                    .join(AuthDeliveryOutbox, AuthDeliveryOutbox.user_id == IdentityUser.id)
                    .where(IdentityUser.email_normalized == email)
                )
            ).one()
            user, action_token, outbox = row
            cipher = DeliveryPayloadCipher(
                current_key_version="integration-v1",
                keys={"integration-v1": delivery_key},
            )
            raw_token = cipher.decrypt(
                EncryptedDeliveryPayload(
                    ciphertext=bytes(outbox.payload_ciphertext),
                    key_version=outbox.payload_key_version,
                ),
                outbox_id=str(outbox.id),
                user_id=str(user.id),
                action_token_id=str(action_token.id),
                purpose="verify_email",
            )
            assert TokenDigester(token_pepper.encode()).matches(
                raw_token,
                action_token.token_hash,
                purpose="verify_email",
            )
            assert raw_token not in response.text
            await session.execute(delete(IdentityUser).where(IdentityUser.id == user.id))
            await session.commit()

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            organization_response = await client.post(
                "/auth/register/organization",
                json={
                    "email": organization_email,
                    "full_name": "R5B Organization Owner",
                    "password": "organization-integration-password",
                    "accepted_terms_version": "2026-07",
                    "organization_name": "R5B Integration Organization",
                },
                headers={"X-Request-ID": f"r5b-org-{suffix}"},
            )

        assert organization_response.status_code == 202
        assert organization_response.json() == {
            "status": "accepted",
            "next_action": "check_email",
        }

        async with session_factory() as session:
            organization_row = (
                await session.execute(
                    select(
                        IdentityUser,
                        IdentityOrganization,
                        OrganizationMembership,
                        AuthDeliveryOutbox,
                    )
                    .join(
                        OrganizationMembership,
                        OrganizationMembership.user_id == IdentityUser.id,
                    )
                    .join(
                        IdentityOrganization,
                        IdentityOrganization.id == OrganizationMembership.organization_id,
                    )
                    .join(AuthDeliveryOutbox, AuthDeliveryOutbox.user_id == IdentityUser.id)
                    .where(IdentityUser.email_normalized == organization_email)
                )
            ).one()
            organization_user, organization, membership, organization_outbox = organization_row
            assert organization.status == "pending_review"
            assert membership.role == "organization_owner"
            assert organization_outbox.payload_key_version == "integration-v1"
            await session.execute(delete(IdentityUser).where(IdentityUser.id == organization_user.id))
            await session.execute(delete(IdentityOrganization).where(IdentityOrganization.id == organization.id))
            await session.commit()

        key_presence = [await redis.exists(key) for key in expected_rate_keys]
        assert all(key_presence)
    finally:
        async with session_factory() as cleanup_session:
            await cleanup_session.execute(
                delete(IdentityUser).where(IdentityUser.email_normalized.in_((email, organization_email)))
            )
            await cleanup_session.execute(
                delete(IdentityOrganization).where(IdentityOrganization.display_name == "R5B Integration Organization")
            )
            await cleanup_session.commit()
        await redis.delete(*expected_rate_keys)
        await redis.aclose()
        await engine.dispose()
