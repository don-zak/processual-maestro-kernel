from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from processual_api.billing.models import CustomerBillingProfile
from processual_api.billing.repository import BillingProfileRepository


@pytest.mark.asyncio
async def test_repository_gets_personal_profile_with_null_organization() -> None:
    expected = SimpleNamespace(id=uuid.uuid4())
    session = SimpleNamespace(
        scalar=AsyncMock(return_value=expected),
    )

    repository = BillingProfileRepository(session)
    result = await repository.get_for_context(
        user_id=uuid.uuid4(),
        organization_id=None,
    )

    assert result is expected
    statement = session.scalar.await_args.args[0]
    assert "organization_id IS NULL" in str(statement)


@pytest.mark.asyncio
async def test_repository_gets_organization_profile_by_context() -> None:
    expected = SimpleNamespace(id=uuid.uuid4())
    session = SimpleNamespace(
        scalar=AsyncMock(return_value=expected),
    )
    organization_id = uuid.uuid4()

    repository = BillingProfileRepository(session)
    result = await repository.get_for_context(
        user_id=uuid.uuid4(),
        organization_id=organization_id,
        for_update=True,
    )

    assert result is expected
    statement = session.scalar.await_args.args[0]
    rendered = str(statement)

    assert "organization_id" in rendered
    assert "FOR UPDATE" in rendered


@pytest.mark.asyncio
async def test_repository_creates_new_active_profile() -> None:
    session = SimpleNamespace(
        scalar=AsyncMock(return_value=None),
        add=Mock(),
        flush=AsyncMock(),
    )
    user_id = uuid.uuid4()

    repository = BillingProfileRepository(session)
    profile = await repository.upsert_for_context(
        user_id=user_id,
        organization_id=None,
        country_code="TN",
        region="Tunis",
        city="Tunis",
        postal_code="1000",
        address_line_1="Address",
        address_line_2=None,
    )

    assert isinstance(profile, CustomerBillingProfile)
    assert profile.user_id == user_id
    assert profile.organization_id is None
    assert profile.country_code == "TN"
    assert profile.status == "active"
    session.add.assert_called_once_with(profile)
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_repository_updates_address_without_overriding_review_status() -> None:
    profile = CustomerBillingProfile(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        organization_id=None,
        country_code="TN",
        status="review_required",
    )
    session = SimpleNamespace(
        scalar=AsyncMock(return_value=profile),
        add=Mock(),
        flush=AsyncMock(),
    )

    repository = BillingProfileRepository(session)
    updated = await repository.upsert_for_context(
        user_id=profile.user_id,
        organization_id=None,
        country_code="FR",
        region="Île-de-France",
        city="Paris",
        postal_code="75001",
        address_line_1="Address",
        address_line_2=None,
    )

    assert updated is profile
    assert updated.country_code == "FR"
    assert updated.status == "review_required"
    session.add.assert_not_called()
    session.flush.assert_awaited_once()
