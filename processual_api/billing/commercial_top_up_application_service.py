"""Atomic application service for commercial quota top-ups.

The service is fail-closed by default. Runtime persistence, payment handling,
grant execution, audit writes, and commercial event-ledger writes remain
disabled unless an explicit policy is injected by a governed composition root.
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
from enum import StrEnum
from typing import Protocol

from processual_api.billing.commercial_settings_top_up_checkout_contracts import (
    TopUpCheckoutChannel,
)
from processual_api.billing.commercial_top_up_event_ledger import (
    TOP_UP_EVENT_LEDGER_STORAGE_ENABLED,
    TopUpEventLedgerConflictError,
    TopUpEventLedgerRepository,
    stage_top_up_events,
)
from processual_api.billing.commercial_top_up_models import (
    CommercialTopUpAuditRecord,
    CommercialTopUpGrant,
    CommercialTopUpOrder,
    CommercialTopUpPaymentEvidence,
)
from processual_api.billing.commercial_top_up_order_grant_contracts import (
    ORDER_CREATION_ENABLED,
    PAYMENT_VERIFICATION_ENABLED,
    UNIT_GRANT_EXECUTION_ENABLED,
    PaymentVerificationContract,
    PaymentVerificationOutcome,
    TopUpOrderContract,
    TopUpOrderState,
    UnitGrantOutcome,
    decide_unit_grant,
)
from processual_api.billing.commercial_top_up_persistence_audit_contracts import (
    TOP_UP_AUDIT_STORAGE_ENABLED,
    TOP_UP_GRANT_STORAGE_ENABLED,
    TOP_UP_ORDER_STORAGE_ENABLED,
    TOP_UP_PAYMENT_EVIDENCE_STORAGE_ENABLED,
)
from processual_api.billing.commercial_top_up_transition_authority import (
    TopUpTransitionEvidence,
    build_verified_payment_grant_events,
)

TOP_UP_APPLICATION_SERVICE_VERSION = "2026-08-b2-top-up-application-service-v2"
TOP_UP_APPLICATION_SERVICE_STATUS = "draft_review"


class TopUpApplicationServiceError(RuntimeError):
    """Base error for governed top-up application operations."""


class TopUpApplicationServiceDisabledError(TopUpApplicationServiceError):
    """Raised when a required runtime capability remains disabled."""


class TopUpApplicationConflictError(TopUpApplicationServiceError):
    """Raised when commercial authority or idempotency state conflicts."""


class TopUpApplicationNotFoundError(TopUpApplicationServiceError):
    """Raised when a referenced top-up order does not exist."""


class TopUpApplicationOutcome(StrEnum):
    CREATED = "created"
    IDEMPOTENT_REPLAY = "idempotent_replay"
    PAYMENT_AND_GRANT_RECORDED = "payment_and_grant_recorded"


@dataclass(frozen=True, slots=True)
class TopUpApplicationPolicy:
    order_creation_enabled: bool = ORDER_CREATION_ENABLED
    payment_verification_enabled: bool = PAYMENT_VERIFICATION_ENABLED
    grant_execution_enabled: bool = UNIT_GRANT_EXECUTION_ENABLED
    order_storage_enabled: bool = TOP_UP_ORDER_STORAGE_ENABLED
    payment_storage_enabled: bool = TOP_UP_PAYMENT_EVIDENCE_STORAGE_ENABLED
    grant_storage_enabled: bool = TOP_UP_GRANT_STORAGE_ENABLED
    audit_storage_enabled: bool = TOP_UP_AUDIT_STORAGE_ENABLED
    event_ledger_enabled: bool = TOP_UP_EVENT_LEDGER_STORAGE_ENABLED


@dataclass(frozen=True, slots=True)
class CreateTopUpOrderCommand:
    order_id: uuid.UUID
    account_id: uuid.UUID
    subscription_id: uuid.UUID
    plan_code: str
    requested_units: int
    bundle_count: int
    total_price_usd: Decimal
    channel: TopUpCheckoutChannel
    idempotency_key: str
    actor_reference: str
    evidence_reference: str
    settlement_currency: str | None = None
    settlement_amount: Decimal | None = None
    exchange_rate_usd_tnd: Decimal | None = None
    exchange_rate_source: str | None = None
    exchange_rate_reference: str | None = None
    exchange_rate_observed_at: datetime | None = None
    exchange_rate_expires_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.settlement_currency is None:
            object.__setattr__(self, "settlement_currency", "USD")
        if self.settlement_amount is None:
            object.__setattr__(self, "settlement_amount", self.total_price_usd)
        if not self.plan_code.strip():
            raise ValueError("plan_code must not be blank")
        if self.requested_units <= 0:
            raise ValueError("requested_units must be positive")
        if self.bundle_count <= 0:
            raise ValueError("bundle_count must be positive")
        if self.total_price_usd <= 0:
            raise ValueError("total_price_usd must be positive")
        if not self.idempotency_key.strip():
            raise ValueError("idempotency_key must not be blank")
        if not self.actor_reference.strip():
            raise ValueError("actor_reference must not be blank")
        if not self.evidence_reference.strip():
            raise ValueError("evidence_reference must not be blank")


@dataclass(frozen=True, slots=True)
class RecordPaymentAndGrantCommand:
    order_id: uuid.UUID
    provider_reference: str
    verified_amount: Decimal
    verified_currency: str
    immutable_evidence_reference: str
    actor_reference: str

    def __post_init__(self) -> None:
        if not self.provider_reference.strip():
            raise ValueError("provider_reference must not be blank")
        if self.verified_amount <= 0:
            raise ValueError("verified_amount must be positive")
        normalized_currency = self.verified_currency.strip().upper()
        if len(normalized_currency) != 3:
            raise ValueError("verified_currency must be ISO-4217")
        if not self.immutable_evidence_reference.strip():
            raise ValueError("immutable_evidence_reference must not be blank")
        if not self.actor_reference.strip():
            raise ValueError("actor_reference must not be blank")


@dataclass(frozen=True, slots=True)
class TopUpApplicationResult:
    order_id: uuid.UUID
    outcome: TopUpApplicationOutcome
    grant_outcome: UnitGrantOutcome | None
    committed: bool


class OrderRepository(Protocol):
    async def get_by_id(
        self,
        order_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> CommercialTopUpOrder | None: ...

    async def get_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> CommercialTopUpOrder | None: ...

    def add(self, order: CommercialTopUpOrder) -> None: ...


class PaymentRepository(Protocol):
    async def get_for_order(
        self,
        order_id: uuid.UUID,
    ) -> CommercialTopUpPaymentEvidence | None: ...

    async def get_by_provider_reference(
        self,
        provider_reference: str,
    ) -> CommercialTopUpPaymentEvidence | None: ...

    def add(self, payment: CommercialTopUpPaymentEvidence) -> None: ...


class GrantRepository(Protocol):
    async def get_for_order(
        self,
        order_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> CommercialTopUpGrant | None: ...

    async def get_by_idempotency_key(
        self,
        grant_idempotency_key: str,
    ) -> CommercialTopUpGrant | None: ...

    def add(self, grant: CommercialTopUpGrant) -> None: ...


class AuditRepository(Protocol):
    def append(self, record: CommercialTopUpAuditRecord) -> None: ...


class AsyncTopUpUnitOfWork(Protocol):
    orders: OrderRepository
    payments: PaymentRepository
    grants: GrantRepository
    audit: AuditRepository
    event_ledger: TopUpEventLedgerRepository

    async def __aenter__(self) -> AsyncTopUpUnitOfWork: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


UnitOfWorkFactory = Callable[[], AbstractAsyncContextManager[AsyncTopUpUnitOfWork]]


class CommercialTopUpApplicationService:
    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        policy: TopUpApplicationPolicy | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._policy = policy or TopUpApplicationPolicy()
        self._clock = clock or (lambda: datetime.now(UTC))

    async def create_order(
        self,
        command: CreateTopUpOrderCommand,
    ) -> TopUpApplicationResult:
        self._require(self._policy.order_creation_enabled, "top-up order creation is disabled")
        self._require(self._policy.order_storage_enabled, "top-up order storage is disabled")
        self._require(self._policy.audit_storage_enabled, "top-up audit storage is disabled")

        async with self._unit_of_work_factory() as uow:
            existing = await uow.orders.get_by_idempotency_key(command.idempotency_key)
            if existing is not None:
                if not _same_order(existing, command):
                    raise TopUpApplicationConflictError(
                        "top-up order idempotency key conflicts with existing order"
                    )
                return TopUpApplicationResult(
                    order_id=existing.id,
                    outcome=TopUpApplicationOutcome.IDEMPOTENT_REPLAY,
                    grant_outcome=None,
                    committed=False,
                )

            order = CommercialTopUpOrder(
                id=command.order_id,
                account_id=command.account_id,
                subscription_id=command.subscription_id,
                plan_code=command.plan_code,
                requested_units=command.requested_units,
                bundle_count=command.bundle_count,
                total_price_usd=command.total_price_usd,
                settlement_currency=_command_settlement_currency(command),
                settlement_amount=command.settlement_amount,
                exchange_rate_usd_tnd=command.exchange_rate_usd_tnd,
                exchange_rate_source=command.exchange_rate_source,
                exchange_rate_reference=command.exchange_rate_reference,
                exchange_rate_observed_at=command.exchange_rate_observed_at,
                exchange_rate_expires_at=command.exchange_rate_expires_at,
                channel=command.channel.value,
                idempotency_key=command.idempotency_key,
                state=TopUpOrderState.AWAITING_PAYMENT.value,
            )
            uow.orders.add(order)
            uow.audit.append(
                self._audit_record(
                    order_id=command.order_id,
                    action="order_created",
                    actor_reference=command.actor_reference,
                    evidence_reference=command.evidence_reference,
                    payload={
                        "idempotency_key": command.idempotency_key,
                        "requested_units": command.requested_units,
                        "total_price_usd": str(command.total_price_usd),
                    },
                )
            )
            await uow.commit()

        return TopUpApplicationResult(
            order_id=command.order_id,
            outcome=TopUpApplicationOutcome.CREATED,
            grant_outcome=None,
            committed=True,
        )

    async def record_payment_and_grant(
        self,
        command: RecordPaymentAndGrantCommand,
    ) -> TopUpApplicationResult:
        self._require(
            self._policy.payment_verification_enabled,
            "top-up payment verification is disabled",
        )
        self._require(
            self._policy.grant_execution_enabled,
            "top-up unit grant execution is disabled",
        )
        self._require(self._policy.order_storage_enabled, "top-up order storage is disabled")
        self._require(
            self._policy.payment_storage_enabled,
            "top-up payment evidence storage is disabled",
        )
        self._require(self._policy.grant_storage_enabled, "top-up grant storage is disabled")
        self._require(self._policy.audit_storage_enabled, "top-up audit storage is disabled")
        self._require(
            self._policy.event_ledger_enabled,
            "top-up commercial event ledger is disabled",
        )

        async with self._unit_of_work_factory() as uow:
            order = await uow.orders.get_by_id(command.order_id, for_update=True)
            if order is None:
                raise TopUpApplicationNotFoundError("top-up order was not found")

            existing_provider_payment = await uow.payments.get_by_provider_reference(
                command.provider_reference
            )
            existing_grant = await uow.grants.get_for_order(
                command.order_id,
                for_update=True,
            )

            if existing_provider_payment is not None:
                if existing_provider_payment.order_id != command.order_id:
                    raise TopUpApplicationConflictError(
                        "provider payment reference belongs to another top-up order"
                    )
                if existing_grant is None:
                    raise TopUpApplicationConflictError(
                        "payment replay found without its atomic grant"
                    )
                return TopUpApplicationResult(
                    order_id=command.order_id,
                    outcome=TopUpApplicationOutcome.IDEMPOTENT_REPLAY,
                    grant_outcome=UnitGrantOutcome(existing_grant.outcome),
                    committed=False,
                )

            if order.state != TopUpOrderState.AWAITING_PAYMENT.value:
                raise TopUpApplicationConflictError(
                    "top-up payment and grant must start from awaiting_payment"
                )

            payment_contract = PaymentVerificationContract(
                order_id=command.order_id,
                provider_reference=command.provider_reference,
                outcome=PaymentVerificationOutcome.VERIFIED,
                verified_amount=command.verified_amount,
                verified_currency=command.verified_currency.strip().upper(),
                immutable_evidence_reference=command.immutable_evidence_reference,
            )
            order_contract = _to_order_contract(order=order, existing_grant=existing_grant)
            existing_keys = (
                frozenset({existing_grant.grant_idempotency_key})
                if existing_grant is not None
                else frozenset()
            )
            decision = decide_unit_grant(
                order=order_contract,
                payment=payment_contract,
                previously_granted_idempotency_keys=existing_keys,
                execution_enabled=self._policy.grant_execution_enabled,
            )
            if decision.outcome is not UnitGrantOutcome.GRANTED:
                raise TopUpApplicationConflictError(
                    f"atomic unit grant was not approved: {decision.reason}"
                )

            payment_payload: dict[str, object] = {
                "provider_reference": command.provider_reference,
                "verified_amount": str(command.verified_amount),
                "verified_currency": command.verified_currency.strip().upper(),
            }
            grant_payload: dict[str, object] = {
                "grant_idempotency_key": decision.grant_idempotency_key,
                "units": decision.units,
                "outcome": decision.outcome.value,
            }
            occurred_at = self._clock()
            if occurred_at.tzinfo is None:
                raise ValueError("application service clock must be timezone aware")
            authority_events = build_verified_payment_grant_events(
                TopUpTransitionEvidence(
                    order_id=command.order_id,
                    provider_reference=command.provider_reference,
                    actor_reference=command.actor_reference,
                    evidence_reference=command.immutable_evidence_reference,
                    occurred_at=occurred_at,
                    payment_payload_digest=_payload_digest(payment_payload),
                    grant_payload_digest=_payload_digest(grant_payload),
                )
            )
            try:
                ledger_result = await stage_top_up_events(
                    repository=uow.event_ledger,
                    events=authority_events,
                )
            except TopUpEventLedgerConflictError as exc:
                raise TopUpApplicationConflictError(
                    f"top-up commercial event ledger conflict: {exc}"
                ) from exc
            if ledger_result.replayed:
                raise TopUpApplicationConflictError(
                    "commercial event replay exists without atomic payment and grant"
                )

            payment = CommercialTopUpPaymentEvidence(
                order_id=command.order_id,
                provider_reference=command.provider_reference,
                outcome=payment_contract.outcome.value,
                verified_amount=payment_contract.verified_amount,
                verified_currency=payment_contract.verified_currency,
                immutable_evidence_reference=payment_contract.immutable_evidence_reference,
            )
            grant = CommercialTopUpGrant(
                order_id=command.order_id,
                outcome=decision.outcome.value,
                units=decision.units,
                grant_idempotency_key=decision.grant_idempotency_key,
                reason=decision.reason,
            )
            uow.payments.add(payment)
            uow.grants.add(grant)
            order.state = TopUpOrderState.GRANTED.value
            uow.audit.append(
                self._audit_record(
                    order_id=command.order_id,
                    action="payment_verified",
                    actor_reference=command.actor_reference,
                    evidence_reference=command.immutable_evidence_reference,
                    payload=payment_payload,
                )
            )
            uow.audit.append(
                self._audit_record(
                    order_id=command.order_id,
                    action="grant_applied",
                    actor_reference=command.actor_reference,
                    evidence_reference=f"grant://{decision.grant_idempotency_key}",
                    payload=grant_payload,
                )
            )
            await uow.commit()

        return TopUpApplicationResult(
            order_id=command.order_id,
            outcome=TopUpApplicationOutcome.PAYMENT_AND_GRANT_RECORDED,
            grant_outcome=UnitGrantOutcome.GRANTED,
            committed=True,
        )

    def _audit_record(
        self,
        *,
        order_id: uuid.UUID,
        action: str,
        actor_reference: str,
        evidence_reference: str,
        payload: dict[str, object],
    ) -> CommercialTopUpAuditRecord:
        occurred_at = self._clock()
        if occurred_at.tzinfo is None:
            raise ValueError("application service clock must be timezone aware")
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

    @staticmethod
    def _require(enabled: bool, message: str) -> None:
        if not enabled:
            raise TopUpApplicationServiceDisabledError(message)


def _command_settlement_currency(command: CreateTopUpOrderCommand) -> str:
    settlement_currency = command.settlement_currency
    if settlement_currency is None:
        raise TopUpApplicationConflictError("top-up settlement currency is missing")
    return settlement_currency.strip().upper()


def _same_order(
    existing: CommercialTopUpOrder,
    command: CreateTopUpOrderCommand,
) -> bool:
    return (
        existing.id == command.order_id
        and existing.account_id == command.account_id
        and existing.subscription_id == command.subscription_id
        and existing.plan_code == command.plan_code
        and existing.requested_units == command.requested_units
        and existing.bundle_count == command.bundle_count
        and existing.total_price_usd == command.total_price_usd
        and existing.settlement_currency == _command_settlement_currency(command)
        and existing.settlement_amount == command.settlement_amount
        and existing.exchange_rate_usd_tnd == command.exchange_rate_usd_tnd
        and existing.exchange_rate_source == command.exchange_rate_source
        and existing.exchange_rate_reference == command.exchange_rate_reference
        and existing.exchange_rate_observed_at == command.exchange_rate_observed_at
        and existing.exchange_rate_expires_at == command.exchange_rate_expires_at
        and existing.channel == command.channel.value
    )


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
    account_id = order.account_id
    if account_id is None:
        raise TopUpApplicationConflictError(
            "stored top-up order is missing its account authority"
        )
    return TopUpOrderContract(
        order_id=order.id,
        account_id=account_id,
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
    material = f"{order_id}|{action}|{evidence_reference}|{payload_digest}".encode()
    return f"top-up-event:{hashlib.sha256(material).hexdigest()}"


def build_top_up_application_service_status() -> dict[str, bool | str]:
    policy = TopUpApplicationPolicy()
    return {
        "contract_version": TOP_UP_APPLICATION_SERVICE_VERSION,
        "status": TOP_UP_APPLICATION_SERVICE_STATUS,
        "order_creation_enabled": policy.order_creation_enabled,
        "payment_verification_enabled": policy.payment_verification_enabled,
        "grant_execution_enabled": policy.grant_execution_enabled,
        "order_storage_enabled": policy.order_storage_enabled,
        "payment_storage_enabled": policy.payment_storage_enabled,
        "grant_storage_enabled": policy.grant_storage_enabled,
        "audit_storage_enabled": policy.audit_storage_enabled,
        "event_ledger_enabled": policy.event_ledger_enabled,
        "atomic_payment_grant_audit_required": True,
        "atomic_payment_grant_audit_event_ledger_required": True,
        "fail_closed_by_default": True,
    }


__all__ = [
    "CommercialTopUpApplicationService",
    "CreateTopUpOrderCommand",
    "RecordPaymentAndGrantCommand",
    "TopUpApplicationConflictError",
    "TopUpApplicationNotFoundError",
    "TopUpApplicationOutcome",
    "TopUpApplicationPolicy",
    "TopUpApplicationResult",
    "TopUpApplicationServiceDisabledError",
    "build_top_up_application_service_status",
]
