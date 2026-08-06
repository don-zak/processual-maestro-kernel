from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from processual_api.admin_marketplace.direct_order_service import (
    TunisiaPaymentOptionResult,
)
from processual_api.billing import direct_checkout_router as checkout

USER_ID = "11111111-1111-4111-8111-111111111111"
SESSION_ID = "22222222-2222-4222-8222-222222222222"
ORGANIZATION_ID = "org_checkout_matrix"


def _identity() -> dict[str, str]:
    return {
        "user_id": USER_ID,
        "session_id": SESSION_ID,
        "organization_id": ORGANIZATION_ID,
    }


def _option(*, plan_id: str, billing_period: str) -> TunisiaPaymentOptionResult:
    return TunisiaPaymentOptionResult(
        visible=True,
        reason_code="tunisian_direct_payment_available",
        address_status="confirmed",
        country_code="TN",
        sales_channel="maestro_direct",
        currency="TND",
        offer_ref=f"{plan_id}_tn_{billing_period}",
        offer_display_name=f"{plan_id} {billing_period}",
        billing_period=billing_period,
        amount=Decimal("100.000"),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("billing_period", ("monthly", "annual"))
@pytest.mark.parametrize(
    "plan_id",
    ("academic_individual", "starter", "business", "enterprise_pilot"),
)
async def test_payment_option_is_bound_to_verified_registration_intent(
    monkeypatch,
    plan_id: str,
    billing_period: str,
) -> None:
    service = AsyncMock()
    service.evaluate_payment_option.return_value = _option(
        plan_id=plan_id,
        billing_period=billing_period,
    )
    monkeypatch.setattr(
        checkout,
        "_verified_preparation",
        AsyncMock(
            return_value={
                "status": "verified",
                "plan_id": plan_id,
                "billing_period": billing_period,
            }
        ),
    )

    response = await checkout.get_tunisia_payment_options(
        current_user=_identity(),
        service=service,
    )

    assert response.visible is True
    assert response.billing_period == billing_period
    service.evaluate_payment_option.assert_awaited_once_with(
        customer_ref=ORGANIZATION_ID,
        plan_ref=plan_id,
        billing_period=billing_period,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "preparation",
    (
        {"status": "pending_verification", "checkout_available": False},
        {"status": "no_intent", "checkout_available": False},
        {"status": "invalid_intent", "checkout_available": False},
        {"status": "verified", "billing_period": "monthly"},
        {"status": "verified", "plan_id": "starter"},
        {"status": "verified", "plan_id": None, "billing_period": "annual"},
        {"status": "verified", "plan_id": "starter", "billing_period": None},
    ),
)
async def test_order_creation_fails_closed_without_complete_verified_intent(
    monkeypatch,
    preparation: dict[str, object],
) -> None:
    service = AsyncMock()
    monkeypatch.setattr(
        checkout,
        "_verified_preparation",
        AsyncMock(return_value=preparation),
    )

    with pytest.raises(HTTPException) as captured:
        await checkout.create_tunisia_direct_order(
            current_user=_identity(),
            service=service,
            correlation_id="corr-checkout-matrix",
            idempotency_key="checkout-matrix-idempotency-0001",
        )

    assert captured.value.status_code == 409
    assert captured.value.detail["reason_code"] == "verified_registration_intent_required"
    service.create_order.assert_not_awaited()
