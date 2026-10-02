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
        "Set EVALUATION_RUNTIME_INTEGRATION_DATABASE_URL to run the isolated "
        "External Evaluation PostgreSQL quota-boundary qualification."
    ),
)


def _async_database_url() -> str:
    return DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)


@pytest.mark.asyncio
async def test_concurrent_unique_claims_stop_exactly_at_quota_boundary(monkeypatch) -> None:
    """Q10: unique concurrent admissions never overshoot the PostgreSQL key quota."""

    quota_limit = 5
    attempt_count = 12
    engine = create_async_engine(_async_database_url(), pool_size=attempt_count, max_overflow=2)
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

    owner_id = "q10-isolated-owner"
    grant_id = "q10-isolated-grant"
    api_key_id = "q10-isolated-key"
    task_id = "crm.customer_context"
    binding_id = "evaluation.crm.q10-isolated"
    now = datetime.now(UTC)
    authority = {
        "evaluation_grants_v1": [
            {
                "grant_id": grant_id,
                "status": "active",
                "client_id": "q10-isolated-client",
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
                prefix="pmk_q10_isolated",
                hashed="not-used-by-q10-claim-test",
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

    async def unique_claim(index: int):
        idempotency_key = f"q10-unique-{index:03d}"
        fingerprint = delivery.evaluation_request_fingerprint(
            grant_id=grant_id,
            api_key_id=api_key_id,
            task_id=task_id,
            binding_id=binding_id,
            task_input={"customer_id": f"q10-customer-{index:03d}"},
        )
        try:
            return await delivery.claim_evaluation_execution(
                owner_id=owner_id,
                grant_id=grant_id,
                api_key_id=api_key_id,
                idempotency_key=idempotency_key,
                request_fingerprint=fingerprint,
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
            item for item in outcomes if isinstance(item, delivery.EvaluationQuotaExceededError)
        ]

        assert len(claimed) == quota_limit
        assert len(rejected) == attempt_count - quota_limit
        assert sorted(item["record"]["usage_count"] for item in claimed) == list(
            range(1, quota_limit + 1)
        )
        assert all(item["status"] == "claimed" for item in claimed)
        assert all(
            item["record"]["quota_semantics"] == "admitted_execution"
            for item in claimed
        )

        async with sessions() as inspect:
            authority_key = await inspect.get(EvaluationAuthorityKey, api_key_id)
            assert authority_key is not None
            assert authority_key.usage_count == quota_limit
            assert authority_key.usage_count <= quota_limit
            assert authority_key.quota_rejected_count == attempt_count - quota_limit
            assert authority_key.payload["usage_count"] == quota_limit
            assert authority_key.payload["evaluation_grant_state"] == "quota_exhausted"

            delivery_count = (
                await inspect.execute(
                    text(
                        "SELECT count(*) FROM evaluation_runtime_delivery "
                        "WHERE owner_id_sha256 = :owner_id_sha256"
                    ),
                    {"owner_id_sha256": delivery._owner_digest(owner_id)},
                )
            ).scalar_one()
            assert delivery_count == quota_limit
    finally:
        await cleanup()
        await engine.dispose()
