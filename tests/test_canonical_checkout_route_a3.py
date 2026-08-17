from __future__ import annotations

import inspect

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
