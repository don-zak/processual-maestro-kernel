from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from sqlalchemy.exc import IntegrityError

from processual_api.auth.admin_recovery_email_repository import (
    AdminRecoveryEmailConflictError,
    SqlAlchemyAdminRecoveryEmailUnitOfWork,
)


@pytest.mark.asyncio
async def test_integrity_error_is_mapped_to_recovery_email_conflict() -> None:
    session = AsyncMock()
    session.commit.side_effect = IntegrityError("statement", {}, RuntimeError("constraint"))
    unit = SqlAlchemyAdminRecoveryEmailUnitOfWork(lambda: session)

    async with unit:
        with pytest.raises(AdminRecoveryEmailConflictError):
            await unit.commit()

    session.rollback.assert_awaited()
    session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_infrastructure_failure_is_not_misreported_as_identity_conflict() -> None:
    session = AsyncMock()
    failure = RuntimeError("database transport unavailable")
    session.commit.side_effect = failure
    unit = SqlAlchemyAdminRecoveryEmailUnitOfWork(lambda: session)

    with pytest.raises(RuntimeError, match="database transport unavailable"):
        async with unit:
            await unit.commit()

    # __aexit__ owns rollback for non-integrity failures so the original
    # infrastructure exception remains visible to the caller.
    session.rollback.assert_awaited_once()
    session.close.assert_awaited_once()
