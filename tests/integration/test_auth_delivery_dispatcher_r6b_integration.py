from __future__ import annotations

import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from processual_api.auth.delivery_crypto import DeliveryPayloadCipher
from processual_api.auth.delivery_dispatcher import (
    DeliveryDispatcher,
    DeliveryDispatcherConfig,
)
from processual_api.auth.delivery_repository import SqlAlchemyDeliveryRepository
from processual_api.auth.models import AuthActionToken, AuthDeliveryOutbox, IdentityUser

DATABASE_URL = os.environ.get("AUTH_R5B_INTEGRATION_DATABASE_URL", "")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="Set AUTH_R5B_INTEGRATION_DATABASE_URL to run the R6B PostgreSQL gate.",
)


class RecordingProvider:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    async def send_verification_email(self, **values: str) -> None:
        self.calls.append(values)
        await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_concurrent_dispatchers_claim_once_and_finalize_with_real_postgresql():
    database_url = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(UTC)
    suffix = uuid.uuid4().hex
    user_id = uuid.uuid4()
    action_token_id = uuid.uuid4()
    outbox_id = uuid.uuid4()
    cipher = DeliveryPayloadCipher(current_key_version="integration-v1", keys={"integration-v1": b"k" * 32})
    encrypted = cipher.encrypt(
        "integration-verification-token",
        outbox_id=str(outbox_id),
        user_id=str(user_id),
        action_token_id=str(action_token_id),
        purpose="verify_email",
    )
    provider = RecordingProvider()
    config = DeliveryDispatcherConfig(
        public_base_url="https://accounts.example.test",
        batch_size=1,
        lease_timeout=timedelta(minutes=5),
        max_attempts=3,
        retry_base=timedelta(seconds=30),
        retry_max=timedelta(minutes=10),
    )

    async with session_factory() as session:
        user = IdentityUser(
            id=user_id,
            email_normalized=f"auth-r6b-{suffix}@example.test",
            display_name="R6B Integration",
            password_hash="integration-only-password-hash",
            status="pending_verification",
        )
        action_token = AuthActionToken(
            id=action_token_id,
            user_id=user_id,
            purpose="verify_email",
            token_hash=f"integration-{suffix}",
            expires_at=now + timedelta(hours=1),
            user=user,
        )
        session.add_all(
            [
                user,
                action_token,
                AuthDeliveryOutbox(
                    id=outbox_id,
                    user_id=user_id,
                    action_token_id=action_token_id,
                    event_type="verify_email",
                    payload_ciphertext=encrypted.ciphertext,
                    payload_key_version=encrypted.key_version,
                    available_at=now,
                    attempt_count=0,
                    user=user,
                    action_token=action_token,
                ),
            ]
        )
        await session.commit()

    try:
        dispatchers = [
            DeliveryDispatcher(
                repository=SqlAlchemyDeliveryRepository(session_factory),
                provider=provider,
                cipher=cipher,
                config=config,
                clock=lambda: now,
            )
            for _ in range(2)
        ]
        results = await asyncio.gather(*(dispatcher.dispatch_once() for dispatcher in dispatchers))

        assert sum(result.claimed for result in results) == 1
        assert sum(result.delivered for result in results) == 1
        assert len(provider.calls) == 1
        assert provider.calls[0]["idempotency_key"] == f"pmk-auth-delivery-v1:{outbox_id}"

        async with session_factory() as session:
            persisted = await session.scalar(
                select(AuthDeliveryOutbox).where(AuthDeliveryOutbox.id == outbox_id)
            )
            assert persisted is not None
            assert persisted.attempt_count == 1
            assert persisted.delivered_at == now
            assert persisted.claim_id is None
            assert persisted.claimed_at is None
    finally:
        async with session_factory() as session:
            await session.execute(delete(IdentityUser).where(IdentityUser.id == user_id))
            await session.commit()
        await engine.dispose()
