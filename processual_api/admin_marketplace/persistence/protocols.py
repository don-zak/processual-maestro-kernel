from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from processual_api.admin_marketplace.models import (
    AdminMarketAuditRecord,
    AdminMarketChannelEligibility,
    AdminMarketChannelSelection,
    AdminMarketCommercialDecision,
    AdminMarketEntitlementActivation,
    AdminMarketInvoice,
    AdminMarketOffer,
    AdminMarketOrder,
    AdminMarketPaymentDestination,
    AdminMarketPaymentVerification,
    AdminMarketPlan,
    AdminMarketSubscription,
    AdminMarketTrial,
)


@runtime_checkable
class PlanRepository(Protocol):
    async def get_by_id(
        self,
        plan_id: uuid.UUID,
    ) -> AdminMarketPlan | None: ...

    def add(
        self,
        plan: AdminMarketPlan,
    ) -> None: ...


@runtime_checkable
class OfferRepository(Protocol):
    async def get_by_id(
        self,
        offer_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketOffer | None: ...

    def add(
        self,
        offer: AdminMarketOffer,
    ) -> None: ...


@runtime_checkable
class SubscriptionRepository(Protocol):
    async def get_by_id(
        self,
        subscription_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketSubscription | None: ...

    def add(
        self,
        subscription: AdminMarketSubscription,
    ) -> None: ...


@runtime_checkable
class TrialRepository(Protocol):
    async def get_by_id(
        self,
        trial_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketTrial | None: ...

    def add(
        self,
        trial: AdminMarketTrial,
    ) -> None: ...


@runtime_checkable
class OrderRepository(Protocol):
    async def get_by_id(
        self,
        order_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketOrder | None: ...

    def add(
        self,
        order: AdminMarketOrder,
    ) -> None: ...


@runtime_checkable
class PaymentDestinationRepository(Protocol):
    async def list_all(
        self,
    ) -> Sequence[AdminMarketPaymentDestination]: ...

    async def get_by_id(
        self,
        destination_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketPaymentDestination | None: ...

    async def get_by_ref(
        self,
        destination_ref: str,
        *,
        for_update: bool = False,
    ) -> AdminMarketPaymentDestination | None: ...

    async def get_by_creation_idempotency_key_hash(
        self,
        key_hash: str,
        *,
        for_update: bool = False,
    ) -> AdminMarketPaymentDestination | None: ...

    async def get_active_default(
        self,
        *,
        for_update: bool = False,
    ) -> AdminMarketPaymentDestination | None: ...

    def add(
        self,
        destination: AdminMarketPaymentDestination,
    ) -> None: ...


@runtime_checkable
class PaymentVerificationRepository(Protocol):
    async def get_by_id(
        self,
        verification_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketPaymentVerification | None: ...

    def add(
        self,
        verification: AdminMarketPaymentVerification,
    ) -> None: ...


@runtime_checkable
class InvoiceRepository(Protocol):
    async def get_by_id(
        self,
        invoice_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketInvoice | None: ...

    def add(
        self,
        invoice: AdminMarketInvoice,
    ) -> None: ...


@runtime_checkable
class EntitlementActivationRepository(Protocol):
    async def get_by_id(
        self,
        activation_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketEntitlementActivation | None: ...

    def add(
        self,
        activation: AdminMarketEntitlementActivation,
    ) -> None: ...


@runtime_checkable
class ChannelEligibilityRepository(Protocol):
    async def get_by_id(
        self,
        eligibility_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketChannelEligibility | None: ...

    async def get_by_customer_ref(
        self,
        customer_ref: str,
        *,
        for_update: bool = False,
    ) -> AdminMarketChannelEligibility | None: ...

    def add(
        self,
        eligibility: AdminMarketChannelEligibility,
    ) -> None: ...


@runtime_checkable
class ChannelSelectionRepository(Protocol):
    async def get_by_id(
        self,
        selection_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketChannelSelection | None: ...

    def add(
        self,
        selection: AdminMarketChannelSelection,
    ) -> None: ...


@runtime_checkable
class CommercialDecisionRepository(Protocol):
    async def get_by_id(
        self,
        decision_id: uuid.UUID,
    ) -> AdminMarketCommercialDecision | None: ...

    def add(
        self,
        decision: AdminMarketCommercialDecision,
    ) -> None: ...


@runtime_checkable
class CommercialAuditRepository(Protocol):
    async def get_by_id(
        self,
        audit_record_id: uuid.UUID,
    ) -> AdminMarketAuditRecord | None: ...

    async def list_by_resource(
        self,
        *,
        resource_type: str,
        resource_id: str,
    ) -> Sequence[AdminMarketAuditRecord]: ...

    def append(
        self,
        audit_record: AdminMarketAuditRecord,
    ) -> None: ...


@runtime_checkable
class AdminMarketplaceUnitOfWork(Protocol):
    plans: PlanRepository
    offers: OfferRepository
    subscriptions: SubscriptionRepository
    trials: TrialRepository
    orders: OrderRepository
    payment_destinations: PaymentDestinationRepository
    payment_verifications: PaymentVerificationRepository
    invoices: InvoiceRepository
    entitlement_activations: EntitlementActivationRepository
    channel_eligibilities: ChannelEligibilityRepository
    channel_selections: ChannelSelectionRepository
    commercial_decisions: CommercialDecisionRepository
    commercial_audit: CommercialAuditRepository

    async def __aenter__(
        self,
    ) -> AdminMarketplaceUnitOfWork: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...

    async def __aexit__(
        self,
        exc_type,
        exc,
        traceback,
    ) -> None: ...


__all__ = [
    "AdminMarketplaceUnitOfWork",
    "ChannelEligibilityRepository",
    "ChannelSelectionRepository",
    "CommercialAuditRepository",
    "CommercialDecisionRepository",
    "EntitlementActivationRepository",
    "InvoiceRepository",
    "OfferRepository",
    "OrderRepository",
    "PaymentDestinationRepository",
    "PaymentVerificationRepository",
    "PlanRepository",
    "SubscriptionRepository",
    "TrialRepository",
]
