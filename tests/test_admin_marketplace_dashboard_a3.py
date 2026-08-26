from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from processual_api.admin_marketplace.dashboard_read_service import (
    AdminMarketplaceDashboardReadResult,
    DashboardChannelReadResult,
    DashboardQuotaReadResult,
    DashboardSubscriptionReadResult,
    DashboardTrialReadResult,
    DashboardVerifiedOrderValueReadResult,
)
from processual_api.admin_marketplace.dashboard_router import (
    get_admin_marketplace_dashboard,
)
from processual_api.admin_marketplace.errors import (
    AdminMarketplaceAuthorityDeniedError,
)

NOW = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)


def _result() -> AdminMarketplaceDashboardReadResult:
    return AdminMarketplaceDashboardReadResult(
        trials=(
            DashboardTrialReadResult(
                trial_ref="trial_001",
                customer_ref="customer_001",
                plan_code="pilot",
                status="active",
                starts_at=NOW,
                ends_at=NOW,
            ),
        ),
        subscriptions=(
            DashboardSubscriptionReadResult(
                subscription_ref="sub_001",
                customer_ref="customer_001",
                plan_code="pilot",
                status="active",
                starts_at=NOW,
                ends_at=None,
            ),
        ),
        quotas=(
            DashboardQuotaReadResult(
                subscription_id="11111111-1111-4111-8111-111111111111",
                customer_ref="customer_001",
                plan_code="pilot",
                metric_code="maestro_units",
                period_start=NOW,
                period_end=NOW,
                base_limit_units=100,
                rollover_units=10,
                top_up_units=5,
                used_units=20,
                remaining_units=95,
                rollover_status="available",
            ),
        ),
        channels=(
            DashboardChannelReadResult(
                customer_ref="customer_001",
                country_code="TN",
                address_status="confirmed",
                maestro_direct_status="eligible",
                lemon_squeezy_status="eligible",
                customer_choice_allowed=True,
                admin_review_required=False,
                restriction_reason=None,
                automatic_activation_allowed=True,
                selected_channel="lemon_squeezy",
                customer_consented=True,
                selection_recorded_at=NOW,
            ),
        ),
        verified_order_values=(
            DashboardVerifiedOrderValueReadResult(
                currency="TND",
                verified_order_count=2,
                verified_order_value=Decimal("99.800"),
            ),
        ),
    )


@pytest.mark.asyncio
async def test_dashboard_uses_identity_authority_and_returns_safe_read_model() -> None:
    authority = object()
    resolver = AsyncMock()
    resolver.resolve.return_value = authority
    runtime = SimpleNamespace(authority_resolver=resolver)
    service = AsyncMock()
    service.read.return_value = _result()

    response = await get_admin_marketplace_dashboard(
        current_user={"user_id": "user-001", "session_id": "session-001"},
        runtime=runtime,
        service=service,
    )

    resolver.resolve.assert_awaited_once_with(
        user_id="user-001",
        session_id="session-001",
    )
    service.read.assert_awaited_once_with(authority=authority)
    assert response["trials"][0]["trial_ref"] == "trial_001"
    assert response["quotas"][0]["remaining_units"] == 95
    assert response["channels"][0]["selected_channel"] == "lemon_squeezy"
    assert response["verified_order_values"][0]["verified_order_value"] == Decimal("99.800")
    serialized = repr(response).lower()
    assert "raw_account_identifier" not in serialized
    assert "token" not in serialized
    assert "secret" not in serialized


@pytest.mark.asyncio
async def test_dashboard_denies_missing_marketplace_authority() -> None:
    resolver = AsyncMock()
    resolver.resolve.side_effect = AdminMarketplaceAuthorityDeniedError("denied")
    runtime = SimpleNamespace(authority_resolver=resolver)
    service = AsyncMock()

    with pytest.raises(HTTPException) as captured:
        await get_admin_marketplace_dashboard(
            current_user={"user_id": "user-001", "session_id": "session-001"},
            runtime=runtime,
            service=service,
        )

    assert captured.value.status_code == 403
    service.read.assert_not_awaited()


@pytest.mark.asyncio
async def test_dashboard_rejects_incomplete_identity_before_read() -> None:
    resolver = AsyncMock()
    runtime = SimpleNamespace(authority_resolver=resolver)
    service = AsyncMock()

    with pytest.raises(HTTPException) as captured:
        await get_admin_marketplace_dashboard(
            current_user={"user_id": "user-001"},
            runtime=runtime,
            service=service,
        )

    assert captured.value.status_code == 401
    resolver.resolve.assert_not_awaited()
    service.read.assert_not_awaited()
