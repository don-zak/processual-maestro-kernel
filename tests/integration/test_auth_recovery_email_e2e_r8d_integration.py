from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from processual_api.auth.delivery_crypto import (
    DeliveryPayloadCipher,
    EncryptedDeliveryPayload,
)
from processual_api.auth.delivery_dispatcher import (
    DeliveryDispatcher,
    DeliveryDispatcherConfig,
)
from processual_api.auth.delivery_repository import (
    SqlAlchemyDeliveryRepository,
)
from processual_api.auth.models import (
    AuthActionToken,
    AuthDeliveryOutbox,
    AuthSession,
    IdentityPlatformAuthority,
    IdentityUser,
    IdentityUserEmailAddress,
)
from processual_api.auth.rate_limit import (
    AuthRateLimitDecision,
)
from processual_api.auth.recovery_email_router import (
    get_recovery_email_runtime,
    platform_admin_step_up_dependency,
    router,
)
from processual_api.auth.recovery_email_runtime import (
    RecoveryEmailRuntime,
)
from processual_api.auth.recovery_email_verification_repository import (
    SqlAlchemyRecoveryEmailVerificationUnitOfWork,
)
from processual_api.auth.recovery_email_verification_service import (
    RecoveryEmailVerificationService,
)
from processual_api.auth.token_material import TokenDigester

DATABASE_URL = os.environ.get(
    "AUTH_R5B_INTEGRATION_DATABASE_URL",
    "",
)

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason=(
        "Set AUTH_R5B_INTEGRATION_DATABASE_URL "
        "to run the recovery-email E2E gate."
    ),
)

NOW = datetime(2026, 7, 23, 14, tzinfo=UTC)


class AllowingRateLimiter:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def consume(self, **values):
        self.calls.append(values)

        return AuthRateLimitDecision(
            allowed=True,
            retry_after_seconds=0,
            remaining=100,
        )


class UntrustedProxyPolicy:
    max_forwarded_hops = 1

    def is_trusted(self, peer) -> bool:
        return False


class RecordingProvider:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def send_verification_email(
        self,
        **values,
    ) -> None:
        self.calls.append(values)


def _async_database_url() -> str:
    return DATABASE_URL.replace(
        "postgresql://",
        "postgresql+asyncpg://",
        1,
    )


def _decrypt_outbox_token(
    *,
    cipher: DeliveryPayloadCipher,
    outbox: AuthDeliveryOutbox,
) -> str:
    return cipher.decrypt(
        EncryptedDeliveryPayload(
            ciphertext=bytes(
                outbox.payload_ciphertext
            ),
            key_version=outbox.payload_key_version,
        ),
        outbox_id=str(outbox.id),
        user_id=str(outbox.user_id),
        action_token_id=str(
            outbox.action_token_id
        ),
        purpose="verify_recovery_email",
    )


@pytest.mark.asyncio
async def test_recovery_email_full_operational_lifecycle():
    engine = create_async_engine(
        _async_database_url()
    )
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    suffix = uuid.uuid4().hex
    user_id = uuid.uuid4()
    recovery_email_id = uuid.uuid4()
    authority_id = uuid.uuid4()
    session_id = uuid.uuid4()

    primary_email = (
        f"primary-{suffix}@example.test"
    )
    recovery_email_value = (
        f"recovery-{suffix}@example.test"
    )

    cipher = DeliveryPayloadCipher(
        current_key_version="e2e-v1",
        keys={"e2e-v1": b"k" * 32},
    )
    token_digester = TokenDigester(b"p" * 32)

    def unit_of_work_factory():
        return (
            SqlAlchemyRecoveryEmailVerificationUnitOfWork(
                session_factory
            )
        )

    service = RecoveryEmailVerificationService(
        unit_of_work_factory=unit_of_work_factory,
        token_digester=token_digester,
        delivery_cipher=cipher,
        clock=lambda: NOW,
        token_ttl=timedelta(hours=1),
    )

    rate_limiter = AllowingRateLimiter()

    runtime = RecoveryEmailRuntime(
        service=service,
        rate_limiter=rate_limiter,
        proxy_policy=UntrustedProxyPolicy(),
        minimum_response_seconds=0,
    )

    app = FastAPI()
    app.include_router(router)

    app.dependency_overrides[
        get_recovery_email_runtime
    ] = lambda: runtime

    app.dependency_overrides[
        platform_admin_step_up_dependency
    ] = lambda: {
        "user_id": str(user_id),
        "session_id": str(session_id),
        "session_type": "identity_user",
        "platform_authorities": [
            "platform_admin"
        ],
    }

    async with session_factory() as session:
        user = IdentityUser(
            id=user_id,
            email_normalized=primary_email,
            display_name="Recovery E2E Administrator",
            password_hash="e2e-password-hash",
            status="active",
            email_verified_at=NOW,
        )

        recovery_email = IdentityUserEmailAddress(
            id=recovery_email_id,
            user_id=user_id,
            email_normalized=recovery_email_value,
            purpose="recovery",
            status="pending",
        )

        authority = IdentityPlatformAuthority(
            id=authority_id,
            user_id=user_id,
            authority="platform_admin",
            status="active",
            granted_by_user_id=None,
            grant_reason="AUTH-R8D E2E qualification",
            granted_at=NOW,
        )

        auth_session = AuthSession(
            id=session_id,
            user_id=user_id,
            organization_id=None,
            refresh_family_id=uuid.uuid4(),
            authenticated_at=NOW,
            mfa_satisfied_at=(
                NOW - timedelta(seconds=30)
            ),
            last_seen_at=NOW,
            expires_at=NOW + timedelta(hours=1),
            revoked_at=None,
            revoke_reason=None,
        )

        session.add_all(
            [
                user,
                recovery_email,
                authority,
                auth_session,
            ]
        )
        await session.commit()

    try:
        transport = httpx.ASGITransport(
            app=app,
            client=("198.51.100.7", 50000),
        )

        async with httpx.AsyncClient(
            transport=transport,
            base_url="https://testserver",
        ) as client:
            issue_response = await client.post(
                "/auth/recovery-email/verification"
            )

            assert issue_response.status_code == 202
            assert issue_response.json() == {
                "status": "accepted",
                "next_action": (
                    "check_recovery_email"
                ),
            }
            assert "access_token" not in issue_response.text
            assert "refresh_token" not in issue_response.text

            async with session_factory() as session:
                first_token = await session.scalar(
                    select(AuthActionToken)
                    .where(
                        AuthActionToken.user_id
                        == user_id,
                        AuthActionToken.purpose
                        == "verify_recovery_email",
                    )
                )

                assert first_token is not None

                first_outbox = await session.scalar(
                    select(AuthDeliveryOutbox)
                    .where(
                        AuthDeliveryOutbox.action_token_id
                        == first_token.id
                    )
                )

                assert first_outbox is not None
                assert first_token.consumed_at is None
                assert (
                    first_outbox.event_type
                    == "verify_recovery_email"
                )
                assert first_outbox.delivered_at is None

                first_raw_token = (
                    _decrypt_outbox_token(
                        cipher=cipher,
                        outbox=first_outbox,
                    )
                )

                assert first_raw_token
                assert (
                    first_raw_token
                    != first_token.token_hash
                )
                assert (
                    first_raw_token.encode()
                    != bytes(
                        first_outbox.payload_ciphertext
                    )
                )

                first_token_id = first_token.id
                first_outbox_id = first_outbox.id

            resend_response = await client.post(
                "/auth/recovery-email/resend"
            )

            assert resend_response.status_code == 202
            assert resend_response.json() == (
                issue_response.json()
            )

            async with session_factory() as session:
                tokens = list(
                    (
                        await session.scalars(
                            select(AuthActionToken)
                            .where(
                                AuthActionToken.user_id
                                == user_id,
                                AuthActionToken.purpose
                                == "verify_recovery_email",
                            )
                        )
                    ).all()
                )

                assert len(tokens) == 2

                persisted_first = next(
                    token
                    for token in tokens
                    if token.id == first_token_id
                )
                second_token = next(
                    token
                    for token in tokens
                    if token.id != first_token_id
                )

                assert persisted_first.consumed_at == NOW
                assert second_token.consumed_at is None

                second_outbox = await session.scalar(
                    select(AuthDeliveryOutbox)
                    .where(
                        AuthDeliveryOutbox.action_token_id
                        == second_token.id
                    )
                )

                assert second_outbox is not None
                assert second_outbox.id != first_outbox_id

                second_raw_token = (
                    _decrypt_outbox_token(
                        cipher=cipher,
                        outbox=second_outbox,
                    )
                )

                assert second_raw_token
                assert (
                    second_raw_token
                    != first_raw_token
                )
                assert (
                    second_raw_token
                    != second_token.token_hash
                )

                second_token_id = second_token.id
                second_outbox_id = second_outbox.id

            provider = RecordingProvider()

            dispatcher = DeliveryDispatcher(
                repository=(
                    SqlAlchemyDeliveryRepository(
                        session_factory
                    )
                ),
                provider=provider,
                cipher=cipher,
                config=DeliveryDispatcherConfig(
                    public_base_url=(
                        "https://accounts.example.test"
                    ),
                    batch_size=10,
                    lease_timeout=timedelta(
                        minutes=5
                    ),
                    max_attempts=3,
                    retry_base=timedelta(
                        seconds=30
                    ),
                    retry_max=timedelta(
                        minutes=10
                    ),
                ),
                clock=lambda: NOW,
            )

            dispatch_result = (
                await dispatcher.dispatch_once()
            )

            assert dispatch_result.claimed == 2
            assert dispatch_result.delivered == 1
            assert dispatch_result.dead_lettered == 1
            assert dispatch_result.retry_scheduled == 0

            assert len(provider.calls) == 1
            assert provider.calls[0]["recipient"] == (
                recovery_email_value
            )
            assert provider.calls[0]["recipient"] != (
                primary_email
            )
            assert provider.calls[0]["template"] == (
                "verify_recovery_email"
            )
            assert provider.calls[0][
                "verification_url"
            ].startswith(
                "https://accounts.example.test/"
                "auth/recovery-email/verify?token="
            )
            assert second_raw_token in (
                provider.calls[0][
                    "verification_url"
                ]
            )
            assert first_raw_token not in (
                provider.calls[0][
                    "verification_url"
                ]
            )

            async with session_factory() as session:
                first_outbox_after_dispatch = (
                    await session.get(
                        AuthDeliveryOutbox,
                        first_outbox_id,
                    )
                )
                second_outbox_after_dispatch = (
                    await session.get(
                        AuthDeliveryOutbox,
                        second_outbox_id,
                    )
                )

                assert (
                    first_outbox_after_dispatch
                    is not None
                )
                assert (
                    second_outbox_after_dispatch
                    is not None
                )
                assert (
                    first_outbox_after_dispatch
                    .dead_lettered_at
                    == NOW
                )
                assert (
                    first_outbox_after_dispatch
                    .last_error_code
                    == "action_token_consumed"
                )
                assert (
                    second_outbox_after_dispatch
                    .delivered_at
                    == NOW
                )
                assert (
                    second_outbox_after_dispatch
                    .dead_lettered_at
                    is None
                )

            session_count_before_verify = None

            async with session_factory() as session:
                session_count_before_verify = (
                    await session.scalar(
                        select(func.count())
                        .select_from(AuthSession)
                        .where(
                            AuthSession.user_id
                            == user_id
                        )
                    )
                )

            assert session_count_before_verify == 1

            verify_response = await client.post(
                "/auth/recovery-email/verify",
                json={"token": second_raw_token},
            )

            assert verify_response.status_code == 200
            assert verify_response.json() == {
                "status": "processed"
            }
            assert (
                verify_response.headers[
                    "cache-control"
                ]
                == "no-store"
            )
            assert "access_token" not in verify_response.text
            assert "refresh_token" not in verify_response.text

            replay_response = await client.post(
                "/auth/recovery-email/verify",
                json={"token": second_raw_token},
            )

            assert replay_response.status_code == 200
            assert replay_response.json() == (
                verify_response.json()
            )
            assert "access_token" not in replay_response.text
            assert "refresh_token" not in replay_response.text

            async with session_factory() as session:
                persisted_user = await session.get(
                    IdentityUser,
                    user_id,
                )
                persisted_recovery = await session.get(
                    IdentityUserEmailAddress,
                    recovery_email_id,
                )
                persisted_authority = await session.get(
                    IdentityPlatformAuthority,
                    authority_id,
                )
                persisted_session = await session.get(
                    AuthSession,
                    session_id,
                )
                persisted_second_token = (
                    await session.get(
                        AuthActionToken,
                        second_token_id,
                    )
                )

                session_count_after_verify = (
                    await session.scalar(
                        select(func.count())
                        .select_from(AuthSession)
                        .where(
                            AuthSession.user_id
                            == user_id
                        )
                    )
                )

                assert persisted_user is not None
                assert persisted_recovery is not None
                assert persisted_authority is not None
                assert persisted_session is not None
                assert persisted_second_token is not None

                assert (
                    persisted_user.email_normalized
                    == primary_email
                )
                assert (
                    persisted_recovery.email_normalized
                    == recovery_email_value
                )
                assert (
                    persisted_recovery.status
                    == "verified"
                )
                assert (
                    persisted_recovery.verified_at
                    == NOW
                )
                assert (
                    persisted_recovery.revoked_at
                    is None
                )
                assert (
                    persisted_second_token.consumed_at
                    == NOW
                )
                assert (
                    persisted_authority.authority
                    == "platform_admin"
                )
                assert (
                    persisted_authority.status
                    == "active"
                )
                assert (
                    persisted_authority.revoked_at
                    is None
                )
                assert (
                    persisted_session.mfa_satisfied_at
                    == NOW - timedelta(seconds=30)
                )
                assert persisted_session.revoked_at is None
                assert session_count_after_verify == 1

            assert rate_limiter.calls
            assert {
                call["action"]
                for call in rate_limiter.calls
            } == {
                "recovery_email_issue",
                "recovery_email_verify",
            }

    finally:
        app.dependency_overrides.clear()

        async with session_factory() as session:
            await session.execute(
                delete(IdentityUser).where(
                    IdentityUser.id == user_id
                )
            )
            await session.commit()

        await engine.dispose()
