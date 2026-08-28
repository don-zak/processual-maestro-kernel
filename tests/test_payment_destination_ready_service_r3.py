from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock

import pytest

from processual_api.admin_marketplace.payment_destination_contracts import (
    PaymentDestinationStatus,
)
from processual_api.admin_marketplace.payment_destination_ready_service import (
    ReadyPaymentDestinationAdministrationService,
)
from processual_api.admin_marketplace.payment_destination_service import (
    PaymentDestinationAdministrationResult,
)


@dataclass
class _ReadyHarness:
    create: AsyncMock
    activate: AsyncMock
    set_default: AsyncMock


def _result(
    *,
    status: PaymentDestinationStatus,
    is_active: bool,
    is_default: bool,
    reason_code: str,
) -> PaymentDestinationAdministrationResult:
    from datetime import UTC, datetime
    import uuid

    now = datetime(2026, 8, 28, 8, 0, tzinfo=UTC)
    return PaymentDestinationAdministrationResult(
        destination_id=uuid.UUID("10000000-0000-0000-0000-000000000001"),
        destination_ref="bank-primary",
        display_name="Primary Tunisian bank",
        destination_type="bank_account",
        institution_name="Example Tunisian Bank",
        account_holder_name="Processual Maestro",
        masked_identifier="********************0000",
        country_code="TN",
        currency="TND",
        sales_channel="maestro_direct",
        status=status,
        validation_method="structural",
        validation_reason_code="structurally_validated",
        validated_at=now,
        is_active=is_active,
        is_default=is_default,
        effective_at=now if is_active else None,
        expires_at=None,
        instructions="Include the payment reference.",
        created_at=now,
        updated_at=now,
        reason_code=reason_code,
    )


@pytest.mark.asyncio
async def test_one_action_converges_validated_destination_to_active_default(monkeypatch) -> None:
    validated = _result(
        status=PaymentDestinationStatus.VALIDATED,
        is_active=False,
        is_default=False,
        reason_code="payment_destination_created_and_validated",
    )
    active = _result(
        status=PaymentDestinationStatus.ACTIVE,
        is_active=True,
        is_default=False,
        reason_code="payment_destination_activated",
    )
    ready = _result(
        status=PaymentDestinationStatus.ACTIVE,
        is_active=True,
        is_default=True,
        reason_code="payment_destination_default_set",
    )

    monkeypatch.setattr(
        "processual_api.admin_marketplace.payment_destination_ready_service.PaymentDestinationAdministrationService.create_and_validate",
        AsyncMock(return_value=validated),
    )
    service = object.__new__(ReadyPaymentDestinationAdministrationService)
    service.activate = AsyncMock(return_value=active)  # type: ignore[method-assign]
    service.set_default = AsyncMock(return_value=ready)  # type: ignore[method-assign]

    result = await service.create_and_validate(
        authority=object(),
        command=object(),  # type: ignore[arg-type]
        correlation_id="r3-ready-001",
        idempotency_key="r3-ready-idempotency-001",
    )

    assert result.status is PaymentDestinationStatus.ACTIVE
    assert result.is_active is True
    assert result.is_default is True
    assert result.reason_code == "payment_destination_ready_for_customers"
    service.activate.assert_awaited_once()
    service.set_default.assert_awaited_once()


@pytest.mark.asyncio
async def test_retry_of_already_ready_destination_is_convergent(monkeypatch) -> None:
    ready = _result(
        status=PaymentDestinationStatus.ACTIVE,
        is_active=True,
        is_default=True,
        reason_code="payment_destination_create_validate_idempotent",
    )
    monkeypatch.setattr(
        "processual_api.admin_marketplace.payment_destination_ready_service.PaymentDestinationAdministrationService.create_and_validate",
        AsyncMock(return_value=ready),
    )
    service = object.__new__(ReadyPaymentDestinationAdministrationService)
    service.activate = AsyncMock()  # type: ignore[method-assign]
    service.set_default = AsyncMock()  # type: ignore[method-assign]

    result = await service.create_and_validate(
        authority=object(),
        command=object(),  # type: ignore[arg-type]
        correlation_id="r3-ready-retry",
        idempotency_key="r3-ready-idempotency-001",
    )

    assert result.is_active is True
    assert result.is_default is True
    assert result.reason_code == "payment_destination_ready_for_customers"
    service.activate.assert_not_awaited()
    service.set_default.assert_not_awaited()
