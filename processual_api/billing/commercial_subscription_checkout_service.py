"""Consolidated subscription checkout and activation authority for Group 2.

This module owns the application boundary between a customer checkout intent,
payment evidence, a platform-admin commercial decision, and the already
qualified monthly subscription grant authority.

It deliberately does not call payment providers, expose webhooks, create HTTP
routes, or wire runtime enforcement. Provider events are recorded as evidence;
they never grant units directly.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Final, Protocol
from uuid import UUID

from processual_api.billing.commercial_subscription_cycle_grant_service import (
    ApprovedSubscriptionCycleGrantCommand,
    SubscriptionCycleKind,
)

COMMERCIAL_CHECKOUT_AUTHORITY_VERSION: Final = "2026-07-group2-commercial-checkout-authority-v1"
COMMERCIAL_CHECKOUT_AUTHORITY_STATUS: Final = "draft_review"

COMMERCIAL_CHECKOUT_AUTHORITY_ENABLED: Final = False
COMMERCIAL_CHECKOUT_WRITES_ENABLED: Final = False
COMMERCIAL_CHECKOUT_PROVIDER_RUNTIME_ENABLED: Final = False
COMMERCIAL_CHECKOUT_WEBHOOK_RUNTIME_ENABLED: Final = False
COMMERCIAL_CHECKOUT_ACTIVATION_ENABLED: Final = False
COMMERCIAL_CHECKOUT_GRANT_BRIDGE_ENABLED: Final = False

AUTHORITATIVE_CURRENCY: Final = "USD"
LOCAL_TUNISIA_CURRENCY: Final = "TND"


class CommercialCheckoutAuthorityError(RuntimeError):
    """Base commercial checkout authority error."""


class CommercialCheckoutDisabledError(CommercialCheckoutAuthorityError):
    """Raised while the package remains fail-closed."""


class CommercialCheckoutConflictError(CommercialCheckoutAuthorityError):
    """Raised for an idempotency or lifecycle conflict."""


class CommercialCheckoutNotFoundError(CommercialCheckoutAuthorityError):
    """Raised when a requested order does not exist."""


class CommercialCheckoutPermissionError(CommercialCheckoutAuthorityError):
    """Raised when the caller lacks platform-admin authority."""


class CommercialCheckoutEvidenceError(CommercialCheckoutAuthorityError):
    """Raised when payment evidence cannot authorize activation."""


class CommercialCheckoutChannel(StrEnum):
    LOCAL_TUNISIA = "local_tunisia"
    LEMON_SQUEEZY = "lemon_squeezy"


class CommercialCheckoutOrderState(StrEnum):
    DRAFT = "draft"
    AWAITING_PAYMENT = "awaiting_payment"
    PAYMENT_PENDING = "payment_pending"
    PAYMENT_VERIFIED = "payment_verified"
    PAYMENT_REJECTED = "payment_rejected"
    ACTIVATION_REVIEW = "activation_review"
    ACTIVATION_APPROVED = "activation_approved"
    ACTIVATION_REJECTED = "activation_rejected"
    ACTIVATED = "activated"
    CANCELLED = "cancelled"


class PaymentEvidenceOutcome(StrEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"
    REQUIRES_REVIEW = "requires_review"


class CommercialDecisionOutcome(StrEnum):
    APPROVED = "approved"
    DENIED = "denied"
    REQUIRES_REVIEW = "requires_review"


class CheckoutSurfaceState(StrEnum):
    LOADING = "loading"
    ELIGIBILITY_REQUIRED = "eligibility_required"
    CHANNEL_SELECTION = "channel_selection"
    REVIEW = "review"
    PAYMENT_PENDING = "payment_pending"
    VERIFICATION_PENDING = "verification_pending"
    ACTIVATION_REVIEW = "activation_review"
    SUCCESS = "success"
    ERROR = "error"
    DISABLED = "disabled"


@dataclass(frozen=True, slots=True)
class CommercialCheckoutPolicy:
    enabled: bool = COMMERCIAL_CHECKOUT_AUTHORITY_ENABLED
    writes_enabled: bool = COMMERCIAL_CHECKOUT_WRITES_ENABLED
    provider_runtime_enabled: bool = COMMERCIAL_CHECKOUT_PROVIDER_RUNTIME_ENABLED
    webhook_runtime_enabled: bool = COMMERCIAL_CHECKOUT_WEBHOOK_RUNTIME_ENABLED
    activation_enabled: bool = COMMERCIAL_CHECKOUT_ACTIVATION_ENABLED
    grant_bridge_enabled: bool = COMMERCIAL_CHECKOUT_GRANT_BRIDGE_ENABLED


@dataclass(frozen=True, slots=True)
class SubscriptionCheckoutOrder:
    order_id: UUID
    tenant_id: UUID
    subscription_id: UUID
    customer_reference: str
    plan_code: str
    included_units: int
    billing_cycle_reference: str
    cycle_started_at: datetime
    cycle_ends_at: datetime
    authoritative_price_usd: Decimal
    selected_channel: CommercialCheckoutChannel
    settlement_currency: str
    settlement_amount: Decimal
    quote_reference: str
    quote_expires_at: datetime
    billing_country: str | None
    tunisian_address_eligible: bool
    customer_choice_preserved: bool
    state: CommercialCheckoutOrderState
    idempotency_key: str
    created_at: datetime
    version: int = 0

    def __post_init__(self) -> None:
        if self.included_units <= 0:
            raise ValueError("included_units must be positive")
        _positive_decimal(
            self.authoritative_price_usd,
            "authoritative_price_usd",
        )
        _positive_decimal(
            self.settlement_amount,
            "settlement_amount",
        )
        if self.cycle_started_at.tzinfo is None:
            raise ValueError("cycle_started_at must be timezone-aware")
        if self.cycle_ends_at.tzinfo is None:
            raise ValueError("cycle_ends_at must be timezone-aware")
        if self.cycle_ends_at <= self.cycle_started_at:
            raise ValueError("cycle_ends_at must be after cycle_started_at")
        if self.quote_expires_at.tzinfo is None:
            raise ValueError("quote_expires_at must be timezone-aware")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        if self.quote_expires_at <= self.created_at:
            raise ValueError("quote must expire after order creation")
        if not self.customer_reference.strip():
            raise ValueError("customer_reference must not be blank")
        if not self.plan_code.strip():
            raise ValueError("plan_code must not be blank")
        if not self.billing_cycle_reference.strip():
            raise ValueError("billing_cycle_reference must not be blank")
        if not self.quote_reference.strip():
            raise ValueError("quote_reference must not be blank")
        if not self.idempotency_key.strip():
            raise ValueError("idempotency_key must not be blank")
        if self.version < 0:
            raise ValueError("version must not be negative")

        normalized_country = None if self.billing_country is None else self.billing_country.strip().upper()
        if normalized_country is not None and len(normalized_country) != 2:
            raise ValueError("billing_country must be an ISO alpha-2 code")
        object.__setattr__(self, "billing_country", normalized_country)

        if self.selected_channel is CommercialCheckoutChannel.LOCAL_TUNISIA:
            if normalized_country != "TN":
                raise ValueError("local Tunisia channel requires billing country TN")
            if not self.tunisian_address_eligible:
                raise ValueError("local Tunisia channel requires eligible address")
            if self.settlement_currency != LOCAL_TUNISIA_CURRENCY:
                raise ValueError("local Tunisia settlement currency must be TND")
        elif self.settlement_currency != AUTHORITATIVE_CURRENCY:
            raise ValueError("Lemon Squeezy settlement currency must be USD")
        elif self.settlement_amount != self.authoritative_price_usd:
            raise ValueError("Lemon Squeezy settlement must equal USD price")

        if not self.customer_choice_preserved:
            raise ValueError("customer channel choice must remain preserved")


@dataclass(frozen=True, slots=True)
class CommercialPaymentEvidence:
    evidence_id: UUID
    order_id: UUID
    provider_reference: str
    channel: CommercialCheckoutChannel
    outcome: PaymentEvidenceOutcome
    verified_amount: Decimal | None
    verified_currency: str | None
    immutable_evidence_reference: str
    observed_at: datetime
    idempotency_key: str

    def __post_init__(self) -> None:
        if not self.provider_reference.strip():
            raise ValueError("provider_reference must not be blank")
        if not self.immutable_evidence_reference.strip():
            raise ValueError("immutable_evidence_reference must not be blank")
        if not self.idempotency_key.strip():
            raise ValueError("idempotency_key must not be blank")
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")

        if self.outcome is PaymentEvidenceOutcome.VERIFIED:
            if self.verified_amount is None:
                raise ValueError("verified payment requires verified_amount")
            _positive_decimal(
                self.verified_amount,
                "verified_amount",
            )
            if self.verified_currency is None:
                raise ValueError("verified payment requires verified_currency")
            if len(self.verified_currency.strip()) != 3:
                raise ValueError("verified_currency must have length three")


@dataclass(frozen=True, slots=True)
class CommercialActivationDecision:
    decision_id: UUID
    order_id: UUID
    outcome: CommercialDecisionOutcome
    actor_reference: str
    authority_reference: str
    approval_reference: str
    reason: str
    occurred_at: datetime
    idempotency_key: str

    def __post_init__(self) -> None:
        for name, value in (
            ("actor_reference", self.actor_reference),
            ("authority_reference", self.authority_reference),
            ("approval_reference", self.approval_reference),
            ("reason", self.reason),
            ("idempotency_key", self.idempotency_key),
        ):
            if not value.strip():
                raise ValueError(f"{name} must not be blank")
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class CreateSubscriptionCheckoutCommand:
    order: SubscriptionCheckoutOrder


@dataclass(frozen=True, slots=True)
class RecordPaymentEvidenceCommand:
    evidence: CommercialPaymentEvidence


@dataclass(frozen=True, slots=True)
class DecideSubscriptionActivationCommand:
    decision: CommercialActivationDecision
    recent_mfa_step_up: bool


@dataclass(frozen=True, slots=True)
class CommercialCheckoutResult:
    order: SubscriptionCheckoutOrder
    committed: bool
    idempotent_replay: bool
    grant_command: ApprovedSubscriptionCycleGrantCommand | None


@dataclass(frozen=True, slots=True)
class CommercialCheckoutView:
    surface: str
    state: CheckoutSurfaceState
    order_reference: str | None
    selected_channel: str | None
    available_channels: tuple[str, ...]
    authoritative_price_usd: str | None
    settlement_currency: str | None
    settlement_amount: str | None
    customer_choice_preserved: bool
    payment_verified: bool
    activation_approved: bool
    checkout_enabled: bool
    provider_runtime_enabled: bool
    activation_enabled: bool
    grant_bridge_enabled: bool
    messages: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["state"] = self.state.value
        payload["available_channels"] = list(self.available_channels)
        payload["messages"] = list(self.messages)
        return payload


class SubscriptionCheckoutOrderRepository(Protocol):
    async def get_by_id(
        self,
        order_id: UUID,
        *,
        for_update: bool = False,
    ) -> SubscriptionCheckoutOrder | None: ...

    async def get_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> SubscriptionCheckoutOrder | None: ...

    def add(self, order: SubscriptionCheckoutOrder) -> None: ...

    def replace(self, order: SubscriptionCheckoutOrder) -> None: ...


class CommercialPaymentEvidenceRepository(Protocol):
    async def get_by_provider_reference(
        self,
        provider_reference: str,
    ) -> CommercialPaymentEvidence | None: ...

    async def get_latest_for_order(
        self,
        order_id: UUID,
    ) -> CommercialPaymentEvidence | None: ...

    def add(self, evidence: CommercialPaymentEvidence) -> None: ...


class CommercialActivationDecisionRepository(Protocol):
    async def get_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> CommercialActivationDecision | None: ...

    async def get_latest_for_order(
        self,
        order_id: UUID,
    ) -> CommercialActivationDecision | None: ...

    def add(self, decision: CommercialActivationDecision) -> None: ...


class CommercialCheckoutUnitOfWork(Protocol):
    orders: SubscriptionCheckoutOrderRepository
    payments: CommercialPaymentEvidenceRepository
    decisions: CommercialActivationDecisionRepository

    async def __aenter__(
        self,
    ) -> CommercialCheckoutUnitOfWork: ...

    async def __aexit__(
        self,
        exc_type,
        exc,
        traceback,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


class CommercialSubscriptionCheckoutService:
    def __init__(
        self,
        *,
        unit_of_work_factory: Callable[[], CommercialCheckoutUnitOfWork],
        policy: CommercialCheckoutPolicy | None = None,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._policy = policy or CommercialCheckoutPolicy()

    async def create_checkout(
        self,
        command: CreateSubscriptionCheckoutCommand,
    ) -> CommercialCheckoutResult:
        self._require_enabled()
        order = command.order
        self._validate_channel(order)

        async with self._unit_of_work_factory() as unit:
            existing = await unit.orders.get_by_idempotency_key(order.idempotency_key)
            if existing is not None:
                if existing == order:
                    return CommercialCheckoutResult(
                        order=existing,
                        committed=False,
                        idempotent_replay=True,
                        grant_command=None,
                    )
                raise CommercialCheckoutConflictError("checkout idempotency key conflicts with another payload")

            unit.orders.add(order)
            await unit.commit()

        return CommercialCheckoutResult(
            order=order,
            committed=True,
            idempotent_replay=False,
            grant_command=None,
        )

    async def record_payment_evidence(
        self,
        command: RecordPaymentEvidenceCommand,
    ) -> CommercialCheckoutResult:
        self._require_enabled()
        evidence = command.evidence

        async with self._unit_of_work_factory() as unit:
            order = await unit.orders.get_by_id(
                evidence.order_id,
                for_update=True,
            )
            if order is None:
                raise CommercialCheckoutNotFoundError("checkout order was not found")
            if evidence.channel is not order.selected_channel:
                raise CommercialCheckoutEvidenceError("payment channel does not match checkout order")

            existing = await unit.payments.get_by_provider_reference(evidence.provider_reference)
            if existing is not None:
                if existing == evidence:
                    return CommercialCheckoutResult(
                        order=order,
                        committed=False,
                        idempotent_replay=True,
                        grant_command=None,
                    )
                raise CommercialCheckoutConflictError("provider reference belongs to different evidence")

            self._validate_payment_amount(order, evidence)
            unit.payments.add(evidence)

            next_state = {
                PaymentEvidenceOutcome.PENDING: (CommercialCheckoutOrderState.PAYMENT_PENDING),
                PaymentEvidenceOutcome.VERIFIED: (CommercialCheckoutOrderState.PAYMENT_VERIFIED),
                PaymentEvidenceOutcome.REJECTED: (CommercialCheckoutOrderState.PAYMENT_REJECTED),
                PaymentEvidenceOutcome.REQUIRES_REVIEW: (CommercialCheckoutOrderState.ACTIVATION_REVIEW),
            }[evidence.outcome]
            updated = replace(
                order,
                state=next_state,
                version=order.version + 1,
            )
            unit.orders.replace(updated)
            await unit.commit()

        return CommercialCheckoutResult(
            order=updated,
            committed=True,
            idempotent_replay=False,
            grant_command=None,
        )

    async def decide_activation(
        self,
        command: DecideSubscriptionActivationCommand,
    ) -> CommercialCheckoutResult:
        self._require_enabled()
        if not self._policy.activation_enabled:
            raise CommercialCheckoutDisabledError("commercial activation is disabled")

        decision = command.decision
        self._require_platform_admin(
            decision=decision,
            recent_mfa_step_up=command.recent_mfa_step_up,
        )

        async with self._unit_of_work_factory() as unit:
            order = await unit.orders.get_by_id(
                decision.order_id,
                for_update=True,
            )
            if order is None:
                raise CommercialCheckoutNotFoundError("checkout order was not found")

            previous_decision = await unit.decisions.get_by_idempotency_key(decision.idempotency_key)
            if previous_decision is not None:
                if previous_decision == decision:
                    grant = (
                        self._build_grant_command(
                            order=order,
                            decision=decision,
                        )
                        if (
                            decision.outcome is CommercialDecisionOutcome.APPROVED
                            and order.state is CommercialCheckoutOrderState.ACTIVATION_APPROVED
                        )
                        else None
                    )
                    return CommercialCheckoutResult(
                        order=order,
                        committed=False,
                        idempotent_replay=True,
                        grant_command=grant,
                    )
                raise CommercialCheckoutConflictError("decision idempotency key conflicts with another payload")

            evidence = await unit.payments.get_latest_for_order(order.order_id)
            if evidence is None or evidence.outcome is not PaymentEvidenceOutcome.VERIFIED:
                raise CommercialCheckoutEvidenceError("verified payment evidence is required before activation")

            if decision.outcome is CommercialDecisionOutcome.APPROVED:
                next_state = CommercialCheckoutOrderState.ACTIVATION_APPROVED
                grant = self._build_grant_command(
                    order=order,
                    decision=decision,
                )
            elif decision.outcome is CommercialDecisionOutcome.DENIED:
                next_state = CommercialCheckoutOrderState.ACTIVATION_REJECTED
                grant = None
            else:
                next_state = CommercialCheckoutOrderState.ACTIVATION_REVIEW
                grant = None

            unit.decisions.add(decision)
            updated = replace(
                order,
                state=next_state,
                version=order.version + 1,
            )
            unit.orders.replace(updated)
            await unit.commit()

        return CommercialCheckoutResult(
            order=updated,
            committed=True,
            idempotent_replay=False,
            grant_command=grant,
        )

    def _require_enabled(self) -> None:
        if not self._policy.enabled:
            raise CommercialCheckoutDisabledError("commercial checkout authority is disabled")
        if not self._policy.writes_enabled:
            raise CommercialCheckoutDisabledError("commercial checkout writes are disabled")

    @staticmethod
    def _validate_channel(order: SubscriptionCheckoutOrder) -> None:
        if order.selected_channel is CommercialCheckoutChannel.LOCAL_TUNISIA and (
            order.billing_country != "TN" or not order.tunisian_address_eligible
        ):
            raise CommercialCheckoutAuthorityError("local Tunisia checkout is limited to eligible TN addresses")

    @staticmethod
    def _validate_payment_amount(
        order: SubscriptionCheckoutOrder,
        evidence: CommercialPaymentEvidence,
    ) -> None:
        if evidence.outcome is not PaymentEvidenceOutcome.VERIFIED:
            return
        if evidence.verified_currency is None:
            raise CommercialCheckoutEvidenceError("verified currency is required")
        if evidence.verified_currency.strip().upper() != order.settlement_currency:
            raise CommercialCheckoutEvidenceError("verified currency does not match order settlement")
        if evidence.verified_amount != order.settlement_amount:
            raise CommercialCheckoutEvidenceError("verified amount does not match order settlement")

    @staticmethod
    def _require_platform_admin(
        *,
        decision: CommercialActivationDecision,
        recent_mfa_step_up: bool,
    ) -> None:
        if decision.authority_reference != "platform_admin":
            raise CommercialCheckoutPermissionError("platform_admin authority is required")
        if not recent_mfa_step_up:
            raise CommercialCheckoutPermissionError("recent MFA step-up is required")
        if not decision.approval_reference.startswith("billing-cycle-approval:"):
            raise CommercialCheckoutPermissionError("governed billing-cycle approval reference is required")

    def _build_grant_command(
        self,
        *,
        order: SubscriptionCheckoutOrder,
        decision: CommercialActivationDecision,
    ) -> ApprovedSubscriptionCycleGrantCommand:
        if not self._policy.grant_bridge_enabled:
            raise CommercialCheckoutDisabledError("subscription grant bridge is disabled")
        invoice_prefix = (
            "activation-invoice:"
            if order.state
            in {
                CommercialCheckoutOrderState.PAYMENT_VERIFIED,
                CommercialCheckoutOrderState.ACTIVATION_REVIEW,
            }
            else "renewal-invoice:"
        )
        return ApprovedSubscriptionCycleGrantCommand(
            tenant_id=order.tenant_id,
            subscription_id=order.subscription_id,
            cycle_kind=SubscriptionCycleKind.ACTIVATION,
            cycle_reference=order.billing_cycle_reference,
            cycle_started_at=order.cycle_started_at,
            cycle_ends_at=order.cycle_ends_at,
            units=order.included_units,
            plan_snapshot_reference=(f"{order.plan_code}:checkout-authority-v1"),
            invoice_reference=(f"{invoice_prefix}{order.order_id}"),
            authority_reference=(f"subscription-billing-authority:commercial-checkout:{order.order_id}"),
            approval_reference=decision.approval_reference,
            approved_by=decision.actor_reference,
            occurred_at=decision.occurred_at,
        )


def available_checkout_channels(
    *,
    billing_country: str | None,
    tunisian_address_eligible: bool,
) -> tuple[CommercialCheckoutChannel, ...]:
    normalized = None if billing_country is None else billing_country.strip().upper()
    channels = [CommercialCheckoutChannel.LEMON_SQUEEZY]
    if normalized == "TN" and tunisian_address_eligible:
        channels.insert(0, CommercialCheckoutChannel.LOCAL_TUNISIA)
    return tuple(channels)


def build_checkout_view(
    *,
    order: SubscriptionCheckoutOrder | None,
    policy: CommercialCheckoutPolicy | None = None,
) -> CommercialCheckoutView:
    current = policy or CommercialCheckoutPolicy()
    if order is None:
        state = CheckoutSurfaceState.CHANNEL_SELECTION if current.enabled else CheckoutSurfaceState.DISABLED
        return CommercialCheckoutView(
            surface="customer_subscription_checkout",
            state=state,
            order_reference=None,
            selected_channel=None,
            available_channels=(),
            authoritative_price_usd=None,
            settlement_currency=None,
            settlement_amount=None,
            customer_choice_preserved=True,
            payment_verified=False,
            activation_approved=False,
            checkout_enabled=current.enabled,
            provider_runtime_enabled=current.provider_runtime_enabled,
            activation_enabled=current.activation_enabled,
            grant_bridge_enabled=current.grant_bridge_enabled,
            messages=("Checkout remains unavailable during draft review.",)
            if not current.enabled
            else ("Choose an eligible payment channel.",),
        )

    state = {
        CommercialCheckoutOrderState.DRAFT: CheckoutSurfaceState.REVIEW,
        CommercialCheckoutOrderState.AWAITING_PAYMENT: (CheckoutSurfaceState.PAYMENT_PENDING),
        CommercialCheckoutOrderState.PAYMENT_PENDING: (CheckoutSurfaceState.VERIFICATION_PENDING),
        CommercialCheckoutOrderState.PAYMENT_VERIFIED: (CheckoutSurfaceState.ACTIVATION_REVIEW),
        CommercialCheckoutOrderState.PAYMENT_REJECTED: (CheckoutSurfaceState.ERROR),
        CommercialCheckoutOrderState.ACTIVATION_REVIEW: (CheckoutSurfaceState.ACTIVATION_REVIEW),
        CommercialCheckoutOrderState.ACTIVATION_APPROVED: (CheckoutSurfaceState.SUCCESS),
        CommercialCheckoutOrderState.ACTIVATION_REJECTED: (CheckoutSurfaceState.ERROR),
        CommercialCheckoutOrderState.ACTIVATED: (CheckoutSurfaceState.SUCCESS),
        CommercialCheckoutOrderState.CANCELLED: (CheckoutSurfaceState.ERROR),
    }[order.state]

    return CommercialCheckoutView(
        surface="customer_subscription_checkout",
        state=state,
        order_reference=str(order.order_id),
        selected_channel=order.selected_channel.value,
        available_channels=tuple(
            item.value
            for item in available_checkout_channels(
                billing_country=order.billing_country,
                tunisian_address_eligible=(order.tunisian_address_eligible),
            )
        ),
        authoritative_price_usd=str(order.authoritative_price_usd),
        settlement_currency=order.settlement_currency,
        settlement_amount=str(order.settlement_amount),
        customer_choice_preserved=order.customer_choice_preserved,
        payment_verified=order.state
        in {
            CommercialCheckoutOrderState.PAYMENT_VERIFIED,
            CommercialCheckoutOrderState.ACTIVATION_REVIEW,
            CommercialCheckoutOrderState.ACTIVATION_APPROVED,
            CommercialCheckoutOrderState.ACTIVATED,
        },
        activation_approved=order.state
        in {
            CommercialCheckoutOrderState.ACTIVATION_APPROVED,
            CommercialCheckoutOrderState.ACTIVATED,
        },
        checkout_enabled=current.enabled,
        provider_runtime_enabled=current.provider_runtime_enabled,
        activation_enabled=current.activation_enabled,
        grant_bridge_enabled=current.grant_bridge_enabled,
        messages=(
            "Payment provider events are evidence only.",
            "Activation requires a platform-admin decision.",
            "Units are granted only through the governed ledger bridge.",
        ),
    )


def build_commercial_checkout_authority_status() -> dict[str, object]:
    return {
        "version": COMMERCIAL_CHECKOUT_AUTHORITY_VERSION,
        "status": COMMERCIAL_CHECKOUT_AUTHORITY_STATUS,
        "enabled": COMMERCIAL_CHECKOUT_AUTHORITY_ENABLED,
        "writes_enabled": COMMERCIAL_CHECKOUT_WRITES_ENABLED,
        "provider_runtime_enabled": (COMMERCIAL_CHECKOUT_PROVIDER_RUNTIME_ENABLED),
        "webhook_runtime_enabled": (COMMERCIAL_CHECKOUT_WEBHOOK_RUNTIME_ENABLED),
        "activation_enabled": COMMERCIAL_CHECKOUT_ACTIVATION_ENABLED,
        "grant_bridge_enabled": (COMMERCIAL_CHECKOUT_GRANT_BRIDGE_ENABLED),
        "authoritative_currency": AUTHORITATIVE_CURRENCY,
        "local_tunisia_currency": LOCAL_TUNISIA_CURRENCY,
        "lemon_squeezy_alternative_required": True,
        "tunisian_local_path_optional": True,
        "platform_admin_activation_required": True,
        "recent_mfa_step_up_required": True,
        "webhook_direct_grant_prohibited": True,
        "verified_payment_required": True,
        "customer_choice_preserved": True,
        "fail_closed_by_default": True,
    }


def _positive_decimal(value: Decimal, field_name: str) -> None:
    if not isinstance(value, Decimal):
        raise TypeError(f"{field_name} must use Decimal")
    if not value.is_finite() or value <= 0:
        raise ValueError(f"{field_name} must be positive and finite")


__all__ = [
    "AUTHORITATIVE_CURRENCY",
    "COMMERCIAL_CHECKOUT_ACTIVATION_ENABLED",
    "COMMERCIAL_CHECKOUT_AUTHORITY_ENABLED",
    "COMMERCIAL_CHECKOUT_AUTHORITY_STATUS",
    "COMMERCIAL_CHECKOUT_AUTHORITY_VERSION",
    "COMMERCIAL_CHECKOUT_GRANT_BRIDGE_ENABLED",
    "COMMERCIAL_CHECKOUT_PROVIDER_RUNTIME_ENABLED",
    "COMMERCIAL_CHECKOUT_WEBHOOK_RUNTIME_ENABLED",
    "COMMERCIAL_CHECKOUT_WRITES_ENABLED",
    "CommercialActivationDecision",
    "CommercialActivationDecisionRepository",
    "CommercialCheckoutAuthorityError",
    "CommercialCheckoutChannel",
    "CommercialCheckoutConflictError",
    "CommercialCheckoutDisabledError",
    "CommercialCheckoutEvidenceError",
    "CommercialCheckoutNotFoundError",
    "CommercialCheckoutOrderState",
    "CommercialCheckoutPermissionError",
    "CommercialCheckoutPolicy",
    "CommercialCheckoutResult",
    "CommercialCheckoutUnitOfWork",
    "CommercialCheckoutView",
    "CommercialDecisionOutcome",
    "CommercialPaymentEvidence",
    "CommercialPaymentEvidenceRepository",
    "CommercialSubscriptionCheckoutService",
    "CreateSubscriptionCheckoutCommand",
    "DecideSubscriptionActivationCommand",
    "CheckoutSurfaceState",
    "LOCAL_TUNISIA_CURRENCY",
    "PaymentEvidenceOutcome",
    "RecordPaymentEvidenceCommand",
    "SubscriptionCheckoutOrder",
    "SubscriptionCheckoutOrderRepository",
    "available_checkout_channels",
    "build_checkout_view",
    "build_commercial_checkout_authority_status",
]
