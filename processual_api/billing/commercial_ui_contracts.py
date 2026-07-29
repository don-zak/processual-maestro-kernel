"""Presentation-safe commercial contracts for Group 2.

This module exposes neutral commercial view models for the actual frontend.
It does not implement a standalone UI and does not activate pricing, checkout,
invoicing, settlement, or quota enforcement.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any, Final

from processual_api.billing.maestro_group1_selected_pricing import (
    build_selected_pricing_proposal,
)

COMMERCIAL_UI_CONTRACT_VERSION: Final = "2026-07-group2-commercial-ui-v1"
COMMERCIAL_UI_STATUS: Final = "foundation_only"

PRICING_APPROVED: Final = False
CHECKOUT_ENABLED: Final = False
INVOICING_ENABLED: Final = False
SETTLEMENT_ENABLED: Final = False
QUOTA_ENFORCEMENT_ENABLED: Final = False

REQUIRES_EXISTING_FRONTEND_DESIGN_SYSTEM: Final = True
STANDALONE_UI_ALLOWED: Final = False


class CommercialUiState(StrEnum):
    LOADING = "loading"
    READY = "ready"
    EMPTY = "empty"
    ERROR = "error"
    DISABLED = "disabled"
    PERMISSION_DENIED = "permission_denied"


class CommercialSurface(StrEnum):
    PUBLIC_PRICING = "public_pricing"
    SUBSCRIPTION_CHECKOUT = "subscription_checkout"
    ADMIN_MARKETPLACE = "admin_marketplace"


@dataclass(frozen=True, slots=True)
class CommercialUiMessage:
    state: CommercialUiState
    title: str
    description: str
    retry_allowed: bool
    action_label: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.state, CommercialUiState):
            raise ValueError("state must be CommercialUiState")
        if not self.title.strip():
            raise ValueError("title must not be blank")
        if not self.description.strip():
            raise ValueError("description must not be blank")
        if not isinstance(self.retry_allowed, bool):
            raise ValueError("retry_allowed must be bool")
        if self.action_label is not None and not self.action_label.strip():
            raise ValueError("action_label must not be blank")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["state"] = self.state.value
        return payload


STATE_MESSAGES: Final[dict[CommercialSurface, dict[CommercialUiState, CommercialUiMessage]]] = {
    CommercialSurface.PUBLIC_PRICING: {
        CommercialUiState.LOADING: CommercialUiMessage(
            state=CommercialUiState.LOADING,
            title="Loading plans",
            description="Preparing the latest available plan information.",
            retry_allowed=False,
        ),
        CommercialUiState.EMPTY: CommercialUiMessage(
            state=CommercialUiState.EMPTY,
            title="No plans available",
            description="Commercial plans are not available for publication yet.",
            retry_allowed=False,
        ),
        CommercialUiState.ERROR: CommercialUiMessage(
            state=CommercialUiState.ERROR,
            title="Plans could not be loaded",
            description="The plan information is temporarily unavailable.",
            retry_allowed=True,
            action_label="Try again",
        ),
        CommercialUiState.DISABLED: CommercialUiMessage(
            state=CommercialUiState.DISABLED,
            title="Pricing is under review",
            description="Prices are visible for internal review only.",
            retry_allowed=False,
        ),
    },
    CommercialSurface.SUBSCRIPTION_CHECKOUT: {
        CommercialUiState.LOADING: CommercialUiMessage(
            state=CommercialUiState.LOADING,
            title="Preparing checkout",
            description="Checking eligibility and available payment channels.",
            retry_allowed=False,
        ),
        CommercialUiState.ERROR: CommercialUiMessage(
            state=CommercialUiState.ERROR,
            title="Checkout is unavailable",
            description="The payment journey could not be prepared.",
            retry_allowed=True,
            action_label="Try again",
        ),
        CommercialUiState.DISABLED: CommercialUiMessage(
            state=CommercialUiState.DISABLED,
            title="Checkout is not enabled",
            description="Commercial activation has not been approved.",
            retry_allowed=False,
        ),
    },
    CommercialSurface.ADMIN_MARKETPLACE: {
        CommercialUiState.LOADING: CommercialUiMessage(
            state=CommercialUiState.LOADING,
            title="Loading Admin Marketplace",
            description="Preparing protected commercial controls.",
            retry_allowed=False,
        ),
        CommercialUiState.EMPTY: CommercialUiMessage(
            state=CommercialUiState.EMPTY,
            title="No commercial records",
            description="There are no records matching the current filters.",
            retry_allowed=False,
        ),
        CommercialUiState.ERROR: CommercialUiMessage(
            state=CommercialUiState.ERROR,
            title="Commercial controls could not be loaded",
            description="Protected marketplace data is temporarily unavailable.",
            retry_allowed=True,
            action_label="Try again",
        ),
        CommercialUiState.PERMISSION_DENIED: CommercialUiMessage(
            state=CommercialUiState.PERMISSION_DENIED,
            title="Access denied",
            description=("Admin Marketplace is restricted to the platform administrator."),
            retry_allowed=False,
        ),
        CommercialUiState.DISABLED: CommercialUiMessage(
            state=CommercialUiState.DISABLED,
            title="Commercial actions are disabled",
            description="Review mode does not permit commercial execution.",
            retry_allowed=False,
        ),
    },
}


def build_commercial_ui_foundation() -> dict[str, Any]:
    pricing = build_selected_pricing_proposal()
    return {
        "contract_version": COMMERCIAL_UI_CONTRACT_VERSION,
        "status": COMMERCIAL_UI_STATUS,
        "requires_existing_frontend_design_system": (REQUIRES_EXISTING_FRONTEND_DESIGN_SYSTEM),
        "standalone_ui_allowed": STANDALONE_UI_ALLOWED,
        "pricing_approved": PRICING_APPROVED,
        "checkout_enabled": CHECKOUT_ENABLED,
        "invoicing_enabled": INVOICING_ENABLED,
        "settlement_enabled": SETTLEMENT_ENABLED,
        "quota_enforcement_enabled": QUOTA_ENFORCEMENT_ENABLED,
        "pricing_proposal_status": pricing["proposal_status"],
        "surfaces": {
            surface.value: {state.value: message.to_dict() for state, message in messages.items()}
            for surface, messages in STATE_MESSAGES.items()
        },
    }
