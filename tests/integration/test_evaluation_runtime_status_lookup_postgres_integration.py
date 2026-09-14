from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from processual_api.services import evaluation_runtime_delivery_postgres as delivery
from processual_api.services.evaluation_runtime_delivery_models import EvaluationRuntimeDelivery

DATABASE_URL = os.environ.get("EVALUATION_RUNTIME_INTEGRATION_DATABASE_URL", "")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason=(
        "Set EVALUATION_RUNTIME_INTEGRATION_DATABASE_URL to run the P7 "
        "unbounded execution-status lookup qualification."
    ),
)


def _async_database_url() -> str:
    return DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)


@pytest.mark.asyncio
async def test_public_execution_status_lookup_is_not_limited_to_latest_100(monkeypatch) -> None:
    engine = create_async_engine(_async_database_url(), pool_size=4, max_overflow=2)
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

    owner_id = "p7-status-lookup-owner"
    owner_digest = delivery._owner_digest(owner_id)
    grant_id = "p7-status-lookup-grant"
    api_key_id = "p7-status-lookup-key"
    now = datetime.now(UTC)

    async def cleanup() -> None:
        async with sessions() as session:
            await session.execute(
                text(
                    "DELETE FROM evaluation_runtime_delivery "
                    "WHERE owner_id_sha256 = :owner_id_sha256"
                ),
                {"owner_id_sha256": owner_digest},
            )
            await session.commit()

    await cleanup()
    try:
        async with sessions() as setup:
            for index in range(101):
                accepted_at = now + timedelta(seconds=index)
                setup.add(
                    EvaluationRuntimeDelivery(
                        record_id=f"{index:064x}",
                        owner_id_sha256=owner_digest,
                        grant_id=grant_id,
                        api_key_id=api_key_id,
                        idempotency_key_sha256=f"{index + 1000:064x}",
                        request_fingerprint=f"{index + 2000:064x}",
                        task_id="crm.customer_context",
                        binding_id="evaluation.crm.p7-status-lookup",
                        state="evidence_persisted",
                        state_history=[
                            {"state": "accepted", "at": accepted_at.isoformat()},
                            {"state": "evidence_persisted", "at": accepted_at.isoformat()},
                        ],
                        evidence={"execution_id": f"exec-p7-status-{index:03d}"},
                        replay_response={
                            "execution_id": f"exec-p7-status-{index:03d}",
                            "evaluation_runtime": True,
                            "raw_response_included": False,
                            "raw_secret_visible": False,
                            "raw_task_input_persisted": False,
                        },
                        accepted_at=accepted_at,
                        execution_started_at=accepted_at,
                        executed_at=accepted_at,
                        evidence_persisted_at=accepted_at,
                        failed_at=None,
                        failure_code=None,
                        network_outcome="success",
                        raw_task_input_persisted=False,
                        raw_secret_visible=False,
                    )
                )
            await setup.commit()

        # index 0 is older than the latest-100 window once 101 rows exist.
        receipt = await delivery.get_evaluation_execution_status(
            owner_id=owner_id,
            grant_id=grant_id,
            api_key_id=api_key_id,
            execution_id="exec-p7-status-000",
        )
        assert receipt is not None
        assert receipt["execution_id"] == "exec-p7-status-000"
        assert receipt["status"] == "succeeded"

        # The canonical runtime path remains a direct record_id lookup.
        direct = await delivery.get_evaluation_execution_status(
            owner_id=owner_id,
            grant_id=grant_id,
            api_key_id=api_key_id,
            execution_id=f"{0:064x}",
        )
        assert direct is not None
        assert direct["record_id"] == f"{0:064x}"
    finally:
        await cleanup()
        await engine.dispose()
