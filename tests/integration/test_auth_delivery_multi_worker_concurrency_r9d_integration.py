from __future__ import annotations

import asyncio
import os
import uuid
from collections import Counter
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from processual_api.auth.delivery_crypto import DeliveryPayloadCipher
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
)

DATABASE_URL = os.environ.get(
    "AUTH_R5B_INTEGRATION_DATABASE_URL",
    "",
)

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason=(
        "Set AUTH_R5B_INTEGRATION_DATABASE_URL "
        "to run the AUTH-R9D PostgreSQL concurrency gate."
    ),
)

KEY_VERSION = "auth-r9d-integration-v1"
KEY_BYTES = b"r" * 32
PUBLIC_BASE_URL = "https://accounts.example.test"


class RecordingProvider:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []
        self._lock = asyncio.Lock()

    async def send_verification_email(
        self,
        **values: str,
    ) -> None:
        async with self._lock:
            self.calls.append(dict(values))

        await asyncio.sleep(0)


def _async_database_url() -> str:
    return DATABASE_URL.replace(
        "postgresql://",
        "postgresql+asyncpg://",
        1,
    )


def _engine_and_sessions():
    engine = create_async_engine(
        _async_database_url(),
        pool_size=20,
        max_overflow=20,
    )
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )
    return engine, session_factory


def _cipher() -> DeliveryPayloadCipher:
    return DeliveryPayloadCipher(
        current_key_version=KEY_VERSION,
        keys={KEY_VERSION: KEY_BYTES},
    )


def _dispatcher_config(
    *,
    batch_size: int,
    lease_timeout: timedelta,
    max_attempts: int = 5,
) -> DeliveryDispatcherConfig:
    return DeliveryDispatcherConfig(
        public_base_url=PUBLIC_BASE_URL,
        batch_size=batch_size,
        lease_timeout=lease_timeout,
        max_attempts=max_attempts,
        retry_base=timedelta(seconds=30),
        retry_max=timedelta(minutes=10),
    )


async def _seed_delivery_rows(
    session_factory,
    *,
    count: int,
    now: datetime,
    prefix: str,
    attempt_count: int = 0,
    delivered_at: datetime | None = None,
    dead_lettered_at: datetime | None = None,
    last_error_code: str | None = None,
) -> tuple[uuid.UUID, tuple[uuid.UUID, ...]]:
    suffix = uuid.uuid4().hex
    user_id = uuid.uuid4()

    user = IdentityUser(
        id=user_id,
        email_normalized=(
            f"{prefix}-{suffix}@example.test"
        ),
        display_name="AUTH-R9D Integration",
        password_hash="auth-r9d-integration-password-hash",
        status="pending_verification",
    )

    outbox_ids: list[uuid.UUID] = []
    records: list[object] = [user]
    cipher = _cipher()

    for index in range(count):
        action_token_id = uuid.uuid4()
        outbox_id = uuid.uuid4()

        encrypted = cipher.encrypt(
            f"auth-r9d-token-{suffix}-{index}",
            outbox_id=str(outbox_id),
            user_id=str(user_id),
            action_token_id=str(action_token_id),
            purpose="verify_email",
        )

        action_token = AuthActionToken(
            id=action_token_id,
            user_id=user_id,
            purpose="verify_email",
            token_hash=(
                f"auth-r9d-{suffix}-{index}"
            ),
            expires_at=now + timedelta(hours=2),
            user=user,
        )

        outbox = AuthDeliveryOutbox(
            id=outbox_id,
            user_id=user_id,
            action_token_id=action_token_id,
            event_type="verify_email",
            payload_ciphertext=encrypted.ciphertext,
            payload_key_version=encrypted.key_version,
            available_at=now,
            attempt_count=attempt_count,
            delivered_at=delivered_at,
            dead_lettered_at=dead_lettered_at,
            last_error_code=last_error_code,
            user=user,
            action_token=action_token,
        )

        records.extend(
            [
                action_token,
                outbox,
            ]
        )
        outbox_ids.append(outbox_id)

    async with session_factory() as session:
        session.add_all(records)
        await session.commit()

    return user_id, tuple(outbox_ids)


async def _cleanup_user(
    session_factory,
    user_id: uuid.UUID,
) -> None:
    async with session_factory() as session:
        await session.execute(
            delete(IdentityUser).where(
                IdentityUser.id == user_id
            )
        )
        await session.commit()


async def _load_outbox_rows(
    session_factory,
    outbox_ids: tuple[uuid.UUID, ...],
) -> tuple[AuthDeliveryOutbox, ...]:
    async with session_factory() as session:
        rows = (
            await session.scalars(
                select(AuthDeliveryOutbox)
                .where(
                    AuthDeliveryOutbox.id.in_(
                        outbox_ids
                    )
                )
                .order_by(AuthDeliveryOutbox.id)
            )
        ).all()

    return tuple(rows)


@pytest.mark.asyncio
async def test_two_workers_claim_disjoint_batches_with_real_postgresql():
    engine, session_factory = _engine_and_sessions()
    now = datetime.now(UTC)
    user_id, outbox_ids = await _seed_delivery_rows(
        session_factory,
        count=12,
        now=now,
        prefix="auth-r9d-disjoint",
    )

    try:
        repositories = (
            SqlAlchemyDeliveryRepository(
                session_factory
            ),
            SqlAlchemyDeliveryRepository(
                session_factory
            ),
        )

        claimed_a, claimed_b = await asyncio.gather(
            repositories[0].claim_batch(
                now=now,
                lease_timeout=timedelta(minutes=5),
                batch_size=6,
            ),
            repositories[1].claim_batch(
                now=now,
                lease_timeout=timedelta(minutes=5),
                batch_size=6,
            ),
        )

        ids_a = {
            claim.outbox_id
            for claim in claimed_a
        }
        ids_b = {
            claim.outbox_id
            for claim in claimed_b
        }

        assert len(claimed_a) == 6
        assert len(claimed_b) == 6
        assert ids_a.isdisjoint(ids_b)
        assert ids_a | ids_b == set(outbox_ids)

        all_claims = (*claimed_a, *claimed_b)

        assert len(
            {
                claim.claim_id
                for claim in all_claims
            }
        ) == 12

        rows = await _load_outbox_rows(
            session_factory,
            outbox_ids,
        )

        assert len(rows) == 12
        assert all(
            row.claim_id is not None
            for row in rows
        )
        assert all(
            row.claimed_at == now
            for row in rows
        )
        assert all(
            row.attempt_count == 1
            for row in rows
        )
        assert all(
            row.delivered_at is None
            for row in rows
        )
    finally:
        await _cleanup_user(
            session_factory,
            user_id,
        )
        await engine.dispose()


@pytest.mark.asyncio
async def test_expired_lease_reclaim_fences_stale_owner_with_real_postgresql():
    engine, session_factory = _engine_and_sessions()
    now = datetime.now(UTC)
    lease_timeout = timedelta(seconds=60)

    user_id, outbox_ids = await _seed_delivery_rows(
        session_factory,
        count=1,
        now=now,
        prefix="auth-r9d-lease",
    )

    outbox_id = outbox_ids[0]

    try:
        original_repository = (
            SqlAlchemyDeliveryRepository(
                session_factory
            )
        )
        restarted_repository = (
            SqlAlchemyDeliveryRepository(
                session_factory
            )
        )

        original_claims = (
            await original_repository.claim_batch(
                now=now,
                lease_timeout=lease_timeout,
                batch_size=1,
            )
        )

        assert len(original_claims) == 1

        original_claim = original_claims[0]

        pre_expiry_claims = (
            await restarted_repository.claim_batch(
                now=now + timedelta(seconds=30),
                lease_timeout=lease_timeout,
                batch_size=1,
            )
        )

        assert pre_expiry_claims == ()

        reclaim_time = (
            now
            + lease_timeout
            + timedelta(seconds=1)
        )

        reclaimed = (
            await restarted_repository.claim_batch(
                now=reclaim_time,
                lease_timeout=lease_timeout,
                batch_size=1,
            )
        )

        assert len(reclaimed) == 1

        current_claim = reclaimed[0]

        assert current_claim.outbox_id == outbox_id
        assert (
            current_claim.claim_id
            != original_claim.claim_id
        )
        assert original_claim.attempt_count == 1
        assert current_claim.attempt_count == 2

        stale_delivered = (
            await original_repository.mark_delivered(
                outbox_id=outbox_id,
                claim_id=original_claim.claim_id,
                delivered_at=reclaim_time,
            )
        )

        stale_failed = (
            await original_repository.mark_failed(
                outbox_id=outbox_id,
                claim_id=original_claim.claim_id,
                available_at=(
                    reclaim_time
                    + timedelta(minutes=1)
                ),
                error_code="stale-owner",
                dead_lettered_at=None,
            )
        )

        current_delivered = (
            await restarted_repository.mark_delivered(
                outbox_id=outbox_id,
                claim_id=current_claim.claim_id,
                delivered_at=reclaim_time,
            )
        )

        assert stale_delivered is False
        assert stale_failed is False
        assert current_delivered is True

        rows = await _load_outbox_rows(
            session_factory,
            outbox_ids,
        )
        persisted = rows[0]

        assert persisted.attempt_count == 2
        assert persisted.delivered_at == reclaim_time
        assert persisted.claim_id is None
        assert persisted.claimed_at is None
        assert persisted.last_error_code is None
    finally:
        await _cleanup_user(
            session_factory,
            user_id,
        )
        await engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_dispatchers_deliver_each_outbox_once_with_real_postgresql():
    engine, session_factory = _engine_and_sessions()
    now = datetime.now(UTC)

    user_id, outbox_ids = await _seed_delivery_rows(
        session_factory,
        count=11,
        now=now,
        prefix="auth-r9d-dispatch",
    )

    provider = RecordingProvider()
    config = _dispatcher_config(
        batch_size=6,
        lease_timeout=timedelta(minutes=5),
    )

    try:
        dispatchers = tuple(
            DeliveryDispatcher(
                repository=(
                    SqlAlchemyDeliveryRepository(
                        session_factory
                    )
                ),
                provider=provider,
                cipher=_cipher(),
                config=config,
                clock=lambda: now,
            )
            for _ in range(2)
        )

        results = await asyncio.gather(
            *(
                dispatcher.dispatch_once()
                for dispatcher in dispatchers
            )
        )

        assert sum(
            result.claimed
            for result in results
        ) == 11
        assert sum(
            result.delivered
            for result in results
        ) == 11
        assert sum(
            result.retry_scheduled
            for result in results
        ) == 0
        assert sum(
            result.dead_lettered
            for result in results
        ) == 0
        assert sum(
            result.stale_finalization
            for result in results
        ) == 0

        idempotency_keys = [
            call["idempotency_key"]
            for call in provider.calls
        ]

        expected_keys = {
            f"pmk-auth-delivery-v1:{outbox_id}"
            for outbox_id in outbox_ids
        }

        key_counts = Counter(idempotency_keys)

        assert len(provider.calls) == 11
        assert set(idempotency_keys) == expected_keys
        assert all(
            count == 1
            for count in key_counts.values()
        )

        rows = await _load_outbox_rows(
            session_factory,
            outbox_ids,
        )

        assert all(
            row.delivered_at == now
            for row in rows
        )
        assert all(
            row.attempt_count == 1
            for row in rows
        )
        assert all(
            row.claim_id is None
            for row in rows
        )
        assert all(
            row.claimed_at is None
            for row in rows
        )
    finally:
        await _cleanup_user(
            session_factory,
            user_id,
        )
        await engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_redrive_has_exactly_one_winner_with_real_postgresql():
    engine, session_factory = _engine_and_sessions()
    now = datetime.now(UTC)
    redrive_at = now + timedelta(minutes=1)
    dispatch_at = redrive_at + timedelta(seconds=1)

    user_id, outbox_ids = await _seed_delivery_rows(
        session_factory,
        count=1,
        now=now,
        prefix="auth-r9d-redrive",
        attempt_count=2,
        dead_lettered_at=now,
        last_error_code="attempts_exhausted",
    )

    outbox_id = outbox_ids[0]

    try:
        repositories = (
            SqlAlchemyDeliveryRepository(
                session_factory
            ),
            SqlAlchemyDeliveryRepository(
                session_factory
            ),
        )

        redrive_a, redrive_b = await asyncio.gather(
            repositories[0].redrive_dead_letter(
                outbox_id=outbox_id,
                available_at=redrive_at,
            ),
            repositories[1].redrive_dead_letter(
                outbox_id=outbox_id,
                available_at=redrive_at,
            ),
        )

        successful = [
            result
            for result in (redrive_a, redrive_b)
            if result is not None
        ]

        assert len(successful) == 1

        winner = successful[0]

        assert winner.outbox_id == outbox_id
        assert winner.preserved_attempt_count == 2
        assert winner.available_at == redrive_at

        provider = RecordingProvider()
        config = _dispatcher_config(
            batch_size=1,
            lease_timeout=timedelta(minutes=5),
            max_attempts=5,
        )

        dispatchers = tuple(
            DeliveryDispatcher(
                repository=(
                    SqlAlchemyDeliveryRepository(
                        session_factory
                    )
                ),
                provider=provider,
                cipher=_cipher(),
                config=config,
                clock=lambda: dispatch_at,
            )
            for _ in range(2)
        )

        results = await asyncio.gather(
            *(
                dispatcher.dispatch_once()
                for dispatcher in dispatchers
            )
        )

        assert sum(
            result.claimed
            for result in results
        ) == 1
        assert sum(
            result.delivered
            for result in results
        ) == 1
        assert len(provider.calls) == 1
        assert provider.calls[0][
            "idempotency_key"
        ] == (
            f"pmk-auth-delivery-v1:{outbox_id}"
        )

        rows = await _load_outbox_rows(
            session_factory,
            outbox_ids,
        )
        persisted = rows[0]

        assert persisted.attempt_count == 3
        assert persisted.delivered_at == dispatch_at
        assert persisted.dead_lettered_at is None
        assert persisted.last_error_code is None
        assert persisted.claim_id is None
        assert persisted.claimed_at is None
    finally:
        await _cleanup_user(
            session_factory,
            user_id,
        )
        await engine.dispose()


@pytest.mark.asyncio
async def test_interrupted_worker_recovers_after_lease_expiry_with_real_postgresql():
    engine, session_factory = _engine_and_sessions()
    claim_time = datetime.now(UTC)
    lease_timeout = timedelta(seconds=60)
    pre_expiry_time = (
        claim_time
        + timedelta(seconds=30)
    )
    post_expiry_time = (
        claim_time
        + lease_timeout
        + timedelta(seconds=1)
    )

    user_id, outbox_ids = await _seed_delivery_rows(
        session_factory,
        count=4,
        now=claim_time,
        prefix="auth-r9d-restart",
    )

    interrupted_repository = (
        SqlAlchemyDeliveryRepository(
            session_factory
        )
    )

    try:
        abandoned_claims = (
            await interrupted_repository.claim_batch(
                now=claim_time,
                lease_timeout=lease_timeout,
                batch_size=4,
            )
        )

        assert len(abandoned_claims) == 4
        assert {
            claim.outbox_id
            for claim in abandoned_claims
        } == set(outbox_ids)
        assert all(
            claim.attempt_count == 1
            for claim in abandoned_claims
        )

        provider = RecordingProvider()
        config = _dispatcher_config(
            batch_size=4,
            lease_timeout=lease_timeout,
        )

        immediate_restart = DeliveryDispatcher(
            repository=(
                SqlAlchemyDeliveryRepository(
                    session_factory
                )
            ),
            provider=provider,
            cipher=_cipher(),
            config=config,
            clock=lambda: pre_expiry_time,
        )

        immediate_result = (
            await immediate_restart.dispatch_once()
        )

        assert immediate_result.claimed == 0
        assert immediate_result.delivered == 0
        assert len(provider.calls) == 0

        expired_restart = DeliveryDispatcher(
            repository=(
                SqlAlchemyDeliveryRepository(
                    session_factory
                )
            ),
            provider=provider,
            cipher=_cipher(),
            config=config,
            clock=lambda: post_expiry_time,
        )

        recovered_result = (
            await expired_restart.dispatch_once()
        )

        assert recovered_result.claimed == 4
        assert recovered_result.delivered == 4
        assert recovered_result.retry_scheduled == 0
        assert recovered_result.dead_lettered == 0
        assert recovered_result.stale_finalization == 0

        idempotency_keys = [
            call["idempotency_key"]
            for call in provider.calls
        ]

        assert len(provider.calls) == 4
        assert len(set(idempotency_keys)) == 4
        assert set(idempotency_keys) == {
            f"pmk-auth-delivery-v1:{outbox_id}"
            for outbox_id in outbox_ids
        }

        stale_results = await asyncio.gather(
            *(
                interrupted_repository.mark_delivered(
                    outbox_id=claim.outbox_id,
                    claim_id=claim.claim_id,
                    delivered_at=post_expiry_time,
                )
                for claim in abandoned_claims
            )
        )

        assert stale_results == [
            False,
            False,
            False,
            False,
        ]

        rows = await _load_outbox_rows(
            session_factory,
            outbox_ids,
        )

        assert all(
            row.delivered_at == post_expiry_time
            for row in rows
        )
        assert all(
            row.attempt_count == 2
            for row in rows
        )
        assert all(
            row.claim_id is None
            for row in rows
        )
        assert all(
            row.claimed_at is None
            for row in rows
        )
        assert all(
            row.dead_lettered_at is None
            for row in rows
        )
        assert all(
            row.last_error_code is None
            for row in rows
        )
    finally:
        await _cleanup_user(
            session_factory,
            user_id,
        )
        await engine.dispose()
