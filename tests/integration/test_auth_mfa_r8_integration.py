from __future__ import annotations

import base64
import json
import os
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
import redis.asyncio as redis_async
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import processual_api.auth.mfa_runtime as runtime_module
from processual_api.auth.mfa_runtime import build_mfa_runtime
from processual_api.auth.mfa_service import InvalidMfaCredentialError
from processual_api.auth.models import (
    AuthMfaFactor,
    AuthMfaRecoveryCode,
    AuthRefreshToken,
    AuthSession,
    IdentityUser,
)
from processual_api.auth.totp import totp_code_for_step

DATABASE_URL = os.environ.get("AUTH_R5B_INTEGRATION_DATABASE_URL", "")
REDIS_URL = os.environ.get("AUTH_R5B_INTEGRATION_REDIS_URL", "")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL or not REDIS_URL,
    reason="Set the AUTH_R5B PostgreSQL and Redis URLs to run the R8 gate.",
)


@pytest.mark.asyncio
async def test_totp_enrollment_replay_and_recovery_with_real_postgresql_and_redis(monkeypatch):
    database_url = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    redis = redis_async.from_url(REDIS_URL, decode_responses=True)
    suffix = uuid.uuid4().hex
    user_id = uuid.uuid4()
    session_id = uuid.uuid4()
    now = datetime.now(UTC)
    config = SimpleNamespace(
        auth_mfa_key_ring_json=json.dumps(
            {"v1": base64.b64encode(b"m" * 32).decode()}
        ),
        auth_mfa_current_key_version="v1",
        auth_mfa_issuer="Processual Maestro Test",
        auth_mfa_recovery_code_count=8,
        auth_mfa_step_up_seconds=300,
        auth_token_pepper=("token-" + suffix)[:32],
        auth_rate_limit_pepper=("rate-limit-" + suffix)[:32],
        auth_trusted_proxy_cidrs=(),
        auth_trusted_proxy_max_hops=8,
    )

    async def actual_redis():
        return redis

    monkeypatch.setattr(runtime_module, "get_redis", actual_redis)
    monkeypatch.setattr(runtime_module, "get_session_factory", lambda: session_factory)
    runtime = await build_mfa_runtime(config)

    async with session_factory() as session:
        user = IdentityUser(
            id=user_id,
            email_normalized=f"auth-r8-{suffix}@example.test",
            display_name="R8 Integration",
            password_hash="not-used-by-this-test",
            status="active",
        )
        auth_session = AuthSession(
            id=session_id,
            user_id=user_id,
            refresh_family_id=uuid.uuid4(),
            authenticated_at=now,
            last_seen_at=now,
            expires_at=now + timedelta(hours=1),
            user=user,
        )
        session.add(auth_session)
        session.add(
            AuthRefreshToken(
                session_id=session_id,
                token_hash=("refresh-" + suffix),
                issued_at=now,
                expires_at=now + timedelta(hours=1),
                session=auth_session,
            )
        )
        await session.commit()

    try:
        enrollment = await runtime.service.enroll(user_id=user_id, label="Integration")
        padding = "=" * ((8 - len(enrollment.secret) % 8) % 8)
        factor_secret = base64.b32decode(enrollment.secret + padding)
        code = totp_code_for_step(factor_secret, int(datetime.now(UTC).timestamp()) // 30)
        recovery_codes = await runtime.service.confirm_enrollment(
            user_id=user_id,
            session_id=session_id,
            code=code,
        )
        assert len(recovery_codes) == 8

        with pytest.raises(InvalidMfaCredentialError):
            await runtime.service.verify(
                user_id=user_id,
                session_id=session_id,
                code=code,
                recovery_code=None,
            )

        async with session_factory() as session:
            factor = await session.scalar(
                select(AuthMfaFactor).where(AuthMfaFactor.user_id == user_id)
            )
            stored_codes = list(
                (
                    await session.scalars(
                        select(AuthMfaRecoveryCode).where(
                            AuthMfaRecoveryCode.factor_id == factor.id
                        )
                    )
                ).all()
            )
            auth_session = await session.get(AuthSession, session_id)
            assert enrollment.secret.encode() not in factor.secret_ciphertext
            assert all(code not in {stored.code_hash for stored in stored_codes} for code in recovery_codes)
            assert auth_session.mfa_satisfied_at is not None

        await runtime.service.verify(
            user_id=user_id,
            session_id=session_id,
            code=None,
            recovery_code=recovery_codes[0],
        )
        with pytest.raises(InvalidMfaCredentialError):
            await runtime.service.verify(
                user_id=user_id,
                session_id=session_id,
                code=None,
                recovery_code=recovery_codes[0],
            )
    finally:
        async with session_factory() as session:
            await session.execute(delete(IdentityUser).where(IdentityUser.id == user_id))
            await session.commit()
        await redis.aclose()
        await engine.dispose()
