from __future__ import annotations

from dataclasses import replace

from processual_api.admin_marketplace.errors import (
    PaymentDestinationConflictError,
)
from processual_api.admin_marketplace.payment_destination_contracts import (
    PaymentDestinationCreateContract,
    PaymentDestinationStatus,
)
from processual_api.admin_marketplace.payment_destination_service import (
    PaymentDestinationAdministrationResult,
    PaymentDestinationAdministrationService,
)


class ReadyPaymentDestinationAdministrationService(
    PaymentDestinationAdministrationService
):
    """Converge one admin action to an active default Tunisian payment route.

    The existing create/validate/activate/set-default operations remain available
    for diagnostics and recovery. The normal create-and-validate contract is
    upgraded here to a resumable provisioning operation so an administrator only
    needs account data plus one protected action.
    """

    async def create_and_validate(
        self,
        *,
        authority,
        command: PaymentDestinationCreateContract,
        correlation_id: str,
        idempotency_key: str | None = None,
    ) -> PaymentDestinationAdministrationResult:
        result = await super().create_and_validate(
            authority=authority,
            command=command,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )

        if result.status is PaymentDestinationStatus.VALIDATED:
            result = await self.activate(
                authority=authority,
                destination_ref=result.destination_ref,
                correlation_id=correlation_id,
            )
        elif not (
            result.status is PaymentDestinationStatus.ACTIVE
            and result.is_active
        ):
            raise PaymentDestinationConflictError(
                "Payment destination provisioning cannot resume from its current state."
            )

        if not result.is_default:
            result = await self.set_default(
                authority=authority,
                destination_ref=result.destination_ref,
                correlation_id=correlation_id,
            )

        if not (
            result.status is PaymentDestinationStatus.ACTIVE
            and result.is_active
            and result.is_default
        ):
            raise PaymentDestinationConflictError(
                "Payment destination did not reach customer-ready state."
            )

        return replace(
            result,
            reason_code="payment_destination_ready_for_customers",
        )


__all__ = ["ReadyPaymentDestinationAdministrationService"]
