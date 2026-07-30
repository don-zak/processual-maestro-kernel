"""Atomic bridge from approved commercial top-up to entitlement ledger.

The bridge shares one SQLAlchemy transaction across commercial top-up records,
immutable audit records, entitlement ledger append, and balance CAS. It remains
fail-closed and disconnected from checkout, webhooks, and runtime composition.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Final, Protocol

from processual_api.billing.commercial_entitlement_grant_posting_service import (
    EntitlementGrantPostingConflictError,
    EntitlementGrantPostingResult,
    TopUpGrantCommand,
)
from processual_api.billing.commercial_entitlement_ledger_contracts import (
    EntitlementBalanceSnapshot,
    EntitlementLedgerEntry,
    LedgerEntryType,
)
from processual_api.billing.commercial_entitlement_ledger_persistence_contracts import (
    BalanceCompareAndSwapRequest,
    EntitlementLedgerUnitOfWork,
    LedgerAppendRequest,
)
from processual_api.billing.commercial_settings_top_up_checkout_contracts import (
    TopUpCheckoutChannel,
)
from processual_api.billing.commercial_top_up_application_service import (
    AuditRepository,
    GrantRepository,
    OrderRepository,
    PaymentRepository,
    TopUpApplicationConflictError,
    TopUpApplicationNotFoundError,
    TopUpApplicationServiceDisabledError,
)
from processual_api.billing.commercial_top_up_models import (
    CommercialTopUpAuditRecord,
    CommercialTopUpGrant,
    CommercialTopUpOrder,
    CommercialTopUpPaymentEvidence,
)
from processual_api.billing.commercial_top_up_order_grant_contracts import (
    PaymentVerificationContract,
    PaymentVerificationOutcome,
    TopUpOrderContract,
    TopUpOrderState,
    UnitGrantOutcome,
    decide_unit_grant,
)

TOP_UP_ENTITLEMENT_BRIDGE_VERSION: Final = "2026-07-group2-top-up-entitlement-bridge-v1"
TOP_UP_ENTITLEMENT_BRIDGE_STATUS: Final = "draft_review"
TOP_UP_ENTITLEMENT_BRIDGE_ENABLED: Final = False
TOP_UP_ENTITLEMENT_BRIDGE_WRITES_ENABLED: Final = False
TOP_UP_ENTITLEMENT_BRIDGE_RUNTIME_WIRING_ENABLED: Final = False
TOP_UP_ENTITLEMENT_BRIDGE_COMMERCIAL_ACTIVATION_ENABLED: Final = False


@dataclass(frozen=True, slots=True)
class TopUpEntitlementBridgePolicy:
    enabled: bool = TOP_UP_ENTITLEMENT_BRIDGE_ENABLED
    writes_enabled: bool = TOP_UP_ENTITLEMENT_BRIDGE_WRITES_ENABLED
    runtime_wiring_enabled: bool = TOP_UP_ENTITLEMENT_BRIDGE_RUNTIME_WIRING_ENABLED
    commercial_activation_enabled: bool = TOP_UP_ENTITLEMENT_BRIDGE_COMMERCIAL_ACTIVATION_ENABLED


@dataclass(frozen=True, slots=True)
class PostApprovedTopUpCommand:
    tenant_id: uuid.UUID
    order_id: uuid.UUID
    provider_reference: str
    verified_amount: Decimal
    verified_currency: str
    immutable_evidence_reference: str
    settlement_reference: str
    actor_reference: str
    occurred_at: datetime

    def __post_init__(self) -> None:
        if not self.provider_reference.strip():
            raise ValueError("provider_reference must not be blank")
        if self.verified_amount <= 0:
            raise ValueError("verified_amount must be positive")
        if len(self.verified_currency.strip().upper()) != 3:
            raise ValueError("verified_currency must be ISO-4217")
        if not self.immutable_evidence_reference.strip():
            raise ValueError("immutable_evidence_reference must not be blank")
        if not self.settlement_reference.strip():
            raise ValueError("settlement_reference must not be blank")
        if not self.actor_reference.strip():
            raise ValueError("actor_reference must not be blank")
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class TopUpEntitlementBridgeResult:
    order_id: uuid.UUID
    ledger_entry_id: uuid.UUID
    duplicate: bool
    committed: bool
    available_units: int
    resulting_balance_version: int


class AtomicTopUpEntitlementUnitOfWork(
    EntitlementLedgerUnitOfWork,
    Protocol,
):
    orders: OrderRepository
    payments: PaymentRepository
    grants: GrantRepository
    audit: AuditRepository

    async def __aenter__(
        self,
    ) -> AtomicTopUpEntitlementUnitOfWork: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None: ...


AtomicUnitOfWorkFactory = Callable[
    [],
    AbstractAsyncContextManager[AtomicTopUpEntitlementUnitOfWork],
]


class CommercialTopUpEntitlementBridgeService:
    def __init__(
        self,
        *,
        unit_of_work_factory: AtomicUnitOfWorkFactory,
        policy: TopUpEntitlementBridgePolicy | None = None,
        entry_id_factory: Callable[[], uuid.UUID] = uuid.uuid4,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._policy = policy or TopUpEntitlementBridgePolicy()
        self._entry_id_factory = entry_id_factory

    async def post_approved_top_up(
        self,
        command: PostApprovedTopUpCommand,
    ) -> TopUpEntitlementBridgeResult:
        self._require(self._policy.enabled, "top-up entitlement bridge is disabled")
        self._require(
            self._policy.writes_enabled,
            "top-up entitlement bridge writes are disabled",
        )

        async with self._unit_of_work_factory() as unit:
            try:
                order = await unit.orders.get_by_id(
                    command.order_id,
                    for_update=True,
                )
                if order is None:
                    raise TopUpApplicationNotFoundError("top-up order was not found")

                existing_payment = await unit.payments.get_by_provider_reference(command.provider_reference)
                existing_grant = await unit.grants.get_for_order(
                    command.order_id,
                    for_update=True,
                )
                grant_key = f"top-up-grant:{order.id}:{order.idempotency_key}"
                existing_ledger = await unit.ledger.get_by_idempotency_key(
                    tenant_id=command.tenant_id,
                    subscription_id=order.subscription_id,
                    idempotency_key=grant_key,
                )

                if existing_payment is not None:
                    if existing_payment.order_id != command.order_id:
                        raise TopUpApplicationConflictError(
                            "provider payment reference belongs to another top-up order"
                        )
                    if existing_grant is None or existing_ledger is None:
                        raise TopUpApplicationConflictError("top-up replay found incomplete atomic posting")
                    stored = await unit.balances.get_snapshot(
                        tenant_id=command.tenant_id,
                        subscription_id=order.subscription_id,
                    )
                    if stored is None:
                        raise TopUpApplicationConflictError("top-up replay has no entitlement balance")
                    snapshot, version = stored
                    await unit.commit()
                    return TopUpEntitlementBridgeResult(
                        order_id=order.id,
                        ledger_entry_id=existing_ledger.entry_id,
                        duplicate=True,
                        committed=False,
                        available_units=snapshot.available_units,
                        resulting_balance_version=version,
                    )

                payment_contract = PaymentVerificationContract(
                    order_id=command.order_id,
                    provider_reference=command.provider_reference,
                    outcome=PaymentVerificationOutcome.VERIFIED,
                    verified_amount=command.verified_amount,
                    verified_currency=(command.verified_currency.strip().upper()),
                    immutable_evidence_reference=(command.immutable_evidence_reference),
                )
                order_contract = _to_order_contract(
                    order=order,
                    existing_grant=existing_grant,
                )
                decision = decide_unit_grant(
                    order=order_contract,
                    payment=payment_contract,
                    previously_granted_idempotency_keys=(
                        frozenset({existing_grant.grant_idempotency_key}) if existing_grant is not None else frozenset()
                    ),
                    execution_enabled=True,
                )
                if decision.outcome is not UnitGrantOutcome.GRANTED:
                    raise TopUpApplicationConflictError(f"atomic unit grant was not approved: {decision.reason}")

                posting = await self._post_entitlement(
                    unit=unit,
                    command=TopUpGrantCommand(
                        tenant_id=command.tenant_id,
                        subscription_id=order.subscription_id,
                        units=decision.units,
                        order_reference=str(order.id),
                        payment_evidence_reference=(command.immutable_evidence_reference),
                        settlement_reference=(command.settlement_reference),
                        idempotency_key=(decision.grant_idempotency_key),
                        occurred_at=command.occurred_at,
                    ),
                )

                unit.payments.add(
                    CommercialTopUpPaymentEvidence(
                        order_id=command.order_id,
                        provider_reference=command.provider_reference,
                        outcome=payment_contract.outcome.value,
                        verified_amount=payment_contract.verified_amount,
                        verified_currency=payment_contract.verified_currency,
                        immutable_evidence_reference=(payment_contract.immutable_evidence_reference),
                    )
                )
                unit.grants.add(
                    CommercialTopUpGrant(
                        order_id=command.order_id,
                        outcome=decision.outcome.value,
                        units=decision.units,
                        grant_idempotency_key=(decision.grant_idempotency_key),
                        reason=decision.reason,
                    )
                )
                order.state = TopUpOrderState.GRANTED.value
                unit.audit.append(
                    _audit_record(
                        order_id=command.order_id,
                        action="payment_verified",
                        actor_reference=command.actor_reference,
                        evidence_reference=(command.immutable_evidence_reference),
                        occurred_at=command.occurred_at,
                        payload={
                            "provider_reference": (command.provider_reference),
                            "verified_amount": str(command.verified_amount),
                            "verified_currency": (command.verified_currency.strip().upper()),
                        },
                    )
                )
                unit.audit.append(
                    _audit_record(
                        order_id=command.order_id,
                        action="grant_applied",
                        actor_reference=command.actor_reference,
                        evidence_reference=(f"ledger-entry://{posting.entry_id}"),
                        occurred_at=command.occurred_at,
                        payload={
                            "grant_idempotency_key": (decision.grant_idempotency_key),
                            "ledger_entry_id": str(posting.entry_id),
                            "units": decision.units,
                        },
                    )
                )
                await unit.commit()

                return TopUpEntitlementBridgeResult(
                    order_id=order.id,
                    ledger_entry_id=posting.entry_id,
                    duplicate=False,
                    committed=True,
                    available_units=posting.available_units,
                    resulting_balance_version=(posting.resulting_balance_version),
                )
            except BaseException:
                await unit.rollback()
                raise

    async def _post_entitlement(
        self,
        *,
        unit: AtomicTopUpEntitlementUnitOfWork,
        command: TopUpGrantCommand,
    ) -> EntitlementGrantPostingResult:
        duplicate = await unit.ledger.get_by_idempotency_key(
            tenant_id=command.tenant_id,
            subscription_id=command.subscription_id,
            idempotency_key=command.idempotency_key,
        )
        if duplicate is not None:
            stored = await unit.balances.get_snapshot(
                tenant_id=command.tenant_id,
                subscription_id=command.subscription_id,
            )
            if stored is None:
                raise EntitlementGrantPostingConflictError("duplicate entry has no persisted balance")
            snapshot, version = stored
            return EntitlementGrantPostingResult(
                entry_id=duplicate.entry_id,
                entry_type=duplicate.entry_type,
                units=duplicate.units,
                duplicate=True,
                previous_balance_version=version,
                resulting_balance_version=version,
                available_units=snapshot.available_units,
                reserved_units=snapshot.reserved_units,
                committed_units=snapshot.committed_units,
            )

        stored = await unit.balances.get_snapshot(
            tenant_id=command.tenant_id,
            subscription_id=command.subscription_id,
        )
        if stored is None:
            snapshot = EntitlementBalanceSnapshot(
                tenant_id=command.tenant_id,
                subscription_id=command.subscription_id,
                available_units=0,
                reserved_units=0,
                committed_units=0,
                calculated_at=command.occurred_at.astimezone(UTC),
            )
            version = 0
        else:
            snapshot, version = stored

        entry = EntitlementLedgerEntry(
            entry_id=self._entry_id_factory(),
            tenant_id=command.tenant_id,
            subscription_id=command.subscription_id,
            entry_type=LedgerEntryType.TOP_UP_GRANT,
            units=command.units,
            idempotency_key=command.idempotency_key,
            occurred_at=command.occurred_at,
            source_reference=command.source_reference,
        )
        append_result = await unit.ledger.append(
            LedgerAppendRequest(
                entry=entry,
                expected_balance_version=version,
            )
        )
        available_units = snapshot.available_units + command.units
        swap_result = await unit.balances.compare_and_swap(
            BalanceCompareAndSwapRequest(
                tenant_id=command.tenant_id,
                subscription_id=command.subscription_id,
                expected_version=version,
                available_units=available_units,
                reserved_units=snapshot.reserved_units,
                committed_units=snapshot.committed_units,
                calculated_at=command.occurred_at,
            )
        )
        if not swap_result.updated:
            raise EntitlementGrantPostingConflictError("entitlement balance compare-and-swap conflict")

        return EntitlementGrantPostingResult(
            entry_id=append_result.entry_id,
            entry_type=LedgerEntryType.TOP_UP_GRANT,
            units=command.units,
            duplicate=append_result.duplicate,
            previous_balance_version=version,
            resulting_balance_version=(swap_result.resulting_version),
            available_units=available_units,
            reserved_units=snapshot.reserved_units,
            committed_units=snapshot.committed_units,
        )

    @staticmethod
    def _require(enabled: bool, message: str) -> None:
        if not enabled:
            raise TopUpApplicationServiceDisabledError(message)


def _to_order_contract(
    *,
    order: CommercialTopUpOrder,
    existing_grant: CommercialTopUpGrant | None,
) -> TopUpOrderContract:
    state = TopUpOrderState(order.state)
    confirmed = state not in {
        TopUpOrderState.DRAFT,
        TopUpOrderState.AWAITING_CONFIRMATION,
    }
    return TopUpOrderContract(
        order_id=order.id,
        account_id=order.account_id,
        subscription_id=order.subscription_id,
        plan_code=order.plan_code,
        requested_units=order.requested_units,
        bundle_count=order.bundle_count,
        total_price_usd=order.total_price_usd,
        settlement_currency=order.settlement_currency,
        settlement_amount=order.settlement_amount,
        exchange_rate_usd_tnd=order.exchange_rate_usd_tnd,
        exchange_rate_source=order.exchange_rate_source,
        exchange_rate_reference=order.exchange_rate_reference,
        exchange_rate_observed_at=order.exchange_rate_observed_at,
        exchange_rate_expires_at=order.exchange_rate_expires_at,
        channel=TopUpCheckoutChannel(order.channel),
        idempotency_key=order.idempotency_key,
        state=state,
        confirmed=confirmed,
        payment_verified=False,
        units_granted=existing_grant is not None,
    )


def _audit_record(
    *,
    order_id: uuid.UUID,
    action: str,
    actor_reference: str,
    evidence_reference: str,
    occurred_at: datetime,
    payload: dict[str, object],
) -> CommercialTopUpAuditRecord:
    digest = _payload_digest(payload)
    event_ref = _event_reference(
        order_id=order_id,
        action=action,
        evidence_reference=evidence_reference,
        payload_digest=digest,
    )
    return CommercialTopUpAuditRecord(
        event_ref=event_ref,
        order_id=order_id,
        action=action,
        occurred_at=occurred_at,
        actor_reference=actor_reference,
        evidence_reference=evidence_reference,
        payload_digest=digest,
    )


def _payload_digest(payload: dict[str, object]) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def _event_reference(
    *,
    order_id: uuid.UUID,
    action: str,
    evidence_reference: str,
    payload_digest: str,
) -> str:
    material = (f"{order_id}|{action}|{evidence_reference}|{payload_digest}").encode()
    return f"top-up-event:{hashlib.sha256(material).hexdigest()}"


def build_top_up_entitlement_bridge_status() -> dict[str, object]:
    return {
        "version": TOP_UP_ENTITLEMENT_BRIDGE_VERSION,
        "status": TOP_UP_ENTITLEMENT_BRIDGE_STATUS,
        "enabled": TOP_UP_ENTITLEMENT_BRIDGE_ENABLED,
        "writes_enabled": TOP_UP_ENTITLEMENT_BRIDGE_WRITES_ENABLED,
        "runtime_wiring_enabled": (TOP_UP_ENTITLEMENT_BRIDGE_RUNTIME_WIRING_ENABLED),
        "commercial_activation_enabled": (TOP_UP_ENTITLEMENT_BRIDGE_COMMERCIAL_ACTIVATION_ENABLED),
        "single_database_transaction_required": True,
        "payment_grant_audit_ledger_atomic": True,
        "idempotency_required": True,
        "fail_closed_by_default": True,
    }


__all__ = [
    "TOP_UP_ENTITLEMENT_BRIDGE_COMMERCIAL_ACTIVATION_ENABLED",
    "TOP_UP_ENTITLEMENT_BRIDGE_ENABLED",
    "TOP_UP_ENTITLEMENT_BRIDGE_RUNTIME_WIRING_ENABLED",
    "TOP_UP_ENTITLEMENT_BRIDGE_STATUS",
    "TOP_UP_ENTITLEMENT_BRIDGE_VERSION",
    "TOP_UP_ENTITLEMENT_BRIDGE_WRITES_ENABLED",
    "AtomicTopUpEntitlementUnitOfWork",
    "CommercialTopUpEntitlementBridgeService",
    "PostApprovedTopUpCommand",
    "TopUpEntitlementBridgePolicy",
    "TopUpEntitlementBridgeResult",
    "build_top_up_entitlement_bridge_status",
]
