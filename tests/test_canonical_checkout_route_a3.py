from __future__ import annotations

import inspect

import httpx
import pytest
from fastapi import HTTPException

from processual_api.billing import router as billing_router
from processual_api.billing.canonical_checkout_resolution import (
    CanonicalCheckoutResolution,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    (
        {"variant_id": "12345", "offer_ref": "starter-monthly"},
        {"plan": "starter", "offer_ref": "starter-monthly"},
        {"billing": "annual", "offer_ref": "starter-monthly"},
    ),
)
async def test_checkout_route_rejects_legacy_identity_before_db_or_env(
    monkeypatch: pytest.MonkeyPatch,
    body: dict[str, str],
) -> None:
    def fail_session_factory():
        raise AssertionError("legacy checkout input must not reach the database")

    def fail_required_environment(name: str) -> str:
        raise AssertionError(f"legacy checkout input must not read {name}")

    monkeypatch.setattr(billing_router, "get_session_factory", fail_session_factory)
    monkeypatch.setattr(
        billing_router,
        "_required_environment",
        fail_required_environment,
    )

    with pytest.raises(HTTPException) as captured:
        await billing_router.create_checkout(
            body,
            current_user={"user_id": "00000000-0000-0000-0000-000000000001"},
        )

    assert captured.value.status_code == 400
    assert captured.value.detail == "Invalid checkout request."


@pytest.mark.asyncio
async def test_checkout_route_requires_offer_ref_before_db_or_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_session_factory():
        raise AssertionError("missing offer_ref must not reach the database")

    def fail_required_environment(name: str) -> str:
        raise AssertionError(f"missing offer_ref must not read {name}")

    monkeypatch.setattr(billing_router, "get_session_factory", fail_session_factory)
    monkeypatch.setattr(
        billing_router,
        "_required_environment",
        fail_required_environment,
    )

    with pytest.raises(HTTPException) as captured:
        await billing_router.create_checkout(
            {"email": "buyer@example.com"},
            current_user={"user_id": "00000000-0000-0000-0000-000000000001"},
        )

    assert captured.value.status_code == 400
    assert captured.value.detail == "Invalid checkout request."


@pytest.mark.asyncio
async def test_checkout_route_uses_resolved_provider_variant_and_offer_ref(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class SessionContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, traceback):
            return False

    captured_request: dict[str, object] = {}

    async def fake_resolve(*, session, offer_ref: str):
        del session
        assert offer_ref == "starter-monthly"
        return CanonicalCheckoutResolution(
            offer_ref="starter-monthly",
            provider_variant_id="67890",
        )

    def fake_required_environment(name: str) -> str:
        return {
            "LEMONSQUEEZY_API_KEY": "secret",
            "LEMONSQUEEZY_STORE_ID": "24680",
            "LEMONSQUEEZY_CHECKOUT_SUCCESS_URL": "https://example.com/success",
            "LEMONSQUEEZY_CHECKOUT_CANCEL_URL": "https://example.com/cancel",
        }[name]

    class FakeResponse:
        status_code = 201

        def json(self) -> dict[str, object]:
            return {
                "data": {
                    "id": "checkout-1",
                    "attributes": {"url": "https://example.com/checkout"},
                }
            }

    class FakeAsyncClient:
        def __init__(self, *, timeout: int) -> None:
            assert timeout == 15

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def post(self, url: str, *, json, headers):
            captured_request.update(
                {"url": url, "json": json, "headers": headers}
            )
            return FakeResponse()

    monkeypatch.setattr(
        billing_router,
        "get_session_factory",
        lambda: lambda: SessionContext(),
    )
    monkeypatch.setattr(
        billing_router,
        "resolve_canonical_checkout_in_session",
        fake_resolve,
    )
    monkeypatch.setattr(
        billing_router,
        "_required_environment",
        fake_required_environment,
    )
    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    result = await billing_router.create_checkout(
        {"offer_ref": "Starter-Monthly", "email": " buyer@example.com "},
        current_user={"user_id": "00000000-0000-0000-0000-000000000001"},
    )

    attributes = captured_request["json"]["data"]["attributes"]
    assert attributes["variant_id"] == 67890
    assert attributes["custom_data"] == {
        "customer_ref": "00000000-0000-0000-0000-000000000001",
        "offer_ref": "starter-monthly",
    }
    assert attributes["customer_email"] == "buyer@example.com"
    assert result == {
        "url": "https://example.com/checkout",
        "checkout_id": "checkout-1",
    }


def test_checkout_route_has_no_legacy_variant_authority() -> None:
    source = inspect.getsource(billing_router)
    checkout_source = inspect.getsource(billing_router.create_checkout)

    assert "_VARIANTS" not in source
    assert "LS_VARIANT_" not in source
    assert 'body.get("variant_id")' not in checkout_source
    assert 'body.get("plan")' not in checkout_source
    assert 'body.get("billing")' not in checkout_source
    assert "require_canonical_checkout_request" in checkout_source
    assert "resolve_canonical_checkout_in_session" in checkout_source
    assert "resolution.provider_variant_id" in checkout_source
