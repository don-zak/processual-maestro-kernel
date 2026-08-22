from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from processual_api.auth.account_recovery_external_revocation import (
    AccountRecoveryExternalAuthorityRevoker,
)
from processual_api.auth.account_recovery_repository import (
    SqlAlchemyAccountRecoveryUnitOfWork,
)
from processual_api.auth.account_recovery_router import (
    get_account_recovery_runtime,
    router,
)
from processual_api.auth.account_recovery_runtime import AccountRecoveryRuntime
from processual_api.auth.account_recovery_service import AccountRecoveryService
from processual_api.auth.delivery_crypto import (
    DeliveryPayloadCipher,
    EncryptedDeliveryPayload,
)
from processual_api.auth.models import (
    AuthAccountRecoveryRequest,
    AuthActionToken,
    AuthDeliveryOutbox,
    AuthMfaFactor,
    AuthMfaRecoveryCode,
    AuthRefreshToken,
    AuthSession,
    IdentityPlatformAuthority,
    IdentityUser,
    IdentityUserEmailAddress,
)
from processual_api.auth.passwords import PasswordService
from processual_api.auth.rate_limit import RedisAuthRateLimiter, TrustedProxyPolicy
from processual_api.auth.token_material import TokenDigester
from processual_api.supervisor_session_keys import (
    issue_supervisor_session_key,
    validate_supervisor_session_key,
)

DATABASE_URL = os.environ.get("AUTH_R9C_INTEGRATION_DATABASE_URL", "")
REDIS_URL = os.environ.get("AUTH_R9C_INTEGRATION_REDIS_URL", "")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL or not REDIS_URL,
    reason=(
        "Set AUTH_R9C_INTEGRATION_DATABASE_URL and "
        "AUTH_R9C_INTEGRATION_REDIS_URL to run the R9C gate."
    ),
)

NOW = datetime(2026, 8, 22, 12, 30, tzinfo=UTC)
OLD_PASSWORD = "Old-Password-2026!"
NEW_PASSWORD = "New-Password-2026!"


def _async_database_url() -> str:
    if DATABASE_URL.startswith("postgresql+asyncpg://"):
        return DATABASE_URL
    return DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)


def _decrypt_verification_token(
    *,
    cipher: DeliveryPayloadCipher,
    outbox: AuthDeliveryOutbox,
) -> str:
    return cipher.decrypt(
        EncryptedDeliveryPayload(
            ciphertext=bytes(outbox.payload_ciphertext),
            key_version=outbox.payload_key_version,
        ),
        outbox_id=str(outbox.id),
        user_id=str(outbox.user_id),
        account_recovery_request_id=str(outbox.account_recovery_request_id),
        purpose="account_recovery_verification",
    )


@pytest.mark.asyncio
async def test_account_recovery_http_postgres_redis_revokes_all_authority(tmp_path) -> None:
    engine = create_async_engine(_async_database_url())
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    redis = Redis.from_url(REDIS_URL, decode_responses=False)

    suffix = uuid.uuid4().hex
    user_id = uuid.uuid4()
    recovery_email_id = uuid.uuid4()
    session_id = uuid.uuid4()
    refresh_id = uuid.uuid4()
    action_token_id = uuid.uuid4()
    factor_id = uuid.uuid4()
    recovery_code_id = uuid.uuid4()
    primary_email = f"r9c-primary-{suffix}@example.test"
    recovery_email = f"r9c-recovery-{suffix}@example.test"
    client_ip = f"2001:db8::{suffix[:8]}"
    rate_prefix = f"rl:auth:r9c:{suffix}"

    password_service = PasswordService()
    old_hash = password_service.hash_password(OLD_PASSWORD)
    cipher = DeliveryPayloadCipher(
        current_key_version="r9c-v1",
        keys={"r9c-v1": b"k" * 32},
    )
    digester = TokenDigester(b"p" * 32)

    supervisor_path = tmp_path / "supervisor-session-keys.json"
    supervisor = issue_supervisor_session_key(
        supervisor_path,
        {
            "email": "owner@example.test",
            "supervision_level": "owner_supervisor",
        },
        {
            "level": "operations_supervisor",
            "issued_to": primary_email,
            "session_label": "R9C recovery target",
            "reason": "R9C qualification",
            "expires_at": "",
        },
    )
    external_settings = {
        "api_keys": [
            {
                "id": f"api-{suffix}",
                "user_id": str(user_id),
                "status": "enabled",
                "revoked_at": None,
            }
        ]
    }

    def settings_loader(value: str):
        assert value == str(user_id)
        return external_settings

    def settings_saver(value: str, raw: dict):
        assert value == str(user_id)
        external_settings.clear()
        external_settings.update(raw)

    external_revoker = AccountRecoveryExternalAuthorityRevoker(
        supervisor_store_path=supervisor_path,
        settings_loader=settings_loader,
        settings_saver=settings_saver,
        clock=lambda: NOW,
    )

    def uow_factory() -> SqlAlchemyAccountRecoveryUnitOfWork:
        return SqlAlchemyAccountRecoveryUnitOfWork(session_factory)

    runtime = AccountRecoveryRuntime(
        service=AccountRecoveryService(
            unit_of_work_factory=uow_factory,
            token_digester=digester,
            delivery_cipher=cipher,
            password_service=password_service,
            external_authority_revoker=external_revoker,
            clock=lambda: NOW,
        ),
        rate_limiter=RedisAuthRateLimiter(
            redis,
            pepper=b"r" * 32,
            key_prefix=rate_prefix,
        ),
        proxy_policy=TrustedProxyPolicy.from_cidrs((), max_forwarded_hops=1),
        minimum_response_seconds=0,
    )

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_account_recovery_runtime] = lambda: runtime

    async with session_factory() as session:
        session.add(
            IdentityUser(
                id=user_id,
                email_normalized=primary_email,
                display_name="R9C Recovery User",
                password_hash=old_hash,
                status="active",
                email_verified_at=NOW - timedelta(days=30),
                failed_login_count=2,
                locked_until=NOW + timedelta(minutes=10),
            )
        )
        await session.flush()
        session.add(
            IdentityUserEmailAddress(
                id=recovery_email_id,
                user_id=user_id,
                email_normalized=recovery_email,
                purpose="recovery",
                status="verified",
                verified_at=NOW - timedelta(days=20),
                revoked_at=None,
            )
        )
        session.add(
            AuthSession(
                id=session_id,
                user_id=user_id,
                organization_id=None,
                refresh_family_id=uuid.uuid4(),
                authenticated_at=NOW - timedelta(hours=1),
                mfa_satisfied_at=NOW - timedelta(minutes=20),
                last_seen_at=NOW - timedelta(minutes=1),
                expires_at=NOW + timedelta(hours=8),
                revoked_at=None,
                revoke_reason=None,
            )
        )
        session.add(
            AuthActionToken(
                id=action_token_id,
                user_id=user_id,
                purpose="reset_password",
                token_hash=f"action-{suffix}",
                expires_at=NOW + timedelta(hours=1),
                consumed_at=None,
                invalidated_at=None,
            )
        )
        session.add(
            AuthMfaFactor(
                id=factor_id,
                user_id=user_id,
                factor_type="totp",
                label="Authenticator",
                status="active",
                secret_ciphertext=b"encrypted-r9c-test-secret",
                secret_key_version="r9c-test",
                verified_at=NOW - timedelta(days=10),
                last_used_step=123,
                disabled_at=None,
            )
        )
        await session.flush()
        session.add(
            AuthRefreshToken(
                id=refresh_id,
                session_id=session_id,
                parent_token_id=None,
                token_hash=f"refresh-{suffix}",
                issued_at=NOW - timedelta(hours=1),
                expires_at=NOW + timedelta(days=7),
                consumed_at=None,
                revoked_at=None,
                reuse_detected_at=None,
            )
        )
        session.add(
            AuthMfaRecoveryCode(
                id=recovery_code_id,
                factor_id=factor_id,
                code_hash=f"recovery-code-{suffix}",
                used_at=None,
            )
        )
        await session.commit()

    try:
        transport = httpx.ASGITransport(
            app=app,
            client=(client_ip, 50123),
        )
        async with httpx.AsyncClient(
            transport=transport,
            base_url="https://testserver",
        ) as client:
            start = await client.post(
                "/auth/account-recovery/start",
                json={"login": primary_email},
            )
            assert start.status_code == 202
            assert start.json() == {
                "status": "accepted",
                "next_action": "check_recovery_email",
            }
            assert start.headers["cache-control"] == "no-store"

            async with session_factory() as session:
                recovery_request = await session.scalar(
                    select(AuthAccountRecoveryRequest).where(
                        AuthAccountRecoveryRequest.user_id == user_id,
                        AuthAccountRecoveryRequest.state == "pending",
                    )
                )
                assert recovery_request is not None
                outbox = await session.scalar(
                    select(AuthDeliveryOutbox).where(
                        AuthDeliveryOutbox.account_recovery_request_id
                        == recovery_request.id
                    )
                )
                assert outbox is not None
                raw_verification_token = _decrypt_verification_token(
                    cipher=cipher,
                    outbox=outbox,
                )
                assert raw_verification_token
                assert raw_verification_token != recovery_request.verification_token_hash
                request_id = recovery_request.id

            verify = await client.post(
                "/auth/account-recovery/verify",
                json={
                    "request_id": str(request_id),
                    "token": raw_verification_token,
                },
            )
            assert verify.status_code == 200
            verify_body = verify.json()
            assert verify_body["status"] == "verified"
            assert verify_body["password_change_required"] is True
            assert verify_body["mfa_reenrollment_required"] is True
            assert verify_body["session_created"] is False
            assert verify_body["access_token_issued"] is False
            assert verify_body["refresh_token_issued"] is False
            assert verify.headers["cache-control"] == "no-store"
            completion_token = verify_body["completion_token"]

            verify_replay = await client.post(
                "/auth/account-recovery/verify",
                json={
                    "request_id": str(request_id),
                    "token": raw_verification_token,
                },
            )
            assert verify_replay.status_code == 400

            complete = await client.post(
                "/auth/account-recovery/complete",
                json={
                    "request_id": str(request_id),
                    "completion_token": completion_token,
                    "new_password": NEW_PASSWORD,
                    "confirm_password": NEW_PASSWORD,
                },
            )
            assert complete.status_code == 200
            complete_body = complete.json()
            assert complete_body["status"] == "completed"
            assert complete_body["password_changed"] is True
            assert complete_body["mfa_reenrollment_required"] is True
            assert complete_body["session_created"] is False
            assert complete_body["access_token_issued"] is False
            assert complete_body["refresh_token_issued"] is False
            assert complete_body["api_key_issued"] is False
            assert complete_body["authority_granted"] is False
            assert complete_body["revocations"]["sessions_revoked"] == 1
            assert complete_body["revocations"]["refresh_tokens_revoked"] == 1
            assert complete_body["revocations"]["action_tokens_revoked"] >= 1
            assert complete_body["revocations"]["supervisor_session_keys_revoked"] == 1
            assert complete_body["revocations"]["api_keys_revoked"] == 1
            assert complete.headers["cache-control"] == "no-store"

            complete_replay = await client.post(
                "/auth/account-recovery/complete",
                json={
                    "request_id": str(request_id),
                    "completion_token": completion_token,
                    "new_password": NEW_PASSWORD,
                    "confirm_password": NEW_PASSWORD,
                },
            )
            assert complete_replay.status_code == 400

        async with session_factory() as session:
            user = await session.get(IdentityUser, user_id)
            auth_session = await session.get(AuthSession, session_id)
            refresh = await session.get(AuthRefreshToken, refresh_id)
            action = await session.get(AuthActionToken, action_token_id)
            factor = await session.get(AuthMfaFactor, factor_id)
            request = await session.get(AuthAccountRecoveryRequest, request_id)
            recovery_code_count = await session.scalar(
                select(func.count())
                .select_from(AuthMfaRecoveryCode)
                .where(AuthMfaRecoveryCode.factor_id == factor_id)
            )
            authority_count = await session.scalar(
                select(func.count())
                .select_from(IdentityPlatformAuthority)
                .where(IdentityPlatformAuthority.user_id == user_id)
            )

            assert user is not None
            assert password_service.verify_password(user.password_hash, OLD_PASSWORD).valid is False
            assert password_service.verify_password(user.password_hash, NEW_PASSWORD).valid is True
            assert user.password_changed_at == NOW
            assert user.failed_login_count == 0
            assert user.locked_until is None
            assert auth_session is not None and auth_session.revoked_at == NOW
            assert auth_session.revoke_reason == "account_recovery_completed"
            assert refresh is not None and refresh.revoked_at == NOW
            assert action is not None and action.invalidated_at == NOW
            assert factor is not None and factor.status == "disabled"
            assert factor.disabled_at == NOW
            assert recovery_code_count == 0
            assert request is not None and request.state == "completed"
            assert request.completed_at == NOW
            assert request.completion_token_hash is None
            assert authority_count == 0

        assert external_settings["api_keys"][0]["status"] == "revoked"
        assert external_settings["api_keys"][0]["revoked_at"] == NOW.isoformat()
        with pytest.raises(PermissionError, match="revoked"):
            validate_supervisor_session_key(
                supervisor_path,
                supervisor["raw_key"],
            )
    finally:
        app.dependency_overrides.clear()
        async for key in redis.scan_iter(match=f"{rate_prefix}:*"):
            await redis.delete(key)
        await redis.aclose()
        async with session_factory() as session:
            await session.execute(delete(IdentityUser).where(IdentityUser.id == user_id))
            await session.commit()
        await engine.dispose()
