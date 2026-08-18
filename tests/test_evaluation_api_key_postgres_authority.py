from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import delete, select

from processual_api.db.session import close_db, get_session_factory, init_db
from processual_api.services.evaluation_grant_authority import (
    DurableEvaluationApiKeyDenied,
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
    revoke_durable_evaluation_grant,
)

_DATABASE_URL = os.environ.get("DATABASE_URL", "").lower()
pytestmark = pytest.mark.skipif(
    not _DATABASE_URL.startswith(("postgresql://", "postgresql+asyncpg://")),
    reason="PostgreSQL evaluation-key authority qualification requires DATABASE_URL",
)


@pytest.mark.asyncio
async def test_durable_evaluation_key_authentication_fails_closed_after_grant_revoke() -> None:
    suffix = uuid.uuid4().hex
    owner_ref = f"qualification-admin-{suffix}"
    client_ref = f"qualification-eval-auth-{suffix}"
    grant_uuid: uuid.UUID | None = None

    await init_db()
    session_factory = get_session_factory()
    try:
        grant = await create_durable_evaluation_grant(
            owner_user_ref=owner_ref,
            client_ref=client_ref,
            user_ref=client_ref,
            issued_to="Evaluation Customer",
            purpose="PostgreSQL evaluation authentication qualification",
            allowed_task_ids=["system.health"],
            task_scope_ids=["read:health"],
            allowed_scopes=["read:health"],
            max_requests=5,
            expires_in_days=7,
            approved_by_actor_ref=owner_ref,
            approved_by_role="owner_admin",
        )
        key, raw_key = await issue_durable_evaluation_key(
            grant_ref=grant["grant_id"],
            owner_user_ref=owner_ref,
            label="Evaluation auth qualification",
        )

        identity = await verify_durable_evaluation_api_key(raw_key)
        assert identity is not None
        assert identity["session_type"] == "evaluation_api_key"
        assert identity["client_id"] == client_ref
        assert identity["evaluation_grant_id"] == grant["grant_id"]
        assert identity["api_key_id"] == key["key_id"]
        assert identity["subscription_required"] is False
        assert identity["quota_source"] == "evaluation_usage_ledger"
        assert identity["production_allowed"] is False

        async with session_factory() as session:
            grant_record = await session.scalar(
                select(EvaluationGrantAuthority).where(
                    EvaluationGrantAuthority.grant_ref == grant["grant_id"]
                )
            )
            assert grant_record is not None
            grant_uuid = grant_record.id

        await revoke_durable_evaluation_grant(
            grant_ref=grant["grant_id"],
            owner_user_ref=owner_ref,
        )

        with pytest.raises(
            DurableEvaluationApiKeyDenied,
            match="revoked_or_disabled|grant_inactive",
        ):
            await verify_durable_evaluation_api_key(raw_key)
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
