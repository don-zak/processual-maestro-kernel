from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from fastapi import HTTPException

from processual_api.billing import router as billing_router


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
async def test_checkout_route_requires_session_authority_before_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_session_factory():
        raise AssertionError("missing session authority must fail before DB access")

    monkeypatch.setattr(billing_router, "get_session_factory", fail_session_factory)

    with pytest.raises(HTTPException) as captured:
        await billing_router.create_checkout(
            {"offer_ref": "starter-monthly"},
            current_user={
                "user_id": "00000000-0000-0000-0000-000000000001",
            },
            idempotency_key="checkout-test-key-0001",
        )

    assert captured.value.status_code == 403
    assert captured.value.detail == "Billing access denied."


@pytest.mark.asyncio
async def test_checkout_route_requires_bounded_idempotency_key_before_db(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_session_factory():
        raise AssertionError("invalid idempotency key must fail before DB access")

    monkeypatch.setattr(billing_router, "get_session_factory", fail_session_factory)

    with pytest.raises(HTTPException) as captured:
        await billing_router.create_checkout(
            {"offer_ref": "starter-monthly"},
            current_user={
                "user_id": "00000000-0000-0000-0000-000000000001",
                "session_id": "session-1",
            },
            idempotency_key="short",
        )

    assert captured.value.status_code == 400
    assert captured.value.detail == "A valid Idempotency-Key header is required."


def test_checkout_route_uses_current_canonical_order_authority() -> None:
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
    assert "_checkout_session_id" in checkout_source
    assert "build_lemon_checkout_order_authority" in checkout_source
    assert "order_authority.prepare" in checkout_source
    assert "idempotency_key=normalized_idempotency_key" in checkout_source
    assert "final_resolution != resolution" in checkout_source
    assert '"order_ref": provider_checkout.order_ref' in checkout_source


def test_production_env_has_no_legacy_checkout_variant_keys() -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env.production.example"
    legacy_keys = {
        line.split("=", 1)[0]
        for line in env_path.read_text(encoding="utf-8-sig").splitlines()
        if line.startswith("LS_VARIANT_")
    }

    assert legacy_keys == set()
