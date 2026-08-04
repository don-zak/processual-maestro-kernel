from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from processual_api.admin_marketplace.direct_order_service import (
    DirectCommercialOrderResult,
    TunisiaPaymentOptionResult,
)
from processual_api.admin_marketplace.errors import DirectCommerceUnavailableError
from processual_api.billing import direct_checkout_router as checkout

USER_ID = "11111111-1111-4111-8111-111111111111"
SESSION_ID = "22222222-2222-4222-8222-222222222222"
ORGANIZATION_ID = "org_tunisia_001"
NOW = datetime(2026, 8, 4, 12, 0, tzinfo=UTC)


def current_user(*, organization_id: str | None = ORGANIZATION_ID) -> dict:
    return {
        "user_id": USER_ID,
        "session_id": SESSION_ID,
        "organization_id": organization_id,
    }


def option(*, visible: bool = True) -> TunisiaPaymentOptionResult:
    return TunisiaPaymentOptionResult(
        visible=visible,
        reason_code="tunisian_direct_payment_available",
        address_status="confirmed",
        country_code="TN",
        sales_channel="maestro_direct",
        currency="TND",
        offer_ref="starter_tn_monthly",
        offer_display_name="Starter Tunisia Monthly",
        billing_period="monthly",
        amount=Decimal("49.900"),
    )


def order() -> DirectCommercialOrderResult:
    return DirectCommercialOrderResult(
        order_id=uuid.UUID("30000000-0000-0000-0000-000000000001"),
        order_ref="ord_001",
        customer_ref=ORGANIZATION_ID,
        offer_ref="starter_tn_monthly",
        plan_ref="starter",
        billing_period="monthly",
        sales_channel="maestro_direct",
        country_code="TN",
        currency="TND",
        subtotal_amount=Decimal("49.900"),
        tax_amount=Decimal("0.000"),
        total_amount=Decimal("49.900"),
        status="awaiting_contract",
        contract_status="pending",
        payment_requirement="required",
        payment_status="pending",
        payment_reference="TN-34567890",
        payment_destination_snapshot={
            "destination_ref": "tn_bank_primary",
            "display_name": "Primary Tunisia Bank",
            "destination_type": "bank_account",
            "institution_name": "Tunisia Bank",
            "account_holder_name": "Processual Maestro",
            "masked_identifier": "****************1234",
            "instructions": "Use payment reference.",
            "country_code": "TN",
            "currency": "TND",
            "sales_channel": "maestro_direct",
            "snapshot_at": NOW.isoformat(),
        },
        created_at=NOW,
        updated_at=NOW,
        reason_code="commercial_order_created",
    )


@pytest.mark.asyncio
async def test_payment_option_uses_verified_intent_and_server_identity(monkeypatch) -> None:
    service = AsyncMock()
    service.evaluate_payment_option.return_value = option()
    monkeypatch.setattr(
        checkout,
        "_verified_preparation",
        AsyncMock(return_value={"status": "verified", "plan_id": "starter", "billing_period": "monthly"}),
    )

    response = await checkout.get_tunisia_payment_options(
        current_user=current_user(), service=service
    )

    assert response.visible is True
    assert response.address_status == "confirmed"
    service.evaluate_payment_option.assert_awaited_once_with(
        customer_ref=ORGANIZATION_ID,
        plan_ref="starter",
        billing_period="monthly",
    )


@pytest.mark.asyncio
async def test_unverified_registration_intent_hides_payment_option(monkeypatch) -> None:
    service = AsyncMock()
    monkeypatch.setattr(
        checkout,
        "_verified_preparation",
        AsyncMock(return_value={"status": "pending"}),
    )

    response = await checkout.get_tunisia_payment_options(
        current_user=current_user(), service=service
    )

    assert response.visible is False
    assert response.reason_code == "verified_registration_intent_required"
    service.evaluate_payment_option.assert_not_awaited()


@pytest.mark.asyncio
async def test_order_derives_customer_and_offer_inputs_on_server(monkeypatch) -> None:
    service = AsyncMock()
    service.create_order.return_value = order()
    monkeypatch.setattr(
        checkout,
        "_verified_preparation",
        AsyncMock(return_value={"status": "verified", "plan_id": "starter", "billing_period": "monthly"}),
    )

    response = await checkout.create_tunisia_direct_order(
        current_user=current_user(),
        service=service,
        correlation_id="corr_001",
        idempotency_key="idempotency-key-0001",
    )

    assert response.order_ref == "ord_001"
    assert response.payment_destination.masked_identifier == "****************1234"
    assert "customer_ref" not in response.model_dump()
    service.create_order.assert_awaited_once_with(
        actor_user_id=USER_ID,
        actor_session_id=SESSION_ID,
        customer_ref=ORGANIZATION_ID,
        plan_ref="starter",
        billing_period="monthly",
        correlation_id="corr_001",
        idempotency_key="idempotency-key-0001",
    )


@pytest.mark.asyncio
async def test_order_fails_closed_with_safe_reason(monkeypatch) -> None:
    service = AsyncMock()
    service.create_order.side_effect = DirectCommerceUnavailableError(
        "confirmed_customer_address_required"
    )
    monkeypatch.setattr(
        checkout,
        "_verified_preparation",
        AsyncMock(return_value={"status": "verified", "plan_id": "starter", "billing_period": "monthly"}),
    )

    with pytest.raises(HTTPException) as captured:
        await checkout.create_tunisia_direct_order(
            current_user=current_user(),
            service=service,
            correlation_id="corr_001",
            idempotency_key="idempotency-key-0001",
        )

    assert captured.value.status_code == 409
    assert captured.value.detail["reason_code"] == "confirmed_customer_address_required"
