from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from processual_api.admin_marketplace.authority import authority_context
from processual_api.admin_marketplace.errors import (
    AdminMarketplaceStepUpRequiredError,
)
from processual_api.admin_marketplace.payment_destination_contracts import (
    PaymentDestinationStatus,
    PaymentDestinationType,
)
from processual_api.admin_marketplace.payment_destination_service import (
    PaymentDestinationAdministrationResult,
)
from processual_api.admin_marketplace.router import (
    PaymentDestinationCreateRequest,
    create_and_validate_payment_destination,
    get_admin_marketplace_runtime,
    router,
)
from processual_api.auth.session_router import get_identity_user

USER_ID = "11111111-1111-4111-8111-111111111111"
SESSION_ID = "22222222-2222-4222-8222-222222222222"
NOW = datetime(2026, 8, 4, 20, 0, tzinfo=UTC)
RAW_IDENTIFIER = "TN5910006035183598478831"


def _current_user() -> dict:
    return {
        "session_type": "identity_user",
        "user_id": USER_ID,
        "session_id": SESSION_ID,
    }


def _authority():
    return authority_context(
        user_id=USER_ID,
        session_id=SESSION_ID,
        platform_authorities=("platform_admin",),
        active_platform_admin=True,
        recent_mfa_step_up=True,
    )


def _body() -> PaymentDestinationCreateRequest:
    return PaymentDestinationCreateRequest(
        destination_ref="bank-primary",
        display_name="Primary Tunisian bank",
        destination_type=PaymentDestinationType.BANK_ACCOUNT,
        institution_name="Example Tunisian Bank",
        account_holder_name="Processual Maestro",
        raw_account_identifier=RAW_IDENTIFIER,
        instructions="Include the payment reference.",
    )


def _result() -> PaymentDestinationAdministrationResult:
    return PaymentDestinationAdministrationResult(
        destination_id=uuid.UUID("10000000-0000-0000-0000-000000000001"),
        destination_ref="bank-primary",
        display_name="Primary Tunisian bank",
        destination_type="bank_account",
        institution_name="Example Tunisian Bank",
        account_holder_name="Processual Maestro",
        masked_identifier="********************8831",
        country_code="TN",
        currency="TND",
        sales_channel="maestro_direct",
        status=PaymentDestinationStatus.VALIDATED,
        validation_method="structural",
        validation_reason_code="structurally_validated",
        validated_at=NOW,
        is_active=False,
        is_default=False,
        effective_at=None,
        expires_at=None,
        instructions="Include the payment reference.",
        created_at=NOW,
        updated_at=NOW,
        reason_code="payment_destination_created_and_validated",
    )


def _runtime(*, side_effect=None):
    service = SimpleNamespace(
        create_and_validate=AsyncMock(
            return_value=_result(),
            side_effect=side_effect,
        )
    )
    resolver = SimpleNamespace(resolve=AsyncMock(return_value=_authority()))
    return SimpleNamespace(
        authority_resolver=resolver,
        payment_destination_service=service,
    )


@pytest.mark.asyncio
async def test_create_and_validate_endpoint_returns_only_safe_fields() -> None:
    runtime = _runtime()

    response = await create_and_validate_payment_destination(
        body=_body(),
        current_user=_current_user(),
        runtime=runtime,
        correlation_id="correlation-create-validate-001",
        idempotency_key="destination-create-validate-001",
    )

    assert response.status is PaymentDestinationStatus.VALIDATED
    assert response.masked_identifier.endswith("8831")
    assert response.country_code == "TN"
    assert response.currency == "TND"
    assert response.sales_channel == "maestro_direct"
    serialized = response.model_dump_json()
    assert RAW_IDENTIFIER not in serialized
    assert "ciphertext" not in serialized
    assert "key_version" not in serialized

    runtime.payment_destination_service.create_and_validate.assert_awaited_once()
    command = runtime.payment_destination_service.create_and_validate.await_args.kwargs[
        "command"
    ]
    assert command.raw_account_identifier == RAW_IDENTIFIER
    assert (
        runtime.payment_destination_service.create_and_validate.await_args.kwargs[
            "correlation_id"
        ]
        == "correlation-create-validate-001"
    )
    assert (
        runtime.payment_destination_service.create_and_validate.await_args.kwargs[
            "idempotency_key"
        ]
        == "destination-create-validate-001"
    )


@pytest.mark.asyncio
async def test_create_and_validate_endpoint_exposes_mfa_step_up_signal() -> None:
    runtime = _runtime(
        side_effect=AdminMarketplaceStepUpRequiredError(
            "Recent MFA step-up is required."
        )
    )

    with pytest.raises(HTTPException) as captured:
        await create_and_validate_payment_destination(
            body=_body(),
            current_user=_current_user(),
            runtime=runtime,
            correlation_id="correlation-mfa-required",
            idempotency_key="destination-mfa-required-001",
        )

    assert captured.value.status_code == 428
    assert captured.value.detail == "Recent MFA step-up is required."


def test_router_registers_complete_payment_destination_api() -> None:
    routes = {
        (getattr(route, "path", None), frozenset(route.methods or set()))
        for route in router.routes
    }

    expected = {
        ("/admin-marketplace/payment-destinations", frozenset({"POST"})),
        ("/admin-marketplace/payment-destinations", frozenset({"GET"})),
        (
            "/admin-marketplace/payment-destinations/create-and-validate",
            frozenset({"POST"}),
        ),
        (
            "/admin-marketplace/payment-destinations/{destination_ref}/validate",
            frozenset({"POST"}),
        ),
        (
            "/admin-marketplace/payment-destinations/{destination_ref}/activate",
            frozenset({"POST"}),
        ),
        (
            "/admin-marketplace/payment-destinations/{destination_ref}/deactivate",
            frozenset({"POST"}),
        ),
        (
            "/admin-marketplace/payment-destinations/{destination_ref}/set-default",
            frozenset({"POST"}),
        ),
        (
            "/admin-marketplace/payment-destinations/default",
            frozenset({"GET"}),
        ),
        (
            "/admin-marketplace/payment-destinations/{destination_ref}",
            frozenset({"GET"}),
        ),
    }

    assert expected <= routes


def test_openapi_contract_requires_correlation_and_idempotency_headers() -> None:
    app = FastAPI()
    app.include_router(router)
    operation = app.openapi()["paths"][
        "/admin-marketplace/payment-destinations/create-and-validate"
    ]["post"]
    required_headers = {
        parameter["name"]
        for parameter in operation["parameters"]
        if parameter["in"] == "header" and parameter.get("required") is True
    }

    assert {"X-Correlation-ID", "Idempotency-Key"} <= required_headers
    assert "requestBody" in operation
    assert operation["requestBody"]["required"] is True


def test_http_boundary_sanitizes_payload_and_enforces_json_size() -> None:
    runtime = _runtime()
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_identity_user] = _current_user
    app.dependency_overrides[get_admin_marketplace_runtime] = lambda: runtime
    client = TestClient(app)
    payload = {
        "destination_ref": "bank-primary",
        "display_name": "Primary Tunisian bank",
        "destination_type": "bank_account",
        "institution_name": "Example Tunisian Bank",
        "account_holder_name": "Processual Maestro",
        "raw_account_identifier": RAW_IDENTIFIER,
        "instructions": "Include the payment reference.",
    }
    headers = {
        "X-Correlation-ID": "correlation-http-001",
        "Idempotency-Key": "destination-http-create-validate-001",
    }

    accepted = client.post(
        "/admin-marketplace/payment-destinations/create-and-validate",
        json=payload,
        headers=headers,
    )
    assert accepted.status_code == 201
    assert RAW_IDENTIFIER not in accepted.text
    assert "ciphertext" not in accepted.text

    wrong_media = client.post(
        "/admin-marketplace/payment-destinations/create-and-validate",
        content="not-json",
        headers={**headers, "Content-Type": "text/plain"},
    )
    assert wrong_media.status_code == 415
    assert RAW_IDENTIFIER not in wrong_media.text

    too_large = client.post(
        "/admin-marketplace/payment-destinations/create-and-validate",
        json={**payload, "instructions": "x" * 17_000},
        headers=headers,
    )
    assert too_large.status_code == 413
    assert RAW_IDENTIFIER not in too_large.text
