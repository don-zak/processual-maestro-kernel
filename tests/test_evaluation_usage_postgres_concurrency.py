from __future__ import annotations

import asyncio
import os
import uuid

import pytest
from sqlalchemy import delete, func, select

from processual_api.db.session import close_db, get_session_factory, init_db
from processual_api.services.evaluation_grant_authority import (
    verify_durable_evaluation_api_key,
)
from processual_api.services.evaluation_grant_persistence import (
    EvaluationApiKeyAuthority,
    EvaluationGrantAuthority,
    EvaluationUsageLedger,
)
from processual_api.services.evaluation_grant_provisioning import (
    create_durable_evaluation_grant,
    issue_durable_evaluation_key,
)
from processual_api.services.evaluation_grant_usage import (
    EvaluationUsageError,
    record_evaluation_api_key_usage,
)

_DATABASE_URL = os.environ.get("DATABASE_URL", "").lower()
pytestmark = pytest.mark.skipif(
    not _DATABASE_URL.startswith(("postgresql://", "postgresql+asyncpg://")),
    reason="PostgreSQL evaluation usage concurrency qualification requires DATABASE_URL",
)


@pytest.mark.asyncio
async def test_evaluation_usage_concurrency_never_overshoots_quota() -> None:
    suffix = uuid.uuid4().hex
    owner_ref = f"qualification-admin-{suffix}"
    client_ref = f"qualification-eval-usage-{suffix}"
    grant_uuid: uuid.UUID | None = None

    await init_db()
    session_factory = get_session_factory()
    try:
        grant = await create_durable_evaluation_grant(
            owner_user_ref=owner_ref,
            client_ref=client_ref,
            user_ref=client_ref,
            issued_to="Evaluation Customer",
            purpose="PostgreSQL evaluation concurrency qualification",
            allowed_task_ids=["system.health"],
            task_scope_ids=["read:health"],
            allowed_scopes=["read:health"],
            max_requests=5,
            expires_in_days=7,
            approved_by_actor_ref=owner_ref,
            approved_by_role="owner_admin",
        )
        _key, raw_key = await issue_durable_evaluation_key(
            grant_ref=grant["grant_id"],
            owner_user_ref=owner_ref,
            label="Evaluation usage qualification",
        )
        identity = await verify_durable_evaluation_api_key(raw_key)
        assert identity is not None
        grant_uuid = uuid.UUID(identity["evaluation_grant_authority_id"])

        async def reserve(index: int):
            try:
                usage = await record_evaluation_api_key_usage(
                    current_user=identity,
                    units=1,
                    idempotency_key=f"qualification-{suffix}-{index}",
                    task_id="system.health",
                )
                return ("success", usage.id)
            except EvaluationUsageError as exc:
                return ("rejected", str(exc))

        results = await asyncio.gather(*(reserve(index) for index in range(10)))
        successes = [value for state, value in results if state == "success"]
        rejections = [value for state, value in results if state == "rejected"]

        assert len(successes) == 5
        assert len(rejections) == 5
        assert set(rejections) == {"evaluation_quota_limit_exceeded"}

        async with session_factory() as session:
            grant_record = await session.get(EvaluationGrantAuthority, grant_uuid)
            assert grant_record is not None
            assert grant_record.used_requests == 5
            assert grant_record.rejected_requests == 5
            ledger_count = await session.scalar(
                select(func.count(EvaluationUsageLedger.id)).where(
                    EvaluationUsageLedger.grant_id == grant_uuid
                )
            )
            ledger_units = await session.scalar(
                select(func.coalesce(func.sum(EvaluationUsageLedger.units), 0)).where(
                    EvaluationUsageLedger.grant_id == grant_uuid
                )
            )
            assert ledger_count == 5
            assert ledger_units == 5

        first = await record_evaluation_api_key_usage(
            current_user=identity,
            units=1,
            idempotency_key=f"qualification-{suffix}-0",
            task_id="system.health",
        )
        second = await record_evaluation_api_key_usage(
            current_user=identity,
            units=1,
            idempotency_key=f"qualification-{suffix}-0",
            task_id="system.health",
        )
        assert first.id == second.id

        async with session_factory() as session:
            grant_record = await session.get(EvaluationGrantAuthority, grant_uuid)
            assert grant_record is not None
            assert grant_record.used_requests == 5
    finally:
        if grant_uuid is not None:
            async with session_factory() as session:
                await session.execute(
                    delete(EvaluationUsageLedger).where(
                        EvaluationUsageLedger.grant_id == grant_uuid
                    )
                )
                await session.execute(
                    delete(EvaluationApiKeyAuthority).where(
                        EvaluationApiKeyAuthority.grant_id == grant_uuid
                    )
                )
                await session.execute(
                    delete(EvaluationGrantAuthority).where(
                        EvaluationGrantAuthority.id == grant_uuid
                    )
                )
                await session.commit()
        await close_db()
