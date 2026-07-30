"""Admin Marketplace bridge to governed subscription checkout authority.

The bridge translates an authenticated platform-admin commercial action into
the checkout authority command. It never posts entitlement ledger entries,
calls providers, owns customer registration, or enables runtime execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Final
from uuid import UUID

from processual_api.billing.commercial_subscription_checkout_service import (
    CommercialActivationDecision,
    CommercialDecisionOutcome,
    DecideSubscriptionActivationCommand,
)

ADMIN_MARKETPLACE_CHECKOUT_BRIDGE_VERSION: Final = "2026-07-group2-admin-checkout-bridge-v1"
ADMIN_MARKETPLACE_CHECKOUT_BRIDGE_STATUS: Final = "draft_review"
ADMIN_MARKETPLACE_CHECKOUT_BRIDGE_ENABLED: Final = False
ADMIN_MARKETPLACE_COMMAND_RUNTIME_ENABLED: Final = False
ADMIN_MARKETPLACE_CUSTOMER_REGISTRATION_OWNERSHIP: Final = False
ADMIN_MARKETPLACE_DIRECT_GRANT_ALLOWED: Final = False


class AdminCommercialAction(StrEnum):
    APPROVE_ACTIVATION = "approve_activation"
    REJECT_ACTIVATION = "reject_activation"
    REQUIRE_ACTIVATION_REVIEW = "require_activation_review"


@dataclass(frozen=True, slots=True)
class AdminCommercialActor:
    user_reference: str
    authority_reference: str
    recent_mfa_step_up: bool
    session_reference: str
    correlation_reference: str

    def __post_init__(self) -> None:
        for name, value in (
            ("user_reference", self.user_reference),
            ("authority_reference", self.authority_reference),
            ("session_reference", self.session_reference),
            ("correlation_reference", self.correlation_reference),
        ):
            if not value.strip():
                raise ValueError(f"{name} must not be blank")


@dataclass(frozen=True, slots=True)
class AdminActivationAction:
    action: AdminCommercialAction
    order_id: UUID
    decision_id: UUID
    actor: AdminCommercialActor
    approval_reference: str
    reason: str
    occurred_at: datetime
    idempotency_key: str

    def __post_init__(self) -> None:
        if not self.approval_reference.strip():
            raise ValueError("approval_reference must not be blank")
        if not self.reason.strip():
            raise ValueError("reason must not be blank")
        if not self.idempotency_key.strip():
            raise ValueError("idempotency_key must not be blank")
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")


class AdminMarketplaceCheckoutBridge:
    """Pure translation boundary with explicit platform-admin denial."""

    def build_activation_command(
        self,
        action: AdminActivationAction,
    ) -> DecideSubscriptionActivationCommand:
        actor = action.actor
        if actor.authority_reference != "platform_admin":
            raise PermissionError("Admin Marketplace commercial actions require platform_admin")
        if not actor.recent_mfa_step_up:
            raise PermissionError("Admin Marketplace commercial actions require recent MFA")
        if not action.approval_reference.startswith("billing-cycle-approval:"):
            raise ValueError("approval_reference must use billing-cycle-approval")

        outcome = {
            AdminCommercialAction.APPROVE_ACTIVATION: (CommercialDecisionOutcome.APPROVED),
            AdminCommercialAction.REJECT_ACTIVATION: (CommercialDecisionOutcome.DENIED),
            AdminCommercialAction.REQUIRE_ACTIVATION_REVIEW: (CommercialDecisionOutcome.REQUIRES_REVIEW),
        }[action.action]

        decision = CommercialActivationDecision(
            decision_id=action.decision_id,
            order_id=action.order_id,
            outcome=outcome,
            actor_reference=actor.user_reference,
            authority_reference=actor.authority_reference,
            approval_reference=action.approval_reference,
            reason=action.reason,
            occurred_at=action.occurred_at,
            idempotency_key=action.idempotency_key,
        )
        return DecideSubscriptionActivationCommand(
            decision=decision,
            recent_mfa_step_up=actor.recent_mfa_step_up,
        )


def build_admin_marketplace_checkout_bridge_status() -> dict[str, object]:
    return {
        "version": ADMIN_MARKETPLACE_CHECKOUT_BRIDGE_VERSION,
        "status": ADMIN_MARKETPLACE_CHECKOUT_BRIDGE_STATUS,
        "enabled": ADMIN_MARKETPLACE_CHECKOUT_BRIDGE_ENABLED,
        "command_runtime_enabled": (ADMIN_MARKETPLACE_COMMAND_RUNTIME_ENABLED),
        "platform_admin_only": True,
        "delegated_supervisor_allowed": False,
        "customer_registration_owned": (ADMIN_MARKETPLACE_CUSTOMER_REGISTRATION_OWNERSHIP),
        "direct_grant_allowed": ADMIN_MARKETPLACE_DIRECT_GRANT_ALLOWED,
        "payment_verification_and_activation_decisions_only": True,
        "audit_context_required": True,
        "recent_mfa_step_up_required": True,
    }


__all__ = [
    "ADMIN_MARKETPLACE_CHECKOUT_BRIDGE_ENABLED",
    "ADMIN_MARKETPLACE_CHECKOUT_BRIDGE_STATUS",
    "ADMIN_MARKETPLACE_CHECKOUT_BRIDGE_VERSION",
    "ADMIN_MARKETPLACE_COMMAND_RUNTIME_ENABLED",
    "ADMIN_MARKETPLACE_CUSTOMER_REGISTRATION_OWNERSHIP",
    "ADMIN_MARKETPLACE_DIRECT_GRANT_ALLOWED",
    "AdminActivationAction",
    "AdminCommercialAction",
    "AdminCommercialActor",
    "AdminMarketplaceCheckoutBridge",
    "build_admin_marketplace_checkout_bridge_status",
]
