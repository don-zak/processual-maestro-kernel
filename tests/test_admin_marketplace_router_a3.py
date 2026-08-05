from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from processual_api.admin_marketplace.authority import authority_context
from processual_api.admin_marketplace.commercial_read_service import (
    CommercialContractReadResult,
    CommercialOrderReadResult,
)
from processual_api.admin_marketplace.eligibility_service import (
    AdminMarketplaceEligibilityResult,
    AdminMarketplaceEligibilityState,
)
from processual_api.admin_marketplace.errors import (
    AdminMarketplaceAuthorityDeniedError,
)
from processual_api.admin_marketplace.router import (
    GENERIC_UNAVAILABLE,
    _identity_principal,
    get_admin_marketplace_eligibility,
    list_admin_marketplace_contracts,
    list_admin_marketplace_orders,
    router,
)

USER_ID = "11111111-1111-4111-8111-111111111111"
SESSION_ID = "22222222-2222-4222-8222-222222222222"


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
        recent_mfa_step_up=False,
    )


def _runtime(
    *,
    authority=None,
    result=None,
):
    resolver = SimpleNamespace(
        resolve=AsyncMock(
            return_value=authority or _authority(),
        )
    )
    service = SimpleNamespace(
        evaluate=AsyncMock(
            return_value=result
            or AdminMarketplaceEligibilityResult(
                customer_ref="customer_001",
                state=AdminMarketplaceEligibilityState.ELIGIBLE,
                visible=True,
                country_code="TN",
                address_status="confirmed",
                maestro_direct_status="eligible",
                admin_review_required=False,
                reason_code="tunisian_maestro_direct_eligible",
            )
        )
    )
    return SimpleNamespace(
        authority_resolver=resolver,
        eligibility_service=service,
    )


@pytest.mark.asyncio
async def test_eligibility_endpoint_returns_read_result() -> None:
    runtime = _runtime()

    response = await get_admin_marketplace_eligibility(
        customer_ref="customer_001",
        current_user=_current_user(),
        runtime=runtime,
    )

    assert response.customer_ref == "customer_001"
    assert response.state is AdminMarketplaceEligibilityState.ELIGIBLE
    assert response.visible is True
    assert response.country_code == "TN"
    assert response.address_status == "confirmed"
    assert response.maestro_direct_status == "eligible"
    assert response.admin_review_required is False
    assert response.reason_code == "tunisian_maestro_direct_eligible"

    runtime.authority_resolver.resolve.assert_awaited_once_with(
        user_id=USER_ID,
        session_id=SESSION_ID,
    )
    runtime.eligibility_service.evaluate.assert_awaited_once_with(
        authority=_authority(),
        customer_ref="customer_001",
    )


@pytest.mark.asyncio
async def test_endpoint_does_not_require_recent_mfa_for_catalog_read() -> None:
    runtime = _runtime(
        authority=authority_context(
            user_id=USER_ID,
            session_id=SESSION_ID,
            platform_authorities=("platform_admin",),
            active_platform_admin=True,
            recent_mfa_step_up=False,
        )
    )

    response = await get_admin_marketplace_eligibility(
        customer_ref="customer_001",
        current_user=_current_user(),
        runtime=runtime,
    )

    assert response.visible is True


@pytest.mark.asyncio
async def test_non_platform_admin_authority_is_hidden_as_forbidden() -> None:
    runtime = _runtime()
    runtime.authority_resolver.resolve.side_effect = AdminMarketplaceAuthorityDeniedError(
        "Active platform administrator authority is required."
    )

    with pytest.raises(HTTPException) as captured:
        await get_admin_marketplace_eligibility(
            customer_ref="customer_001",
            current_user=_current_user(),
            runtime=runtime,
        )

    assert captured.value.status_code == 403
    assert captured.value.detail == "Active platform administrator authority is required."
    runtime.eligibility_service.evaluate.assert_not_awaited()


@pytest.mark.asyncio
async def test_blank_customer_reference_is_bad_request() -> None:
    runtime = _runtime()
    runtime.eligibility_service.evaluate.side_effect = ValueError("customer_ref must not be blank.")

    with pytest.raises(HTTPException) as captured:
        await get_admin_marketplace_eligibility(
            customer_ref=" ",
            current_user=_current_user(),
            runtime=runtime,
        )

    assert captured.value.status_code == 400
    assert captured.value.detail == "Invalid Admin Marketplace eligibility request."


@pytest.mark.asyncio
async def test_unexpected_runtime_failure_is_service_unavailable() -> None:
    runtime = _runtime()
    runtime.eligibility_service.evaluate.side_effect = RuntimeError("database unavailable")

    with pytest.raises(HTTPException) as captured:
        await get_admin_marketplace_eligibility(
            customer_ref="customer_001",
            current_user=_current_user(),
            runtime=runtime,
        )

    assert captured.value.status_code == 503
    assert captured.value.detail == GENERIC_UNAVAILABLE


@pytest.mark.parametrize(
    "current_user",
    (
        {},
        {"user_id": USER_ID},
        {"session_id": SESSION_ID},
        {"user_id": "", "session_id": SESSION_ID},
        {"user_id": USER_ID, "session_id": ""},
    ),
)
def test_invalid_identity_principal_is_rejected(
    current_user: dict,
) -> None:
    with pytest.raises(HTTPException) as captured:
        _identity_principal(current_user)

    assert captured.value.status_code == 401
    assert captured.value.detail == "Invalid identity session."


def test_router_registers_read_only_eligibility_route() -> None:
    matches = [
        route
        for route in router.routes
        if getattr(route, "path", None) == "/admin-marketplace/eligibility/{customer_ref}"
    ]

    assert len(matches) == 1
    assert matches[0].methods == {"GET"}


@pytest.mark.asyncio
async def test_admin_commercial_read_endpoints_return_live_records() -> None:
    now = datetime(2026, 8, 5, 10, 0, tzinfo=UTC)
    runtime = _runtime()
    runtime.commercial_read_service = SimpleNamespace(
        list_orders=AsyncMock(
            return_value=(
                CommercialOrderReadResult(
                    order_ref="ord_001",
                    customer_ref="customer_001",
                    plan_ref="starter",
                    offer_ref="starter_tn_monthly",
                    billing_period="monthly",
                    status="awaiting_payment",
                    contract_status="completed",
                    payment_status="pending",
                    payment_reference="TN-34567890",
                    total_amount=Decimal("49.900"),
                    currency="TND",
                    created_at=now,
                    updated_at=now,
                ),
            )
        ),
        list_contracts=AsyncMock(
            return_value=(
                CommercialContractReadResult(
                    contract_ref="ctr_001",
                    order_ref="ord_001",
                    customer_ref="customer_001",
                    contract_version="tn-direct-v1",
                    status="completed",
                    acceptance_method="authenticated_clickwrap",
                    evidence_reference="cev_001",
                    completed_at=now,
                ),
            )
        ),
    )

    orders = await list_admin_marketplace_orders(
        current_user=_current_user(), runtime=runtime
    )
    contracts = await list_admin_marketplace_contracts(
        current_user=_current_user(), runtime=runtime
    )

    assert orders.count == 1
    assert orders.items[0].order_ref == "ord_001"
    assert contracts.count == 1
    assert contracts.items[0].contract_ref == "ctr_001"
