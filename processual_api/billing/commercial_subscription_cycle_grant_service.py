"""Governed monthly subscription-cycle entitlement grant service.

This module accepts only an already-approved billing-cycle authority record.
It does not activate subscriptions, charge customers, create invoices, call a
payment provider, or wire entitlement writes into runtime execution.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Final
from uuid import UUID, uuid4

from processual_api.billing.commercial_entitlement_grant_posting_service import (
    EntitlementGrantPostingResult,
    EntitlementGrantPostingService,
    MonthlySubscriptionGrantCommand,
)
from processual_api.billing.commercial_entitlement_ledger_persistence_contracts import (
    EntitlementLedgerUnitOfWork,
)

SUBSCRIPTION_CYCLE_GRANT_SERVICE_VERSION: Final = "2026-07-group2-subscription-cycle-grant-v1"
SUBSCRIPTION_CYCLE_GRANT_SERVICE_STATUS: Final = "draft_review"
SUBSCRIPTION_CYCLE_GRANT_SERVICE_ENABLED: Final = False
SUBSCRIPTION_CYCLE_GRANT_WRITES_ENABLED: Final = False
SUBSCRIPTION_CYCLE_GRANT_RUNTIME_WIRING_ENABLED: Final = False
SUBSCRIPTION_CYCLE_GRANT_COMMERCIAL_ACTIVATION_ENABLED: Final = False


class SubscriptionCycleGrantServiceError(RuntimeError):
    """Base error for governed subscription-cycle grants."""


class SubscriptionCycleGrantDisabledError(SubscriptionCycleGrantServiceError):
    """Raised when the review-only grant boundary remains disabled."""


class SubscriptionCycleGrantAuthorityError(SubscriptionCycleGrantServiceError):
    """Raised when billing-cycle authority evidence is incomplete."""


class SubscriptionCycleKind(StrEnum):
    ACTIVATION = "activation"
    RENEWAL = "renewal"


@dataclass(frozen=True, slots=True)
class SubscriptionCycleGrantPolicy:
    enabled: bool = SUBSCRIPTION_CYCLE_GRANT_SERVICE_ENABLED
    writes_enabled: bool = SUBSCRIPTION_CYCLE_GRANT_WRITES_ENABLED
    runtime_wiring_enabled: bool = SUBSCRIPTION_CYCLE_GRANT_RUNTIME_WIRING_ENABLED
    commercial_activation_enabled: bool = SUBSCRIPTION_CYCLE_GRANT_COMMERCIAL_ACTIVATION_ENABLED


@dataclass(frozen=True, slots=True)
class ApprovedSubscriptionCycleGrantCommand:
    tenant_id: UUID
    subscription_id: UUID
    cycle_kind: SubscriptionCycleKind
    cycle_reference: str
    cycle_started_at: datetime
    cycle_ends_at: datetime
    units: int
    plan_snapshot_reference: str
    invoice_reference: str
    authority_reference: str
    approval_reference: str
    approved_by: str
    occurred_at: datetime

    def __post_init__(self) -> None:
        if self.units <= 0:
            raise ValueError("units must be positive")
        for value, field_name in (
            (self.cycle_reference, "cycle_reference"),
            (self.plan_snapshot_reference, "plan_snapshot_reference"),
            (self.invoice_reference, "invoice_reference"),
            (self.authority_reference, "authority_reference"),
            (self.approval_reference, "approval_reference"),
            (self.approved_by, "approved_by"),
        ):
            if not value.strip():
                raise ValueError(f"{field_name} must not be blank")

        for value, field_name in (
            (self.cycle_started_at, "cycle_started_at"),
            (self.cycle_ends_at, "cycle_ends_at"),
            (self.occurred_at, "occurred_at"),
        ):
            if value.tzinfo is None:
                raise ValueError(f"{field_name} must be timezone-aware")

        if self.cycle_ends_at <= self.cycle_started_at:
            raise ValueError("cycle_ends_at must be after cycle_started_at")

    @property
    def idempotency_key(self) -> str:
        return f"subscription-cycle-grant:{self.subscription_id}:{self.cycle_reference}"

    @property
    def governed_plan_snapshot_reference(self) -> str:
        return (
            f"{self.plan_snapshot_reference}|"
            f"cycle-kind:{self.cycle_kind.value}|"
            f"authority:{self.authority_reference}|"
            f"approval:{self.approval_reference}|"
            f"approved-by:{self.approved_by}"
        )


@dataclass(frozen=True, slots=True)
class SubscriptionCycleGrantResult:
    subscription_id: UUID
    cycle_reference: str
    cycle_kind: SubscriptionCycleKind
    duplicate: bool
    committed: bool
    ledger_result: EntitlementGrantPostingResult


class CommercialSubscriptionCycleGrantService:
    def __init__(
        self,
        *,
        unit_of_work_factory: Callable[[], EntitlementLedgerUnitOfWork],
        policy: SubscriptionCycleGrantPolicy | None = None,
        entry_id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._policy = policy or SubscriptionCycleGrantPolicy()
        self._posting_service = EntitlementGrantPostingService(
            unit_of_work_factory,
            entry_id_factory=entry_id_factory,
        )

    async def post_approved_cycle(
        self,
        command: ApprovedSubscriptionCycleGrantCommand,
    ) -> SubscriptionCycleGrantResult:
        self._require(
            self._policy.enabled,
            "subscription cycle grant service is disabled",
        )
        self._require(
            self._policy.writes_enabled,
            "subscription cycle grant writes are disabled",
        )
        self._validate_authority(command)

        result = await self._posting_service.post_monthly_subscription_grant(
            MonthlySubscriptionGrantCommand(
                tenant_id=command.tenant_id,
                subscription_id=command.subscription_id,
                units=command.units,
                billing_cycle_reference=(command.cycle_reference),
                plan_snapshot_reference=(command.governed_plan_snapshot_reference),
                invoice_reference=command.invoice_reference,
                idempotency_key=command.idempotency_key,
                occurred_at=command.occurred_at,
            )
        )

        return SubscriptionCycleGrantResult(
            subscription_id=command.subscription_id,
            cycle_reference=command.cycle_reference,
            cycle_kind=command.cycle_kind,
            duplicate=result.duplicate,
            committed=not result.duplicate,
            ledger_result=result,
        )

    @staticmethod
    def _validate_authority(
        command: ApprovedSubscriptionCycleGrantCommand,
    ) -> None:
        if not command.authority_reference.startswith("subscription-billing-authority:"):
            raise SubscriptionCycleGrantAuthorityError("subscription billing authority reference is invalid")
        if not command.approval_reference.startswith("billing-cycle-approval:"):
            raise SubscriptionCycleGrantAuthorityError("billing cycle approval reference is invalid")
        if command.cycle_kind is SubscriptionCycleKind.ACTIVATION:
            if not command.invoice_reference.startswith("activation-invoice:"):
                raise SubscriptionCycleGrantAuthorityError("activation cycle requires activation invoice evidence")
        elif not command.invoice_reference.startswith("renewal-invoice:"):
            raise SubscriptionCycleGrantAuthorityError("renewal cycle requires renewal invoice evidence")

    @staticmethod
    def _require(enabled: bool, message: str) -> None:
        if not enabled:
            raise SubscriptionCycleGrantDisabledError(message)


def build_subscription_cycle_grant_status() -> dict[str, object]:
    return {
        "version": SUBSCRIPTION_CYCLE_GRANT_SERVICE_VERSION,
        "status": SUBSCRIPTION_CYCLE_GRANT_SERVICE_STATUS,
        "enabled": SUBSCRIPTION_CYCLE_GRANT_SERVICE_ENABLED,
        "writes_enabled": SUBSCRIPTION_CYCLE_GRANT_WRITES_ENABLED,
        "runtime_wiring_enabled": (SUBSCRIPTION_CYCLE_GRANT_RUNTIME_WIRING_ENABLED),
        "commercial_activation_enabled": (SUBSCRIPTION_CYCLE_GRANT_COMMERCIAL_ACTIVATION_ENABLED),
        "approved_cycle_authority_required": True,
        "activation_and_renewal_separated": True,
        "deterministic_cycle_idempotency": True,
        "rollover_preserved": True,
        "checkout_calls_allowed": False,
        "payment_provider_calls_allowed": False,
        "subscription_activation_performed": False,
        "fail_closed_by_default": True,
    }


__all__ = [
    "SUBSCRIPTION_CYCLE_GRANT_COMMERCIAL_ACTIVATION_ENABLED",
    "SUBSCRIPTION_CYCLE_GRANT_RUNTIME_WIRING_ENABLED",
    "SUBSCRIPTION_CYCLE_GRANT_SERVICE_ENABLED",
    "SUBSCRIPTION_CYCLE_GRANT_SERVICE_STATUS",
    "SUBSCRIPTION_CYCLE_GRANT_SERVICE_VERSION",
    "SUBSCRIPTION_CYCLE_GRANT_WRITES_ENABLED",
    "ApprovedSubscriptionCycleGrantCommand",
    "CommercialSubscriptionCycleGrantService",
    "SubscriptionCycleGrantAuthorityError",
    "SubscriptionCycleGrantDisabledError",
    "SubscriptionCycleGrantPolicy",
    "SubscriptionCycleGrantResult",
    "SubscriptionCycleKind",
    "build_subscription_cycle_grant_status",
]
