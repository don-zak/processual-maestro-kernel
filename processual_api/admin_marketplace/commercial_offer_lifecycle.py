from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final

from processual_api.admin_marketplace.authority import (
    AdminMarketplaceAction,
    AdminMarketplaceAuthorityContext,
    require_admin_marketplace_authority,
)
from processual_api.admin_marketplace.commercial_offer_provider_binding import (
    is_verified_lemon_squeezy_binding,
)

OFFER_PUBLICATION_PROVENANCE_REQUIRED: Final = True

_ALLOWED_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "draft": frozenset({"under_review", "retired"}),
    "under_review": frozenset({"draft", "approved", "retired"}),
    "approved": frozenset({"under_review", "published", "retired"}),
    "published": frozenset({"suspended", "retired"}),
    "suspended": frozenset({"under_review", "retired"}),
    "retired": frozenset(),
}


@dataclass(frozen=True, slots=True)
class OfferLifecycleDecision:
    current_status: str
    target_status: str
    allowed: bool
    reason_code: str
    required_action: AdminMarketplaceAction


def _action_for_target(target_status: str) -> AdminMarketplaceAction:
    if target_status == "published":
        return AdminMarketplaceAction.PUBLISH_OFFER
    if target_status == "retired":
        return AdminMarketplaceAction.RETIRE_OFFER
    return AdminMarketplaceAction.REVISE_OFFER


def evaluate_offer_lifecycle_transition(
    *,
    current_status: str,
    target_status: str,
    authority: AdminMarketplaceAuthorityContext,
    canonical_projection_verified: bool = False,
    sales_channel: str | None = None,
    provider_binding_verified: bool = False,
) -> OfferLifecycleDecision:
    current = current_status.strip().lower()
    target = target_status.strip().lower()
    action = _action_for_target(target)
    require_admin_marketplace_authority(context=authority, action=action)

    if current not in _ALLOWED_TRANSITIONS or target not in _ALLOWED_TRANSITIONS:
        return OfferLifecycleDecision(
            current_status=current,
            target_status=target,
            allowed=False,
            reason_code="unknown_offer_status",
            required_action=action,
        )

    if target not in _ALLOWED_TRANSITIONS[current]:
        return OfferLifecycleDecision(
            current_status=current,
            target_status=target,
            allowed=False,
            reason_code="offer_status_transition_not_allowed",
            required_action=action,
        )

    if (
        target == "published"
        and OFFER_PUBLICATION_PROVENANCE_REQUIRED
        and not canonical_projection_verified
    ):
        return OfferLifecycleDecision(
            current_status=current,
            target_status=target,
            allowed=False,
            reason_code="canonical_projection_provenance_required",
            required_action=action,
        )

    if (
        target == "published"
        and str(sales_channel or "").strip().lower() == "lemon_squeezy"
        and not provider_binding_verified
    ):
        return OfferLifecycleDecision(
            current_status=current,
            target_status=target,
            allowed=False,
            reason_code="verified_provider_binding_required",
            required_action=action,
        )

    return OfferLifecycleDecision(
        current_status=current,
        target_status=target,
        allowed=True,
        reason_code="offer_status_transition_allowed",
        required_action=action,
    )


def apply_offer_lifecycle_transition(
    *,
    offer: object,
    target_status: str,
    authority: AdminMarketplaceAuthorityContext,
    now: datetime,
    canonical_projection_verified: bool = False,
    provider_binding: object | None = None,
) -> OfferLifecycleDecision:
    if now.tzinfo is None:
        raise ValueError("offer lifecycle clock must be timezone-aware")

    current_status = str(getattr(offer, "status", ""))
    sales_channel = str(getattr(offer, "sales_channel", ""))
    provider_binding_verified = is_verified_lemon_squeezy_binding(
        provider_binding,
        offer_id=getattr(offer, "id", None),
    )
    decision = evaluate_offer_lifecycle_transition(
        current_status=current_status,
        target_status=target_status,
        authority=authority,
        canonical_projection_verified=canonical_projection_verified,
        sales_channel=sales_channel,
        provider_binding_verified=provider_binding_verified,
    )
    if not decision.allowed:
        return decision

    setattr(offer, "status", decision.target_status)
    setattr(offer, "updated_at", now)
    return decision


__all__ = [
    "OFFER_PUBLICATION_PROVENANCE_REQUIRED",
    "OfferLifecycleDecision",
    "apply_offer_lifecycle_transition",
    "evaluate_offer_lifecycle_transition",
]
