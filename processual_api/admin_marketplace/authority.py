from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

from processual_api.admin_marketplace.errors import (
    AdminMarketplaceAuthorityDeniedError,
    AdminMarketplaceStepUpRequiredError,
)

PLATFORM_ADMIN_AUTHORITY = "platform_admin"
PROHIBITED_MARKETPLACE_AUTHORITIES = frozenset(
    {
        "platform_supervisor",
        "billing_admin",
        "viewer_admin",
        "owner_admin",
        "admin",
        "*",
        "admin:*",
        "commercial:*",
        "marketplace:*",
    }
)


class AdminMarketplaceAction(StrEnum):
    VIEW_CATALOG = "marketplace.catalog.view"
    VIEW_AUDIT = "marketplace.audit.view"
    CREATE_OFFER = "marketplace.offer.create"
    REVISE_OFFER = "marketplace.offer.revise"
    PUBLISH_OFFER = "marketplace.offer.publish"
    RETIRE_OFFER = "marketplace.offer.retire"
    VERIFY_PAYMENT = "marketplace.payment.verify"
    DECIDE_ORDER = "marketplace.order.decide"
    ACTIVATE_SUBSCRIPTION = "marketplace.subscription.activate"
    CHANGE_CHANNEL_ELIGIBILITY = "marketplace.channel_eligibility.change"


SENSITIVE_ACTIONS = frozenset(
    {
        AdminMarketplaceAction.CREATE_OFFER,
        AdminMarketplaceAction.REVISE_OFFER,
        AdminMarketplaceAction.PUBLISH_OFFER,
        AdminMarketplaceAction.RETIRE_OFFER,
        AdminMarketplaceAction.VERIFY_PAYMENT,
        AdminMarketplaceAction.DECIDE_ORDER,
        AdminMarketplaceAction.ACTIVATE_SUBSCRIPTION,
        AdminMarketplaceAction.CHANGE_CHANNEL_ELIGIBILITY,
    }
)


@dataclass(frozen=True, slots=True)
class AdminMarketplaceAuthorityContext:
    user_id: str
    session_id: str
    platform_authorities: frozenset[str]
    active_platform_admin: bool
    recent_mfa_step_up: bool

    def __post_init__(self) -> None:
        if not self.user_id.strip() or not self.session_id.strip():
            raise AdminMarketplaceAuthorityDeniedError("Identity user and session are required.")
        normalized = frozenset(value.strip().lower() for value in self.platform_authorities if value.strip())
        object.__setattr__(self, "platform_authorities", normalized)


@dataclass(frozen=True, slots=True)
class AdminMarketplaceAuthorityDecision:
    action: AdminMarketplaceAction
    allowed: bool
    reason_code: str
    step_up_required: bool


def evaluate_admin_marketplace_authority(
    *,
    context: AdminMarketplaceAuthorityContext,
    action: AdminMarketplaceAction,
) -> AdminMarketplaceAuthorityDecision:
    if not isinstance(action, AdminMarketplaceAction):
        return AdminMarketplaceAuthorityDecision(
            action=AdminMarketplaceAction.VIEW_CATALOG,
            allowed=False,
            reason_code="unknown_marketplace_action_denied",
            step_up_required=True,
        )

    authorities = context.platform_authorities
    if any("*" in authority for authority in authorities):
        return AdminMarketplaceAuthorityDecision(
            action=action,
            allowed=False,
            reason_code="wildcard_authority_denied",
            step_up_required=action in SENSITIVE_ACTIONS,
        )
    if authorities & PROHIBITED_MARKETPLACE_AUTHORITIES:
        return AdminMarketplaceAuthorityDecision(
            action=action,
            allowed=False,
            reason_code="non_super_administrator_denied",
            step_up_required=action in SENSITIVE_ACTIONS,
        )
    if PLATFORM_ADMIN_AUTHORITY not in authorities or not context.active_platform_admin:
        return AdminMarketplaceAuthorityDecision(
            action=action,
            allowed=False,
            reason_code="active_platform_admin_required",
            step_up_required=action in SENSITIVE_ACTIONS,
        )
    if action in SENSITIVE_ACTIONS and not context.recent_mfa_step_up:
        return AdminMarketplaceAuthorityDecision(
            action=action,
            allowed=False,
            reason_code="recent_mfa_step_up_required",
            step_up_required=True,
        )
    return AdminMarketplaceAuthorityDecision(
        action=action,
        allowed=True,
        reason_code="super_administrator_authorized",
        step_up_required=action in SENSITIVE_ACTIONS,
    )


def require_admin_marketplace_authority(
    *,
    context: AdminMarketplaceAuthorityContext,
    action: AdminMarketplaceAction,
) -> AdminMarketplaceAuthorityDecision:
    decision = evaluate_admin_marketplace_authority(context=context, action=action)
    if decision.allowed:
        return decision
    if decision.reason_code == "recent_mfa_step_up_required":
        raise AdminMarketplaceStepUpRequiredError("Recent MFA step-up is required.")
    raise AdminMarketplaceAuthorityDeniedError("Exclusive super-administrator authority is required.")


def authority_context(
    *,
    user_id: str,
    session_id: str,
    platform_authorities: Iterable[str],
    active_platform_admin: bool,
    recent_mfa_step_up: bool,
) -> AdminMarketplaceAuthorityContext:
    return AdminMarketplaceAuthorityContext(
        user_id=user_id,
        session_id=session_id,
        platform_authorities=frozenset(platform_authorities),
        active_platform_admin=active_platform_admin,
        recent_mfa_step_up=recent_mfa_step_up,
    )


__all__ = [
    "AdminMarketplaceAction",
    "AdminMarketplaceAuthorityContext",
    "AdminMarketplaceAuthorityDecision",
    "PLATFORM_ADMIN_AUTHORITY",
    "PROHIBITED_MARKETPLACE_AUTHORITIES",
    "SENSITIVE_ACTIONS",
    "authority_context",
    "evaluate_admin_marketplace_authority",
    "require_admin_marketplace_authority",
]
