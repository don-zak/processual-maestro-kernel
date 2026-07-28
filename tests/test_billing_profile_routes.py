from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

import processual_api.billing.router as billing_router
from processual_api.auth.security import get_current_user
from processual_api.db import get_session
from processual_api.main import app

USER_ID = uuid.uuid4()


class FakeSession:
    def __init__(self) -> None:
        self.commit = AsyncMock()
        self.rollback = AsyncMock()
        self.refresh = AsyncMock()


def _current_user() -> dict[str, object]:
    return {
        "sub": str(USER_ID),
        "user_id": str(USER_ID),
        "organization_id": None,
        "session_type": "identity_user",
        "role": "client",
    }


def _profile(*, country_code: str = "TN") -> SimpleNamespace:
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=uuid.uuid4(),
        user_id=USER_ID,
        organization_id=None,
        country_code=country_code,
        region="Tunis",
        city="Tunis",
        postal_code="1000",
        address_line_1="Address",
        address_line_2=None,
        status="active",
        created_at=now,
        updated_at=now,
    )


def _client(session: FakeSession) -> TestClient:
    app.dependency_overrides[get_current_user] = _current_user
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app)


def test_get_billing_profile_returns_current_profile(monkeypatch) -> None:
    profile = _profile()
    repository = SimpleNamespace(
        get_for_context=AsyncMock(return_value=profile),
    )
    monkeypatch.setattr(
        billing_router,
        "BillingProfileRepository",
        lambda session: repository,
    )

    session = FakeSession()
    client = _client(session)

    try:
        response = client.get("/billing/profile")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["country_code"] == "TN"
    repository.get_for_context.assert_awaited_once_with(
        user_id=USER_ID,
        organization_id=None,
    )


def test_get_billing_profile_returns_explicit_missing_state(
    monkeypatch,
) -> None:
    repository = SimpleNamespace(
        get_for_context=AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        billing_router,
        "BillingProfileRepository",
        lambda session: repository,
    )

    session = FakeSession()
    client = _client(session)

    try:
        response = client.get("/billing/profile")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"] == "billing_profile_not_found"


def test_put_billing_profile_derives_ownership_from_session(
    monkeypatch,
) -> None:
    profile = _profile()
    repository = SimpleNamespace(
        upsert_for_context=AsyncMock(return_value=profile),
    )
    monkeypatch.setattr(
        billing_router,
        "BillingProfileRepository",
        lambda session: repository,
    )

    session = FakeSession()
    client = _client(session)

    try:
        response = client.put(
            "/billing/profile",
            json={
                "country_code": "tn",
                "region": "Tunis",
                "city": "Tunis",
                "postal_code": "1000",
                "address_line_1": "Address",
                "address_line_2": None,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    repository.upsert_for_context.assert_awaited_once_with(
        user_id=USER_ID,
        organization_id=None,
        country_code="TN",
        region="Tunis",
        city="Tunis",
        postal_code="1000",
        address_line_1="Address",
        address_line_2=None,
    )
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(profile)
    session.rollback.assert_not_awaited()


def test_put_billing_profile_forbids_client_policy_fields() -> None:
    session = FakeSession()
    client = _client(session)

    try:
        response = client.put(
            "/billing/profile",
            json={
                "country_code": "TN",
                "status": "active",
                "user_id": str(uuid.uuid4()),
                "show_tunisia_payment_option": True,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    session.commit.assert_not_awaited()
