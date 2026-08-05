from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from processual_api.admin_marketplace.authority import (
    AdminMarketplaceAction,
    AdminMarketplaceAuthorityContext,
    require_admin_marketplace_authority,
)
from processual_api.admin_marketplace.persistence.protocols import (
    AdminMarketplaceUnitOfWork,
)


@dataclass(frozen=True, slots=True)
class CommercialOrderReadResult:
    order_ref: str
    customer_ref: str
    plan_ref: str
    offer_ref: str
    billing_period: str
    status: str
    contract_status: str
    payment_status: str
    payment_reference: str | None
    total_amount: Decimal
    currency: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class CommercialContractReadResult:
    contract_ref: str
    order_ref: str
    customer_ref: str
    contract_version: str
    status: str
    acceptance_method: str
    evidence_reference: str
    completed_at: datetime


@dataclass(frozen=True, slots=True)
class PaymentEvidenceReadResult:
    evidence_ref: str
    order_ref: str
    customer_ref: str
    source_type: str
    status: str
    actual_amount: Decimal
    currency: str
    safe_source_reference: str
    reference_matched: bool
    amount_matched: bool
    currency_matched: bool
    destination_matched: bool
    match_reason_code: str
    reported_at: datetime


class AdminMarketplaceCommercialReadService:
    """Read-only, authority-gated Admin Market order and contract views."""

    def __init__(
        self,
        *,
        unit_of_work_factory: Callable[[], AdminMarketplaceUnitOfWork],
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def list_orders(
        self,
        *,
        authority: AdminMarketplaceAuthorityContext,
        limit: int = 100,
    ) -> tuple[CommercialOrderReadResult, ...]:
        require_admin_marketplace_authority(
            context=authority,
            action=AdminMarketplaceAction.VIEW_CATALOG,
        )
        async with self._unit_of_work_factory() as unit:
            orders = await unit.orders.list_recent(limit=limit)
        return tuple(
            CommercialOrderReadResult(
                order_ref=order.order_ref,
                customer_ref=order.customer_ref,
                plan_ref=str(order.offer_snapshot.get("plan_ref", "")),
                offer_ref=str(order.offer_snapshot.get("offer_ref", "")),
                billing_period=order.billing_period,
                status=order.status,
                contract_status=order.contract_status,
                payment_status=order.payment_status,
                payment_reference=order.payment_reference,
                total_amount=Decimal(order.total_amount),
                currency=order.currency,
                created_at=order.created_at,
                updated_at=order.updated_at,
            )
            for order in orders
        )

    async def list_contracts(
        self,
        *,
        authority: AdminMarketplaceAuthorityContext,
        limit: int = 100,
    ) -> tuple[CommercialContractReadResult, ...]:
        require_admin_marketplace_authority(
            context=authority,
            action=AdminMarketplaceAction.VIEW_CATALOG,
        )
        async with self._unit_of_work_factory() as unit:
            contracts = await unit.contracts.list_recent(limit=limit)
            order_refs = {}
            for contract in contracts:
                order = await unit.orders.get_by_id(contract.order_id)
                order_refs[contract.order_id] = "" if order is None else order.order_ref
        return tuple(
            CommercialContractReadResult(
                contract_ref=contract.contract_ref,
                order_ref=order_refs[contract.order_id],
                customer_ref=contract.customer_ref,
                contract_version=contract.contract_version,
                status=contract.status,
                acceptance_method=contract.acceptance_method,
                evidence_reference=contract.evidence_reference,
                completed_at=contract.completed_at,
            )
            for contract in contracts
        )

    async def list_payment_evidence(
        self,
        *,
        authority: AdminMarketplaceAuthorityContext,
        limit: int = 100,
    ) -> tuple[PaymentEvidenceReadResult, ...]:
        require_admin_marketplace_authority(
            context=authority,
            action=AdminMarketplaceAction.VIEW_CATALOG,
        )
        async with self._unit_of_work_factory() as unit:
            evidence_items = await unit.payment_evidence.list_recent(limit=limit)
            order_refs = {}
            for evidence in evidence_items:
                order = await unit.orders.get_by_id(evidence.order_id)
                order_refs[evidence.order_id] = "" if order is None else order.order_ref
        return tuple(
            PaymentEvidenceReadResult(
                evidence_ref=evidence.evidence_ref,
                order_ref=order_refs[evidence.order_id],
                customer_ref=evidence.customer_ref,
                source_type=evidence.source_type,
                status=evidence.status,
                actual_amount=Decimal(evidence.actual_amount),
                currency=evidence.currency,
                safe_source_reference=evidence.safe_source_reference,
                reference_matched=evidence.reference_matched,
                amount_matched=evidence.amount_matched,
                currency_matched=evidence.currency_matched,
                destination_matched=evidence.destination_matched,
                match_reason_code=evidence.match_reason_code,
                reported_at=evidence.reported_at,
            )
            for evidence in evidence_items
        )


__all__ = [
    "AdminMarketplaceCommercialReadService",
    "CommercialContractReadResult",
    "CommercialOrderReadResult",
    "PaymentEvidenceReadResult",
]
