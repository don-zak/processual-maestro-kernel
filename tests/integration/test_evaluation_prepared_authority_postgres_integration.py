from __future__ import annotations

import os
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from processual_api.services import evaluation_authority_postgres as authority
from processual_api.services import evaluation_prepared_authority as prepared

DATABASE_URL = os.environ.get("EVALUATION_RUNTIME_INTEGRATION_DATABASE_URL") or os.environ.get(
    "AUTH_R5B_INTEGRATION_DATABASE_URL",
    "",
)

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="Set EVALUATION_RUNTIME_INTEGRATION_DATABASE_URL to run the prepared authority gate.",
)


def _async_database_url() -> str:
    return DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)


@pytest.mark.asyncio
async def test_prepared_binding_authority_round_trips_through_postgres(monkeypatch) -> None:
    engine = create_async_engine(_async_database_url(), pool_size=2, max_overflow=2)
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

    monkeypatch.setattr(authority, "session_scope", scope)
    owner_id = "integration-prepared-evaluation-owner"

    try:
        async with sessions() as cleanup:
            await cleanup.execute(
                text("DELETE FROM evaluation_authority_state WHERE owner_id = :owner_id"),
                {"owner_id": owner_id},
            )
            await cleanup.commit()

        assert await prepared.load_prepared_evaluation_authority(owner_id) == {}

        snapshot = {
            "enterprise_endpoint_bindings_v1": [
                {
                    "binding_id": "evaluation.crm.customer_context.owned",
                    "task_id": "crm.customer_context",
                }
            ],
            "enterprise_sandbox_content_contracts_v1": [
                {
                    "binding_id": "evaluation.crm.customer_context.owned",
                    "dataset_reference": "project-evaluation-sandbox-customer-v1",
                }
            ],
            "enterprise_sandbox_secret_references_v1": [
                {
                    "binding_id": "evaluation.crm.customer_context.owned",
                    "provider_id": "anonymous",
                    "secret_reference": "public",
                }
            ],
            "enterprise_endpoint_sandbox_grants_v1": [
                {
                    "grant_id": "sandbox-grant-postgres",
                    "binding_id": "evaluation.crm.customer_context.owned",
                    "task_id": "crm.customer_context",
                    "status": "active",
                }
            ],
            "enterprise_endpoint_sandbox_evidence_v1": [
                {
                    "binding_id": "evaluation.crm.customer_context.owned",
                    "task_id": "crm.customer_context",
                    "operational_proof": True,
                }
            ],
        }
        await prepared.save_prepared_evaluation_authority(owner_id, snapshot)
        reloaded = await prepared.load_prepared_evaluation_authority(owner_id)

        assert reloaded == snapshot
        assert reloaded["enterprise_endpoint_bindings_v1"][0]["binding_id"] == (
            "evaluation.crm.customer_context.owned"
        )
        assert reloaded["enterprise_sandbox_secret_references_v1"][0]["secret_reference"] == (
            "public"
        )
    finally:
        async with sessions() as cleanup:
            await cleanup.execute(
                text("DELETE FROM evaluation_authority_state WHERE owner_id = :owner_id"),
                {"owner_id": owner_id},
            )
            await cleanup.commit()
        await engine.dispose()
