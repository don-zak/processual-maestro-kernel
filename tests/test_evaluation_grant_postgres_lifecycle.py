from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import delete, select

from processual_api.db.session import close_db, get_session_factory, init_db
from processual_api.services.evaluation_grant_persistence import (
    EvaluationApiKeyAuthority,
    EvaluationGrantAuthority,
    EvaluationUsageLedger,
)
from processual_api.services.evaluation_grant_provisioning import (
    EvaluationGrantProvisioningError,
    create_durable_evaluation_grant,
    issue_durable_evaluation_key,
    list_durable_evaluation_grants,
    revoke_durable_evaluation_grant,
)

_DATABASE_URL = os.environ.get("DATABASE_URL", "").lower()
pytestmark = pytest.mark.skipif(
    not _DATABASE_URL.startswith(("postgresql://", "postgresql+asyncpg://")),
    reason="PostgreSQL evaluation-grant qualification requires DATABASE_URL",
)


@pytest.mark.asyncio
async def test_durable_evaluation_grant_key_lifecycle_is_transactional() -> None:
    suffix = uuid.uuid4().hex
    owner_ref = f"qualification-admin-{suffix}"
    client_ref = f"qualification-eval-client-{suffix}"

    await init_db()
    session_factory = get_session_factory()
    grant_uuid: uuid.UUID | None = None
    try:
        grant = await create_durable_evaluation_grant(
            owner_user_ref=owner_ref,
            client_ref=client_ref,
            user_ref=client_ref,
            issued_to="Evaluation Customer",
            purpose="PostgreSQL evaluation authority qualification",
            allowed_task_ids=["system.health"],
            task_scope_ids=["read:health"],
            allowed_scopes=["read:health"],
            max_requests=5,
            expires_in_days=7,
            approved_by_actor_ref=owner_ref,
            approved_by_role="owner_admin",
        )
        assert grant["subscription_required"] is False
        assert grant["quota_source"] == "evaluation_usage_ledger"
        assert grant["production_allowed"] is False

        items = await list_durable_evaluation_grants(owner_user_ref=owner_ref)
        assert len(items) == 1
        assert items[0]["grant_id"] == grant["grant_id"]
        assert items[0]["active_key_count"] == 0

        raw_keys: list[str] = []
        for index in range(3):
            key, raw_key = await issue_durable_evaluation_key(
                grant_ref=grant["grant_id"],
                owner_user_ref=owner_ref,
                label=f"Evaluation lifecycle {index}",
            )
            raw_keys.append(raw_key)
            assert raw_key.startswith("pmk_")
            assert raw_key not in repr(key)
            assert key["raw_secret_visible"] is False
            assert key["evaluation_grant_id"] == grant["grant_id"]
            assert key["subscription_required"] is False

        with pytest.raises(
            EvaluationGrantProvisioningError,
            match="maximum_active_evaluation_keys_reached",
        ):
            await issue_durable_evaluation_key(
                grant_ref=grant["grant_id"],
                owner_user_ref=owner_ref,
                label="Must be rejected",
            )

        async with session_factory() as session:
            grant_record = await session.scalar(
                select(EvaluationGrantAuthority).where(
                    EvaluationGrantAuthority.grant_ref == grant["grant_id"]
                )
            )
            assert grant_record is not None
            grant_uuid = grant_record.id
            keys = list(
                (
                    await session.scalars(
                        select(EvaluationApiKeyAuthority).where(
                            EvaluationApiKeyAuthority.grant_id == grant_uuid
                        )
                    )
                ).all()
            )
            assert len(keys) == 3
            stored_hashes = {stored.key_hash for stored in keys}
            for raw_key in raw_keys:
                assert raw_key not in stored_hashes
                assert all(raw_key not in stored_hash for stored_hash in stored_hashes)

        revoked = await revoke_durable_evaluation_grant(
            grant_ref=grant["grant_id"],
            owner_user_ref=owner_ref,
        )
        assert revoked["status"] == "revoked"
        assert revoked["revoked_key_count"] == 3

        async with session_factory() as session:
            grant_record = await session.scalar(
                select(EvaluationGrantAuthority).where(
                    EvaluationGrantAuthority.grant_ref == grant["grant_id"]
                )
            )
            assert grant_record is not None
            assert grant_record.status == "revoked"
            keys = list(
                (
                    await session.scalars(
                        select(EvaluationApiKeyAuthority).where(
                            EvaluationApiKeyAuthority.grant_id == grant_record.id
                        )
                    )
                ).all()
            )
            assert {key.status for key in keys} == {"revoked"}
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
