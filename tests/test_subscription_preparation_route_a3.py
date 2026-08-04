import asyncio
import uuid

import pytest
from fastapi import HTTPException

import processual_api.billing.router as billing_router


def test_billing_router_exposes_subscription_preparation_route():
    paths = {route.path for route in billing_router.router.routes}

    assert "/billing/subscription-preparation" in paths


def test_subscription_preparation_rejects_invalid_identity_principal():
    with pytest.raises(HTTPException) as error:
        asyncio.run(
            billing_router.get_subscription_preparation(
                {"session_type": "identity_user"}
            )
        )

    assert error.value.status_code == 401
    assert error.value.detail == "Invalid identity session."


def test_subscription_preparation_uses_authenticated_user_id(
    monkeypatch,
):
    expected_user_id = uuid.UUID(
        "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    )
    captured = {}

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return None

    def fake_session_factory():
        return FakeSession()

    async def fake_builder(*, repository, user_id):
        captured["repository"] = repository
        captured["user_id"] = user_id
        return {
            "status": "verified",
            "checkout_available": False,
        }

    monkeypatch.setattr(
        billing_router,
        "get_session_factory",
        lambda: fake_session_factory,
    )
    monkeypatch.setattr(
        billing_router,
        "build_subscription_preparation",
        fake_builder,
    )

    result = asyncio.run(
        billing_router.get_subscription_preparation(
            {
                "session_type": "identity_user",
                "user_id": str(expected_user_id),
                "session_id": (
                    "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
                ),
            }
        )
    )

    assert captured["user_id"] == expected_user_id
    assert result == {
        "status": "verified",
        "checkout_available": False,
    }


def test_subscription_preparation_fails_closed_when_database_unavailable(
    monkeypatch,
):
    def unavailable():
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(
        billing_router,
        "get_session_factory",
        unavailable,
    )

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            billing_router.get_subscription_preparation(
                {
                    "session_type": "identity_user",
                    "user_id": (
                        "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
                    ),
                    "session_id": (
                        "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
                    ),
                }
            )
        )

    assert error.value.status_code == 503
    assert (
        error.value.detail
        == "Subscription preparation is unavailable."
    )
