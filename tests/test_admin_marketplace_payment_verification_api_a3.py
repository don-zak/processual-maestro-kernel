from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from processual_api.admin_marketplace.authority import authority_context
from processual_api.admin_marketplace.errors import AdminMarketplaceStepUpRequiredError
from processual_api.admin_marketplace.payment_evidence_service import (
    AdminPaymentVerificationResult,
)
from processual_api.admin_marketplace.router import (
    PaymentVerificationRequest,
    router,
    verify_admin_marketplace_payment,
)

NOW = datetime(2026, 8, 5, 15, 0, tzinfo=UTC)


def current_user():
    return {"user_id": "admin_001", "session_id": "session_001"}


def authority():
    return authority_context(
        user_id="admin_001",
        session_id="session_001",
        platform_authorities=("platform_admin",),
        active_platform_admin=True,
        recent_mfa_step_up=True,
    )


def result():
    return AdminPaymentVerificationResult(
        verification_id=uuid.UUID("10000000-0000-0000-0000-000000000001"),
        verification_ref="pvr_001",
        evidence_ref="pev_001",
        order_ref="ord_001",
        status="verified",
        decision_reason_code="admin_exact_match_confirmed",
        decided_at=NOW,
        order_status="ready_for_activation",
        payment_status="verified",
        reason_code="payment_decision_recorded",
    )


def runtime(*, side_effect=None):
    return SimpleNamespace(
        authority_resolver=SimpleNamespace(resolve=AsyncMock(return_value=authority())),
        payment_verification_service=SimpleNamespace(decide=AsyncMock(return_value=result(), side_effect=side_effect)),
    )


@pytest.mark.asyncio
async def test_admin_payment_verification_passes_identity_authority_and_idempotency() -> None:
    active_runtime = runtime()

    response = await verify_admin_marketplace_payment(
        evidence_ref="pev_001",
        body=PaymentVerificationRequest(decision="verified", reason_code="admin_exact_match_confirmed"),
        current_user=current_user(),
        runtime=active_runtime,
        correlation_id="corr_verify_001",
        idempotency_key="payment-verify-idempotency-0001",
    )

    assert response.payment_status == "verified"
    assert response.order_status == "ready_for_activation"
    call = active_runtime.payment_verification_service.decide.await_args.kwargs
    assert call["authority"].user_id == "admin_001"
    assert call["evidence_ref"] == "pev_001"
    assert call["idempotency_key"] == "payment-verify-idempotency-0001"


@pytest.mark.asyncio
async def test_admin_payment_verification_exposes_mfa_retry_signal() -> None:
    active_runtime = runtime(side_effect=AdminMarketplaceStepUpRequiredError("Recent MFA required."))

    with pytest.raises(HTTPException) as captured:
        await verify_admin_marketplace_payment(
            evidence_ref="pev_001",
            body=PaymentVerificationRequest(decision="verified", reason_code="admin_exact_match_confirmed"),
            current_user=current_user(),
            runtime=active_runtime,
            correlation_id="corr_verify_001",
            idempotency_key="payment-verify-idempotency-0001",
        )

    assert captured.value.status_code == 428


def test_router_registers_payment_evidence_read_and_verification_routes() -> None:
    routes = {(getattr(route, "path", None), frozenset(route.methods or set())) for route in router.routes}

    assert (
        "/admin-marketplace/payment-evidence",
        frozenset({"GET"}),
    ) in routes
    assert (
        "/admin-marketplace/payment-evidence/{evidence_ref}/verify",
        frozenset({"POST"}),
    ) in routes
