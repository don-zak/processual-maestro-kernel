from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from processual_api.services import evaluation_runtime_delivery_postgres as delivery
from processual_api.services.evaluation_authority_models import (
    EvaluationAuthorityKey,
    EvaluationAuthorityState,
)

DATABASE_URL = os.environ.get("EVALUATION_RUNTIME_INTEGRATION_DATABASE_URL", "")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason=(
        "Set EVALUATION_RUNTIME_INTEGRATION_DATABASE_URL to run the P7 "
        "PostgreSQL quota atomicity and replay qualification."
    ),
)


def _async_database_url() -> str:
    return DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)


@pytest.mark.asyncio
async def test_quota_one_twenty_unique_then_twenty_replays_consume_exactly_one(
    monkeypatch,
) -> None:
    """P7: quota=1 admits once under concurrency and durable replay remains +0."""

    quota_limit = 1
    attempt_count = 20
    engine = create_async_engine(
        _async_database_url(),
        pool_size=attempt_count,
        max_overflow=2,
    )
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    @asynccontextmanager
    async def scope():
        session = sessions()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    monkeypatch.setattr(delivery, "session_scope", scope)

    owner_id = "p7-atomicity-owner"
    grant_id = "p7-atomicity-grant"
    api_key_id = "p7-atomicity-key"
    task_id = "crm.customer_context"
    binding_id = "evaluation.crm.p7-atomicity"
    now = datetime.now(UTC)
    authority = {
        "evaluation_grants_v1": [
            {
                "grant_id": grant_id,
                "status": "active",
                "client_id": "p7-atomicity-client",
                "allowed_scopes": ["run:evaluation"],
                "allowed_task_ids": [task_id],
                "allowed_binding_ids": [binding_id],
                "allowed_endpoints": [
                    {"method": "POST", "path": "/evaluation/runtime/task-execute"}
                ],
                "max_requests": quota_limit,
                "expires_at": (now + timedelta(hours=1)).isoformat(),
                "execution_mode": "evaluation_runtime",
                "real_runtime_execution": True,
                "production_allowed": False,
            }
        ]
    }

    async def cleanup() -> None:
        async with sessions() as session:
            await session.execute(
                text(
                    "DELETE FROM evaluation_runtime_delivery "
                    "WHERE owner_id_sha256 = :owner_id_sha256"
                ),
                {"owner_id_sha256": delivery._owner_digest(owner_id)},
            )
            await session.execute(
                text("DELETE FROM evaluation_authority_key WHERE key_id = :key_id"),
                {"key_id": api_key_id},
            )
            await session.execute(
                text("DELETE FROM evaluation_authority_state WHERE owner_id = :owner_id"),
                {"owner_id": owner_id},
            )
            await session.commit()

    await cleanup()
    async with sessions() as setup:
        setup.add(
            EvaluationAuthorityState(
                owner_id=owner_id,
                authority=authority,
                updated_at=now,
                production_allowed=False,
                raw_secret_visible=False,
            )
        )
        await setup.flush()
        setup.add(
            EvaluationAuthorityKey(
                key_id=api_key_id,
                owner_id=owner_id,
                grant_id=grant_id,
                lookup_sha256=None,
                prefix="pmk_p7_atomicity",
                hashed="not-used-by-p7-claim-test",
                status="enabled",
                expires_at=now + timedelta(hours=1),
                usage_count=0,
                quota_rejected_count=0,
                payload={"quota_limit": quota_limit},
                created_at=now,
                last_used_at=None,
                revoked_at=None,
                production_allowed=False,
                raw_secret_visible=False,
            )
        )
        await setup.commit()

    def fingerprint(index: int) -> str:
        return delivery.evaluation_request_fingerprint(
            grant_id=grant_id,
            api_key_id=api_key_id,
            task_id=task_id,
            binding_id=binding_id,
            task_input={"customer_id": f"p7-customer-{index:03d}"},
        )

    async def unique_claim(index: int):
        try:
            return await delivery.claim_evaluation_execution(
                owner_id=owner_id,
                grant_id=grant_id,
                api_key_id=api_key_id,
                idempotency_key=f"p7-unique-{index:03d}",
                request_fingerprint=fingerprint(index),
                task_id=task_id,
                binding_id=binding_id,
            )
        except delivery.EvaluationQuotaExceededError as exc:
            return exc

    try:
        outcomes = await asyncio.gather(
            *(unique_claim(index) for index in range(attempt_count))
        )
        claimed = [item for item in outcomes if isinstance(item, dict)]
        rejected = [
            item
            for item in outcomes
            if isinstance(item, delivery.EvaluationQuotaExceededError)
        ]

        assert len(claimed) == 1
        assert len(rejected) == attempt_count - 1
        assert claimed[0]["status"] == "claimed"
        assert claimed[0]["record"]["usage_count"] == 1

        async with sessions() as inspect:
            authority_key = await inspect.get(EvaluationAuthorityKey, api_key_id)
            assert authority_key is not None
            assert authority_key.usage_count == 1
            assert authority_key.quota_rejected_count == attempt_count - 1
            delivery_count = (
                await inspect.execute(
                    text(
                        "SELECT count(*) FROM evaluation_runtime_delivery "
                        "WHERE owner_id_sha256 = :owner_id_sha256"
                    ),
                    {"owner_id_sha256": delivery._owner_digest(owner_id)},
                )
            ).scalar_one()
            assert delivery_count == 1

        admitted_index = next(
            index for index, item in enumerate(outcomes) if isinstance(item, dict)
        )
        admitted_key = f"p7-unique-{admitted_index:03d}"
        admitted_fingerprint = fingerprint(admitted_index)
        record_id = claimed[0]["record"]["record_id"]

        await delivery.complete_evaluation_execution(
            owner_id=owner_id,
            record_id=record_id,
            evidence={"execution_id": "exec-p7-atomicity-1"},
            replay_response={
                "execution_id": "exec-p7-atomicity-1",
                "evaluation_runtime": True,
                "raw_response_included": False,
                "raw_secret_visible": False,
                "raw_task_input_persisted": False,
            },
        )

        async def replay_claim():
            return await delivery.claim_evaluation_execution(
                owner_id=owner_id,
                grant_id=grant_id,
                api_key_id=api_key_id,
                idempotency_key=admitted_key,
                request_fingerprint=admitted_fingerprint,
                task_id=task_id,
                binding_id=binding_id,
            )

        replays = await asyncio.gather(*(replay_claim() for _ in range(attempt_count)))
        assert len(replays) == attempt_count
        assert all(item["status"] == "replay" for item in replays)
        assert all(
            item["response"]["execution_id"] == "exec-p7-atomicity-1"
            for item in replays
        )

        async with sessions() as inspect:
            authority_key = await inspect.get(EvaluationAuthorityKey, api_key_id)
            assert authority_key is not None
            assert authority_key.usage_count == 1
            assert authority_key.quota_rejected_count == attempt_count - 1
            delivery_count = (
                await inspect.execute(
                    text(
                        "SELECT count(*) FROM evaluation_runtime_delivery "
                        "WHERE owner_id_sha256 = :owner_id_sha256"
                    ),
                    {"owner_id_sha256": delivery._owner_digest(owner_id)},
                )
            ).scalar_one()
            assert delivery_count == 1
    finally:
        await cleanup()
        await engine.dispose()
