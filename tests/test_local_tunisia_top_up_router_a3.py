from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from processual_api.admin_marketplace import local_tunisia_top_up_router as router_module
from processual_api.admin_marketplace.authority import AdminMarketplaceAction
from processual_api.admin_marketplace.local_tunisia_top_up_router import (
    EnvironmentTunisiaExchangeRateProvider,
    LocalTunisiaTopUpPurchaseRequest,
    LocalTunisiaTopUpVerifyRequest,
    TopUpReversalRequest,
)

SUBSCRIPTION_ID = uuid.uuid4()
ORDER_ID = uuid.uuid4()


def test_local_runtime_flags_are_fail_closed_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MAESTRO_LOCAL_TUNISIA_TOP_UP_ENABLED", raising=False)
    monkeypatch.delenv("MAESTRO_LOCAL_TUNISIA_TOP_UP_ADMIN_ENABLED", raising=False)

    assert router_module._enabled("MAESTRO_LOCAL_TUNISIA_TOP_UP_ENABLED") is False
    assert router_module._enabled("MAESTRO_LOCAL_TUNISIA_TOP_UP_ADMIN_ENABLED") is False


@pytest.mark.asyncio
async def test_environment_fx_provider_rejects_missing_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "MAESTRO_TUNISIA_USD_TND_RATE",
        "MAESTRO_TUNISIA_FX_SOURCE",
        "MAESTRO_TUNISIA_FX_REFERENCE",
        "MAESTRO_TUNISIA_FX_TTL_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)

    provider = EnvironmentTunisiaExchangeRateProvider()
    with pytest.raises(RuntimeError, match="configuration is invalid"):
        await provider.quote_usd_to_tnd(requested_at=datetime(2026, 8, 7, tzinfo=UTC))


@pytest.mark.asyncio
async def test_environment_fx_provider_builds_bounded_auditable_quote(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MAESTRO_TUNISIA_USD_TND_RATE", "3.125000")
    monkeypatch.setenv("MAESTRO_TUNISIA_FX_SOURCE", "treasury_admin")
    monkeypatch.setenv("MAESTRO_TUNISIA_FX_REFERENCE", "fx-2026-08-07-001")
    monkeypatch.setenv("MAESTRO_TUNISIA_FX_TTL_SECONDS", "3600")

    requested_at = datetime(2026, 8, 7, 9, tzinfo=UTC)
    quote = await EnvironmentTunisiaExchangeRateProvider().quote_usd_to_tnd(
        requested_at=requested_at
    )

    assert quote.rate == Decimal("3.125000")
    assert quote.source == "treasury_admin"
    assert quote.reference == "fx-2026-08-07-001"
    assert quote.observed_at == requested_at
    assert quote.expires_at > requested_at


@pytest.mark.asyncio
async def test_purchase_route_stays_unavailable_until_explicitly_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MAESTRO_LOCAL_TUNISIA_TOP_UP_ENABLED", raising=False)

    with pytest.raises(HTTPException) as exc_info:
        await router_module.purchase_local_tunisia_top_up(
            body=LocalTunisiaTopUpPurchaseRequest(
                subscription_id=SUBSCRIPTION_ID,
                requested_units=10_000,
            ),
            current_user={"user_id": str(uuid.uuid4())},
            idempotency_key="idem-001",
        )

    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_verify_route_requires_sensitive_verify_payment_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MAESTRO_LOCAL_TUNISIA_TOP_UP_ADMIN_ENABLED", "true")
    seen: list[AdminMarketplaceAction] = []

    async def fake_require_admin_action(*, current_user, runtime, action):
        del current_user, runtime
        seen.append(action)
        raise router_module.AdminMarketplaceAuthorityDeniedError("denied")

    monkeypatch.setattr(router_module, "_require_admin_action", fake_require_admin_action)

    with pytest.raises(HTTPException) as exc_info:
        await router_module.verify_local_tunisia_top_up(
            order_id=ORDER_ID,
            body=LocalTunisiaTopUpVerifyRequest(
                customer_ref="customer_001",
                provider_reference="bank:txn:001",
                amount_tnd=Decimal("31.250"),
                evidence_reference="bank-evidence:001",
            ),
            current_user={"user_id": "admin", "session_id": "session"},
            runtime=SimpleNamespace(),
        )

    assert exc_info.value.status_code == 403
    assert seen == [AdminMarketplaceAction.VERIFY_PAYMENT]


@pytest.mark.asyncio
async def test_reversal_route_requires_sensitive_reconciliation_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MAESTRO_LOCAL_TUNISIA_TOP_UP_ADMIN_ENABLED", "true")
    seen: list[AdminMarketplaceAction] = []

    async def fake_require_admin_action(*, current_user, runtime, action):
        del current_user, runtime
        seen.append(action)
        raise router_module.AdminMarketplaceAuthorityDeniedError("denied")

    monkeypatch.setattr(router_module, "_require_admin_action", fake_require_admin_action)

    with pytest.raises(HTTPException) as exc_info:
        await router_module.reconcile_top_up_reversal(
            order_id=ORDER_ID,
            body=TopUpReversalRequest(
                provider_event_ref="manual:chargeback:001",
                reason_code="chargeback",
            ),
            current_user={"user_id": "admin", "session_id": "session"},
            runtime=SimpleNamespace(),
        )

    assert exc_info.value.status_code == 403
    assert seen == [AdminMarketplaceAction.RECONCILE_PAYMENT]
