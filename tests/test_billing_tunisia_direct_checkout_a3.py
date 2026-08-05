from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from processual_api.admin_marketplace.contract_service import (
    ContractCompletionResult,
)
from processual_api.admin_marketplace.direct_order_service import (
    DirectCommercialOrderResult,
    TunisiaPaymentOptionResult,
)
from processual_api.admin_marketplace.errors import DirectCommerceUnavailableError
from processual_api.admin_marketplace.payment_evidence_service import (
    CustomerPaymentReportResult,
)
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
        contract_version="tn-direct-v1",
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


def completed_contract() -> ContractCompletionResult:
    return ContractCompletionResult(
        contract_id=uuid.UUID("40000000-0000-0000-0000-000000000001"),
        contract_ref="ctr_001",
        order_ref="ord_001",
        contract_version="tn-direct-v1",
        status="completed",
        acceptance_method="authenticated_clickwrap",
        evidence_reference="cev_001",
        completed_at=NOW,
        order_status="awaiting_payment",
        payment_status="pending",
        payment_reference="TN-34567890",
        payment_destination_snapshot=order().payment_destination_snapshot,
        reason_code="contract_completed",
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

    response = await checkout.get_tunisia_payment_options(current_user=current_user(), service=service)

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

    response = await checkout.get_tunisia_payment_options(current_user=current_user(), service=service)

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
    service.create_order.side_effect = DirectCommerceUnavailableError("confirmed_customer_address_required")
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


@pytest.mark.asyncio
async def test_contract_completion_derives_customer_from_identity() -> None:
    service = AsyncMock()
    service.complete_authenticated_clickwrap.return_value = completed_contract()

    response = await checkout.complete_tunisia_direct_contract(
        order_ref="ord_001",
        body=checkout.ContractCompletionRequest(
            accepted=True,
            contract_version="tn-direct-v1",
        ),
        current_user=current_user(),
        service=service,
        correlation_id="corr_contract_001",
        idempotency_key="contract-idempotency-0001",
    )

    assert response.status == "completed"
    assert response.order_status == "awaiting_payment"
    assert response.payment_destination.masked_identifier == "****************1234"
    service.complete_authenticated_clickwrap.assert_awaited_once_with(
        actor_user_id=USER_ID,
        actor_session_id=SESSION_ID,
        customer_ref=ORGANIZATION_ID,
        order_ref="ord_001",
        contract_version="tn-direct-v1",
        correlation_id="corr_contract_001",
        idempotency_key="contract-idempotency-0001",
    )


@pytest.mark.asyncio
async def test_contract_completion_requires_explicit_acceptance() -> None:
    service = AsyncMock()

    with pytest.raises(HTTPException) as captured:
        await checkout.complete_tunisia_direct_contract(
            order_ref="ord_001",
            body=checkout.ContractCompletionRequest(
                accepted=False,
                contract_version="tn-direct-v1",
            ),
            current_user=current_user(),
            service=service,
            correlation_id="corr_contract_001",
            idempotency_key="contract-idempotency-0001",
        )

    assert captured.value.status_code == 400
    service.complete_authenticated_clickwrap.assert_not_awaited()


@pytest.mark.asyncio
async def test_payment_report_derives_customer_identity_and_returns_no_raw_reference() -> None:
    service = AsyncMock()
    service.report.return_value = CustomerPaymentReportResult(
        evidence_id=uuid.UUID("50000000-0000-0000-0000-000000000001"),
        evidence_ref="pev_001",
        order_ref="ord_001",
        source_type="customer_report",
        status="matched",
        actual_amount=Decimal("49.900"),
        currency="TND",
        safe_source_reference="***7788",
        reference_matched=True,
        amount_matched=True,
        currency_matched=True,
        destination_matched=True,
        match_reason_code="customer_report_exact_match",
        reported_at=NOW,
        order_status="awaiting_payment",
        payment_status="customer_reported",
        reason_code="payment_report_recorded",
    )

    response = await checkout.report_tunisia_direct_payment(
        order_ref="ord_001",
        body=checkout.CustomerPaymentReportRequest(
            actual_amount=Decimal("49.900"),
            currency="TND",
            payment_reference="TN-34567890",
            transfer_reference="BANK-TRANSFER-7788",
        ),
        current_user=current_user(),
        service=service,
        correlation_id="corr_report_001",
        idempotency_key="payment-report-idempotency-0001",
    )

    assert response.payment_status == "customer_reported"
    assert response.status == "matched"
    serialized = response.model_dump_json()
    assert "BANK-TRANSFER-7788" not in serialized
    assert "***7788" in serialized
    service.report.assert_awaited_once_with(
        actor_user_id=USER_ID,
        actor_session_id=SESSION_ID,
        customer_ref=ORGANIZATION_ID,
        order_ref="ord_001",
        actual_amount=Decimal("49.900"),
        currency="TND",
        payment_reference="TN-34567890",
        transfer_reference="BANK-TRANSFER-7788",
        correlation_id="corr_report_001",
        idempotency_key="payment-report-idempotency-0001",
    )
