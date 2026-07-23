from __future__ import annotations

import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from processual_api.auth.delivery_crypto import (
    DeliveryPayloadCipher,
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
    IdentityUser,
    IdentityUserEmailAddress,
)

DATABASE_URL = os.environ.get(
    "AUTH_R5B_INTEGRATION_DATABASE_URL",
    "",
)

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason=(
        "Set AUTH_R5B_INTEGRATION_DATABASE_URL "
        "to run the PostgreSQL gate."
    ),
)


class RecordingProvider:
    def __init__(self) -> None:
        self.calls = []

    async def send_verification_email(
        self,
        **values,
    ) -> None:
        self.calls.append(values)
        await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_recovery_event_targets_pending_recovery_email():
    database_url = DATABASE_URL.replace(
        "postgresql://",
        "postgresql+asyncpg://",
        1,
    )
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    now = datetime.now(UTC)
    suffix = uuid.uuid4().hex
    user_id = uuid.uuid4()
    recovery_id = uuid.uuid4()
    action_token_id = uuid.uuid4()
    outbox_id = uuid.uuid4()

    primary_email = (
        f"primary-{suffix}@example.test"
    )
    recovery_email = (
        f"recovery-{suffix}@example.test"
    )

    cipher = DeliveryPayloadCipher(
        current_key_version="integration-v1",
        keys={"integration-v1": b"k" * 32},
    )
    encrypted = cipher.encrypt(
        "integration-recovery-token",
        outbox_id=str(outbox_id),
        user_id=str(user_id),
        action_token_id=str(action_token_id),
        purpose="verify_recovery_email",
    )

    provider = RecordingProvider()

    async with session_factory() as session:
        user = IdentityUser(
            id=user_id,
            email_normalized=primary_email,
            display_name="Recovery Delivery",
            password_hash="integration-password-hash",
            status="active",
            email_verified_at=now,
        )
        recovery = IdentityUserEmailAddress(
            id=recovery_id,
            user_id=user_id,
            email_normalized=recovery_email,
            purpose="recovery",
            status="pending",
            user=user,
        )
        action_token = AuthActionToken(
            id=action_token_id,
            user_id=user_id,
            purpose="verify_recovery_email",
            token_hash=f"recovery-{suffix}",
            expires_at=now + timedelta(hours=1),
            user=user,
        )
        outbox = AuthDeliveryOutbox(
            id=outbox_id,
            user_id=user_id,
            action_token_id=action_token_id,
            event_type="verify_recovery_email",
            payload_ciphertext=encrypted.ciphertext,
            payload_key_version=encrypted.key_version,
            available_at=now,
            attempt_count=0,
            user=user,
            action_token=action_token,
        )

        session.add_all(
            [
                user,
                recovery,
                action_token,
                outbox,
            ]
        )
        await session.commit()

    try:
        dispatcher = DeliveryDispatcher(
            repository=SqlAlchemyDeliveryRepository(
                session_factory
            ),
            provider=provider,
            cipher=cipher,
            config=DeliveryDispatcherConfig(
                public_base_url=(
                    "https://accounts.example.test"
                ),
                batch_size=1,
                lease_timeout=timedelta(minutes=5),
                max_attempts=3,
                retry_base=timedelta(seconds=30),
                retry_max=timedelta(minutes=10),
            ),
            clock=lambda: now,
        )

        result = await dispatcher.dispatch_once()

        assert result.claimed == 1
        assert result.delivered == 1
        assert result.dead_lettered == 0
        assert len(provider.calls) == 1
        assert provider.calls[0]["recipient"] == recovery_email
        assert provider.calls[0]["recipient"] != primary_email
        assert provider.calls[0]["template"] == (
            "verify_recovery_email"
        )
        assert provider.calls[0][
            "verification_url"
        ].startswith(
            "https://accounts.example.test/"
            "auth/recovery-email/verify?token="
        )

        async with session_factory() as session:
            persisted = await session.scalar(
                select(AuthDeliveryOutbox).where(
                    AuthDeliveryOutbox.id == outbox_id
                )
            )

            assert persisted is not None
            assert persisted.delivered_at == now
            assert persisted.attempt_count == 1
            assert persisted.claim_id is None
            assert persisted.claimed_at is None
    finally:
        async with session_factory() as session:
            await session.execute(
                delete(IdentityUser).where(
                    IdentityUser.id == user_id
                )
            )
            await session.commit()

        await engine.dispose()
