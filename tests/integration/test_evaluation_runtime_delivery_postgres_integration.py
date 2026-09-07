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

DATABASE_URL = os.environ.get("EVALUATION_RUNTIME_INTEGRATION_DATABASE_URL") or os.environ.get(
    "AUTH_R5B_INTEGRATION_DATABASE_URL",
    "",
)

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason=(
        "Set EVALUATION_RUNTIME_INTEGRATION_DATABASE_URL to run the shared "
        "External Evaluation delivery concurrency gate."
    ),
)


def _async_database_url() -> str:
    return DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)


@pytest.mark.asyncio
async def test_same_key_race_claims_once_then_replays_and_consumes_one_unit(monkeypatch) -> None:
    engine = create_async_engine(_async_database_url(), pool_size=5, max_overflow=5)
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

    owner_id = "integration-evaluation-owner"
    grant_id = "integration-grant"
    api_key_id = "integration-key"
    key = "integration-race-001"
    now = datetime.now(UTC)
    fingerprint = delivery.evaluation_request_fingerprint(
        grant_id=grant_id,
        api_key_id=api_key_id,
        task_id="crm.customer_context",
        binding_id="evaluation.crm.integration",
        task_input={"customer_id": "1"},
    )
    authority = {
        "evaluation_grants_v1": [
            {
                "grant_id": grant_id,
                "status": "active",
                "client_id": "integration-client",
                "allowed_scopes": ["run:evaluation"],
                "allowed_task_ids": ["crm.customer_context"],
                "allowed_binding_ids": ["evaluation.crm.integration"],
                "allowed_endpoints": [
                    {"method": "POST", "path": "/evaluation/runtime/task-execute"}
                ],
                "max_requests": 1,
                "expires_at": (now + timedelta(days=1)).isoformat(),
                "execution_mode": "evaluation_runtime",
                "real_runtime_execution": True,
                "production_allowed": False,
            }
        ]
    }

    async with sessions() as setup:
        await setup.execute(
            text(
                "DELETE FROM evaluation_runtime_delivery "
                "WHERE owner_id_sha256 = :owner_id_sha256"
            ),
            {"owner_id_sha256": delivery._owner_digest(owner_id)},
        )
        await setup.execute(
            text("DELETE FROM evaluation_authority_key WHERE key_id = :key_id"),
            {"key_id": api_key_id},
        )
        await setup.execute(
            text("DELETE FROM evaluation_authority_state WHERE owner_id = :owner_id"),
            {"owner_id": owner_id},
        )
        setup.add(
            EvaluationAuthorityState(
                owner_id=owner_id,
                authority=authority,
                updated_at=now,
                production_allowed=False,
                raw_secret_visible=False,
            )
        )
        setup.add(
            EvaluationAuthorityKey(
                key_id=api_key_id,
                owner_id=owner_id,
                grant_id=grant_id,
                lookup_sha256=None,
                prefix="pmk_integration",
                hashed="not-used-by-claim-test",
                status="enabled",
                expires_at=now + timedelta(days=1),
                usage_count=0,
                quota_rejected_count=0,
                payload={"quota_limit": 1},
                created_at=now,
                last_used_at=None,
                revoked_at=None,
                production_allowed=False,
                raw_secret_visible=False,
            )
        )
        await setup.commit()

    async def claim():
        try:
            return await delivery.claim_evaluation_execution(
                owner_id=owner_id,
                grant_id=grant_id,
                api_key_id=api_key_id,
                idempotency_key=key,
                request_fingerprint=fingerprint,
                task_id="crm.customer_context",
                binding_id="evaluation.crm.integration",
            )
        except delivery.EvaluationReplayBlockedError as exc:
            return exc

    try:
        first, second = await asyncio.gather(claim(), claim())
        outcomes = [first, second]
        claimed = [item for item in outcomes if isinstance(item, dict)]
        blocked = [
            item
            for item in outcomes
            if isinstance(item, delivery.EvaluationReplayBlockedError)
        ]
        assert len(claimed) == 1
        assert len(blocked) == 1
        assert claimed[0]["status"] == "claimed"
        assert claimed[0]["record"]["usage_count"] == 1
        assert claimed[0]["record"]["quota_semantics"] == "admitted_execution"

        async with sessions() as inspect:
            authority_key = await inspect.get(EvaluationAuthorityKey, api_key_id)
            assert authority_key is not None
            assert authority_key.usage_count == 1

        record_id = claimed[0]["record"]["record_id"]
        await delivery.complete_evaluation_execution(
            owner_id=owner_id,
            record_id=record_id,
            evidence={"execution_id": "exec-integration-1"},
            replay_response={
                "execution_id": "exec-integration-1",
                "evaluation_runtime": True,
                "raw_response_included": False,
                "raw_secret_visible": False,
                "raw_task_input_persisted": False,
            },
        )

        replay = await delivery.claim_evaluation_execution(
            owner_id=owner_id,
            grant_id=grant_id,
            api_key_id=api_key_id,
            idempotency_key=key,
            request_fingerprint=fingerprint,
            task_id="crm.customer_context",
            binding_id="evaluation.crm.integration",
        )
        assert replay["status"] == "replay"
        assert replay["response"]["execution_id"] == "exec-integration-1"

        async with sessions() as inspect:
            authority_key = await inspect.get(EvaluationAuthorityKey, api_key_id)
            assert authority_key is not None
            assert authority_key.usage_count == 1

        with pytest.raises(delivery.EvaluationQuotaExceededError):
            await delivery.claim_evaluation_execution(
                owner_id=owner_id,
                grant_id=grant_id,
                api_key_id=api_key_id,
                idempotency_key="integration-race-002",
                request_fingerprint=delivery.evaluation_request_fingerprint(
                    grant_id=grant_id,
                    api_key_id=api_key_id,
                    task_id="crm.customer_context",
                    binding_id="evaluation.crm.integration",
                    task_input={"customer_id": "2"},
                ),
                task_id="crm.customer_context",
                binding_id="evaluation.crm.integration",
            )

        async with sessions() as inspect:
            authority_key = await inspect.get(EvaluationAuthorityKey, api_key_id)
            assert authority_key is not None
            assert authority_key.usage_count == 1

        conflicting_fingerprint = delivery.evaluation_request_fingerprint(
            grant_id=grant_id,
            api_key_id=api_key_id,
            task_id="crm.customer_context",
            binding_id="evaluation.crm.integration",
            task_input={"customer_id": "3"},
        )
        with pytest.raises(delivery.EvaluationIdempotencyConflictError):
            await delivery.claim_evaluation_execution(
                owner_id=owner_id,
                grant_id=grant_id,
                api_key_id=api_key_id,
                idempotency_key=key,
                request_fingerprint=conflicting_fingerprint,
                task_id="crm.customer_context",
                binding_id="evaluation.crm.integration",
            )
    finally:
        async with sessions() as cleanup:
            await cleanup.execute(
                text(
                    "DELETE FROM evaluation_runtime_delivery "
                    "WHERE owner_id_sha256 = :owner_id_sha256"
                ),
                {"owner_id_sha256": delivery._owner_digest(owner_id)},
            )
            await cleanup.execute(
                text("DELETE FROM evaluation_authority_key WHERE key_id = :key_id"),
                {"key_id": api_key_id},
            )
            await cleanup.execute(
                text("DELETE FROM evaluation_authority_state WHERE owner_id = :owner_id"),
                {"owner_id": owner_id},
            )
            await cleanup.commit()
        await engine.dispose()
