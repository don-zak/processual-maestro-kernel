from __future__ import annotations

import sys
import types
import uuid

import pytest
from fastapi import HTTPException

from processual_api.billing import router as billing


def _configure_checkout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEMONSQUEEZY_API_KEY", "ls-test-key")
    monkeypatch.setenv("LEMONSQUEEZY_STORE_ID", "12345")
    monkeypatch.setenv("LEMONSQUEEZY_CHECKOUT_SUCCESS_URL", "https://maestro.example/console")
    monkeypatch.setenv("LS_VARIANT_STARTER", "111")
    monkeypatch.setenv("LS_VARIANT_STARTER_YEARLY", "112")
    monkeypatch.setenv("LS_VARIANT_PROFESSIONAL", "221")
    monkeypatch.setenv("LS_VARIANT_PROFESSIONAL_YEARLY", "222")
    monkeypatch.setenv("LS_VARIANT_ENTERPRISE", "331")
    monkeypatch.setenv("LS_VARIANT_ENTERPRISE_YEARLY", "332")


def _install_fake_httpx(
    monkeypatch: pytest.MonkeyPatch,
    *,
    status_code: int = 201,
) -> dict[str, object]:
    captured: dict[str, object] = {}

    class FakeResponse:
        def __init__(self) -> None:
            self.status_code = status_code

        def json(self) -> dict[str, object]:
            return {
                "data": {
                    "id": "checkout-123",
                    "attributes": {"url": "https://app.lemonsqueezy.com/checkout/123"},
                }
            }

    class FakeAsyncClient:
        def __init__(self, *, timeout: int) -> None:
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def post(self, url: str, *, json: dict, headers: dict) -> FakeResponse:
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            return FakeResponse()

    fake_httpx = types.SimpleNamespace(AsyncClient=FakeAsyncClient)
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)
    return captured


@pytest.mark.asyncio
async def test_checkout_uses_current_json_api_contract_and_server_catalog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_checkout(monkeypatch)
    monkeypatch.setenv("LEMONSQUEEZY_CHECKOUT_CANCEL_URL", "https://legacy.example/cancel")
    captured = _install_fake_httpx(monkeypatch)
    customer_ref = str(uuid.uuid4())

    result = await billing.create_checkout(
        {
            "plan": "professional",
            "billing": "yearly",
            "email": "buyer@example.com",
            "variant_id": "222",
        },
        current_user={"user_id": customer_ref},
    )

    assert result == {
        "url": "https://app.lemonsqueezy.com/checkout/123",
        "checkout_id": "checkout-123",
    }
    assert captured["url"] == "https://api.lemonsqueezy.com/v1/checkouts"
    headers = captured["headers"]
    assert headers["Authorization"] == "Bearer ls-test-key"
    assert headers["Content-Type"] == "application/vnd.api+json"

    data = captured["json"]["data"]
    assert data["type"] == "checkouts"
    assert data["relationships"] == {
        "store": {"data": {"type": "stores", "id": "12345"}},
        "variant": {"data": {"type": "variants", "id": "222"}},
    }
    assert data["attributes"] == {
        "checkout_data": {
            "email": "buyer@example.com",
            "custom": {"customer_ref": customer_ref},
        },
        "product_options": {"redirect_url": "https://maestro.example/console"},
    }
    serialized = repr(captured["json"])
    assert "store_id" not in serialized
    assert "variant_id" not in serialized
    assert "success_url" not in serialized
    assert "cancel_url" not in serialized
    assert "custom_data" not in serialized
    assert "customer_email" not in serialized
    assert "ls-test-key" not in serialized


@pytest.mark.asyncio
async def test_checkout_rejects_client_variant_outside_server_catalog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_checkout(monkeypatch)
    _install_fake_httpx(monkeypatch)

    with pytest.raises(HTTPException) as exc_info:
        await billing.create_checkout(
            {
                "plan": "starter",
                "billing": "monthly",
                "variant_id": "999999",
            },
            current_user={"user_id": str(uuid.uuid4())},
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Invalid checkout request."


@pytest.mark.asyncio
async def test_checkout_fails_closed_when_catalog_variant_is_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_checkout(monkeypatch)
    monkeypatch.delenv("LS_VARIANT_ENTERPRISE_YEARLY")
    _install_fake_httpx(monkeypatch)

    with pytest.raises(HTTPException) as exc_info:
        await billing.create_checkout(
            {"plan": "enterprise", "billing": "yearly"},
            current_user={"user_id": str(uuid.uuid4())},
        )

    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_checkout_omits_email_when_not_supplied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_checkout(monkeypatch)
    captured = _install_fake_httpx(monkeypatch)
    customer_ref = str(uuid.uuid4())

    await billing.create_checkout(
        {"plan": "starter", "billing": "monthly"},
        current_user={"user_id": customer_ref},
    )

    checkout_data = captured["json"]["data"]["attributes"]["checkout_data"]
    assert checkout_data == {"custom": {"customer_ref": customer_ref}}


@pytest.mark.asyncio
async def test_checkout_maps_provider_failure_without_leaking_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_checkout(monkeypatch)
    _install_fake_httpx(monkeypatch, status_code=422)

    with pytest.raises(HTTPException) as exc_info:
        await billing.create_checkout(
            {"plan": "professional", "billing": "monthly"},
            current_user={"user_id": str(uuid.uuid4())},
        )

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == "Payment provider request failed."
    assert "ls-test-key" not in exc_info.value.detail
