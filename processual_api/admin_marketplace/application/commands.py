from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from types import MappingProxyType

from processual_api.admin_marketplace.authority import (
    AdminMarketplaceAuthorityContext,
)
from processual_api.admin_marketplace.contracts import (
    ChannelEligibilityStatus,
    CommercialDecisionOutcome,
    OfferStatus,
    PaymentVerificationStatus,
    SalesChannel,
)


def _metadata(
    value: Mapping[str, str] | None,
) -> Mapping[str, str]:
    return MappingProxyType(dict(value or {}))


@dataclass(frozen=True, slots=True)
class CommercialOperationContext:
    authority: AdminMarketplaceAuthorityContext
    correlation_id: str

    def __post_init__(self) -> None:
        if not self.correlation_id.strip():
            raise ValueError("correlation_id is required.")


@dataclass(frozen=True, slots=True)
class CreatePlanCommand:
    context: CommercialOperationContext
    plan_id: uuid.UUID
    plan_code: str
    display_name: str
    entitlement_profile_ref: str
    quota_profile_ref: str
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "metadata",
            _metadata(self.metadata),
        )


@dataclass(frozen=True, slots=True)
class CreateOfferCommand:
    context: CommercialOperationContext
    offer_id: uuid.UUID
    offer_code: str
    plan_id: uuid.UUID
    display_name: str
    currency: str
    amount: Decimal
    status: OfferStatus = OfferStatus.DRAFT
    effective_at: datetime | None = None
    expires_at: datetime | None = None
    customer_specific: bool = False


@dataclass(frozen=True, slots=True)
class DecideOfferCommand:
    context: CommercialOperationContext
    offer_id: uuid.UUID
    status: OfferStatus
    decision_id: uuid.UUID
    decision_ref: str
    reason_code: str


@dataclass(frozen=True, slots=True)
class RecordChannelEligibilityCommand:
    context: CommercialOperationContext
    eligibility_id: uuid.UUID
    customer_ref: str
    country_code: str | None
    maestro_direct_status: ChannelEligibilityStatus
    lemon_squeezy_status: ChannelEligibilityStatus
    customer_choice_allowed: bool
    admin_review_required: bool
    restriction_reason: str | None = None
    automatic_activation_allowed: bool = False


@dataclass(frozen=True, slots=True)
class RecordChannelSelectionCommand:
    context: CommercialOperationContext
    selection_id: uuid.UUID
    customer_ref: str
    selected_channel: SalesChannel
    eligible_channels: frozenset[SalesChannel]
    customer_consented: bool = True
    administrator_override_reason: str | None = None


@dataclass(frozen=True, slots=True)
class CreateOrderCommand:
    context: CommercialOperationContext
    order_id: uuid.UUID
    order_ref: str
    customer_ref: str
    offer_id: uuid.UUID
    selected_channel: SalesChannel


@dataclass(frozen=True, slots=True)
class DecidePaymentVerificationCommand:
    context: CommercialOperationContext
    verification_id: uuid.UUID
    verification_ref: str
    order_id: uuid.UUID
    status: PaymentVerificationStatus
    safe_reference: str | None
    decision_id: uuid.UUID
    decision_ref: str
    reason_code: str


@dataclass(frozen=True, slots=True)
class DecideEntitlementActivationCommand:
    context: CommercialOperationContext
    activation_id: uuid.UUID
    activation_ref: str
    customer_ref: str
    subscription_id: uuid.UUID
    entitlement_profile_ref: str
    outcome: CommercialDecisionOutcome
    decision_id: uuid.UUID
    decision_ref: str
    reason_code: str
    automatic_activation_allowed: bool = False


__all__ = [
    "CommercialOperationContext",
    "CreateOfferCommand",
    "CreateOrderCommand",
    "CreatePlanCommand",
    "DecideEntitlementActivationCommand",
    "DecideOfferCommand",
    "DecidePaymentVerificationCommand",
    "RecordChannelEligibilityCommand",
    "RecordChannelSelectionCommand",
]
