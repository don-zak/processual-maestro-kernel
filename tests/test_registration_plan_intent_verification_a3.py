import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.sql.dml import Update

from processual_api.auth.registration_repository import SqlAlchemyRegistrationRepository


@pytest.mark.asyncio
async def test_repository_marks_only_pending_plan_intent_verified():
    session = AsyncMock()
    repository = SqlAlchemyRegistrationRepository(session)
    user_id = uuid.uuid4()
    verified_at = datetime(2026, 8, 3, 20, 0, tzinfo=UTC)

    await repository.mark_registration_plan_intent_verified(
        user_id,
        verified_at=verified_at,
    )

    statement = session.execute.await_args.args[0]
    assert isinstance(statement, Update)
    compiled = str(statement.compile(compile_kwargs={"literal_binds": True}))
    assert "auth_registration_plan_intents" in compiled
    assert "pending_verification" in compiled
    assert "verified" in compiled
    assert user_id in statement.compile().params.values()
