from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.exc import IntegrityError

from processual_api.auth.models import (
    AuthActionToken,
    IdentityOrganization,
    IdentityTermsAcceptance,
    IdentityUser,
    OrganizationMembership,
)
from processual_api.auth.registration_repository import (
    RegistrationConflictError,
    SqlAlchemyRegistrationRepository,
    SqlAlchemyRegistrationUnitOfWork,
)


def test_repository_adds_user_terms_token_and_server_owned_membership() -> None:
    session = Mock()
    repository = SqlAlchemyRegistrationRepository(session)
    now = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)

    repository.add_registration(
        user_id=uuid.uuid4(),
        email_normalized="owner@example.com",
        display_name="Owner",
        password_hash="$argon2id$encoded",
        terms_version="2026-07",
        accepted_at=now,
        action_token_id=uuid.uuid4(),
        action_token_hash="a" * 64,
        action_token_expires_at=now + timedelta(hours=24),
        organization_id=uuid.uuid4(),
        organization_slug="example-a1b2c3d4",
        organization_name="Example",
    )

    added = [call.args[0] for call in session.add.call_args_list]
    assert any(isinstance(item, IdentityUser) for item in added)
    assert any(isinstance(item, IdentityTermsAcceptance) for item in added)
    assert any(isinstance(item, AuthActionToken) for item in added)
    assert any(isinstance(item, IdentityOrganization) for item in added)
    membership = next(item for item in added if isinstance(item, OrganizationMembership))
    assert membership.role == "organization_owner"
    assert membership.status == "active"


@pytest.mark.asyncio
async def test_unit_of_work_maps_integrity_race_and_rolls_back() -> None:
    session = AsyncMock()
    session.commit.side_effect = IntegrityError("statement", {}, Exception("duplicate"))
    unit = SqlAlchemyRegistrationUnitOfWork(lambda: session)

    async with unit:
        with pytest.raises(RegistrationConflictError):
            await unit.commit()

    assert session.rollback.await_count >= 1
    session.close.assert_awaited_once()
