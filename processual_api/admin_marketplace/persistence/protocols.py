from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Protocol, runtime_checkable

from processual_api.admin_marketplace.models import (
    AdminMarketAuditRecord,
    AdminMarketChannelEligibility,
    AdminMarketChannelSelection,
    AdminMarketCommercialDecision,
    AdminMarketContract,
    AdminMarketEntitlementActivation,
    AdminMarketInvoice,
    AdminMarketOffer,
    AdminMarketOrder,
    AdminMarketPaymentDestination,
    AdminMarketPaymentEvidence,
    AdminMarketPaymentReconciliationCase,
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
        *,
        for_update: bool = False,
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

    async def get_published_direct_for_plan_code(
        self,
        *,
        plan_code: str,
        billing_period: str,
        now: datetime,
        for_update: bool = False,
    ) -> AdminMarketOffer | None: ...

    def add(
        self,
        offer: AdminMarketOffer,
    ) -> None: ...


@runtime_checkable
class SubscriptionRepository(Protocol):
    async def list_recent(
        self,
        *,
        limit: int = 100,
    ) -> Sequence[AdminMarketSubscription]: ...

    async def get_by_id(
        self,
        subscription_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketSubscription | None: ...

    async def get_active_by_customer_ref(
        self,
        customer_ref: str,
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
    async def list_recent(self, *, limit: int = 100) -> Sequence[AdminMarketOrder]: ...

    async def get_by_id(
        self,
        order_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketOrder | None: ...

    async def get_by_creation_idempotency_key_hash(
        self,
        key_hash: str,
        *,
        for_update: bool = False,
    ) -> AdminMarketOrder | None: ...

    async def get_by_ref(
        self,
        order_ref: str,
        *,
        for_update: bool = False,
    ) -> AdminMarketOrder | None: ...

    def add(
        self,
        order: AdminMarketOrder,
    ) -> None: ...


@runtime_checkable
class ContractRepository(Protocol):
    async def list_recent(
        self,
        *,
        limit: int = 100,
    ) -> Sequence[AdminMarketContract]: ...

    async def get_by_order_id(
        self,
        order_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketContract | None: ...

    async def get_by_completion_idempotency_key_hash(
        self,
        key_hash: str,
        *,
        for_update: bool = False,
    ) -> AdminMarketContract | None: ...

    def add(self, contract: AdminMarketContract) -> None: ...


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

    async def get_by_order_id(
        self,
        order_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketPaymentVerification | None: ...

    def add(
        self,
        verification: AdminMarketPaymentVerification,
    ) -> None: ...


@runtime_checkable
class PaymentEvidenceRepository(Protocol):
    async def list_recent(
        self,
        *,
        limit: int = 100,
    ) -> Sequence[AdminMarketPaymentEvidence]: ...

    async def list_by_order_id(
        self,
        order_id: uuid.UUID,
    ) -> Sequence[AdminMarketPaymentEvidence]: ...

    async def get_by_ref(
        self,
        evidence_ref: str,
        *,
        for_update: bool = False,
    ) -> AdminMarketPaymentEvidence | None: ...

    async def get_by_submission_idempotency_key_hash(
        self,
        key_hash: str,
    ) -> AdminMarketPaymentEvidence | None: ...

    def add(self, evidence: AdminMarketPaymentEvidence) -> None: ...


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
    async def list_recent(
        self,
        *,
        limit: int = 100,
    ) -> Sequence[AdminMarketEntitlementActivation]: ...

    async def get_by_id(
        self,
        activation_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketEntitlementActivation | None: ...

    async def get_by_order_id(
        self,
        order_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketEntitlementActivation | None: ...

    async def get_by_idempotency_key_hash(
        self,
        key_hash: str,
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
class PaymentReconciliationRepository(Protocol):
    async def list_recent(
        self,
        *,
        limit: int = 100,
    ) -> Sequence[AdminMarketPaymentReconciliationCase]: ...

    async def get_by_evidence_id(
        self,
        evidence_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketPaymentReconciliationCase | None: ...

    async def get_by_idempotency_key_hash(
        self,
        key_hash: str,
    ) -> AdminMarketPaymentReconciliationCase | None: ...

    def add(self, case: AdminMarketPaymentReconciliationCase) -> None: ...


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
    contracts: ContractRepository
    payment_destinations: PaymentDestinationRepository
    payment_verifications: PaymentVerificationRepository
    payment_evidence: PaymentEvidenceRepository
    payment_reconciliations: PaymentReconciliationRepository
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
    "ContractRepository",
    "EntitlementActivationRepository",
    "InvoiceRepository",
    "OfferRepository",
    "OrderRepository",
    "PaymentDestinationRepository",
    "PaymentEvidenceRepository",
    "PaymentReconciliationRepository",
    "PaymentVerificationRepository",
    "PlanRepository",
    "SubscriptionRepository",
    "TrialRepository",
]
