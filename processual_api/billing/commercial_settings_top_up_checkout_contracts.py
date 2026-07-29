"""Checkout journey contracts for Settings quota top-ups.

The contracts coordinate eligibility, channel choice, confirmation, pending,
success, and failure states. They do not create checkout sessions, collect
payments, persist orders, or grant units.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any, Final

from processual_api.billing.commercial_quota_top_up_contracts import (
    quote_top_up,
)
from processual_api.billing.commercial_settings_top_up_ui_contracts import (
    build_settings_top_up_view_model,
)

TOP_UP_CHECKOUT_CONTRACT_VERSION: Final = "2026-07-group2-settings-top-up-checkout-v1"
TOP_UP_CHECKOUT_STATUS: Final = "draft_review"

CHECKOUT_SESSION_CREATION_ENABLED: Final = False
PAYMENT_COLLECTION_ENABLED: Final = False
ORDER_PERSISTENCE_ENABLED: Final = False
UNIT_GRANT_ENABLED: Final = False

LOCAL_TUNISIA_CHANNEL_ENABLED: Final = False
GENERAL_LEMON_SQUEEZY_CHANNEL_ENABLED: Final = False

REQUIRES_ACTIVE_SUBSCRIPTION: Final = True
REQUIRES_ELIGIBLE_BILLING_PROFILE: Final = True
REQUIRES_EXPLICIT_CONFIRMATION: Final = True
DUPLICATE_SUBMISSION_PROTECTION_REQUIRED: Final = True


class TopUpCheckoutChannel(StrEnum):
    LOCAL_TUNISIA = "local_tunisia"
    LEMON_SQUEEZY = "lemon_squeezy"


class TopUpCheckoutState(StrEnum):
    LOADING = "loading"
    ELIGIBILITY_REQUIRED = "eligibility_required"
    CHANNEL_SELECTION = "channel_selection"
    REVIEW = "review"
    CONFIRMATION_REQUIRED = "confirmation_required"
    PAYMENT_PENDING = "payment_pending"
    PAYMENT_SUCCEEDED = "payment_succeeded"
    PAYMENT_FAILED = "payment_failed"
    VERIFICATION_PENDING = "verification_pending"
    GRANT_PENDING = "grant_pending"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    DISABLED = "disabled"


@dataclass(frozen=True, slots=True)
class TopUpCheckoutEligibility:
    active_subscription: bool
    billing_country: str | None
    tunisian_address_eligible: bool
    local_channel_available: bool
    lemon_squeezy_available: bool

    def __post_init__(self) -> None:
        if self.billing_country is not None:
            normalized = self.billing_country.strip().upper()
            if len(normalized) != 2:
                raise ValueError("billing_country must be an ISO alpha-2 code")
        if self.local_channel_available and not self.tunisian_address_eligible:
            raise ValueError("local channel requires eligible Tunisian address")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class TopUpCheckoutJourney:
    surface: str
    plan_code: str
    requested_units: int
    quote: dict[str, Any]
    eligibility: dict[str, Any]
    available_channels: tuple[str, ...]
    selected_channel: str | None
    state: TopUpCheckoutState
    explicit_confirmation_required: bool
    duplicate_submission_protection_required: bool
    checkout_enabled: bool
    payment_enabled: bool
    persistence_enabled: bool
    unit_grant_enabled: bool

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["state"] = self.state.value
        payload["available_channels"] = list(self.available_channels)
        return payload


def evaluate_top_up_checkout_eligibility(
    *,
    active_subscription: bool,
    billing_country: str | None,
    tunisian_address_eligible: bool,
) -> TopUpCheckoutEligibility:
    normalized_country = None if billing_country is None else billing_country.strip().upper()
    local_available = (
        active_subscription
        and normalized_country == "TN"
        and tunisian_address_eligible
        and LOCAL_TUNISIA_CHANNEL_ENABLED
    )
    general_available = active_subscription and GENERAL_LEMON_SQUEEZY_CHANNEL_ENABLED

    return TopUpCheckoutEligibility(
        active_subscription=active_subscription,
        billing_country=normalized_country,
        tunisian_address_eligible=tunisian_address_eligible,
        local_channel_available=local_available,
        lemon_squeezy_available=general_available,
    )


def build_top_up_checkout_journey(
    *,
    plan_code: str,
    requested_units: int,
    active_subscription: bool,
    billing_country: str | None,
    tunisian_address_eligible: bool,
    selected_channel: TopUpCheckoutChannel | None = None,
) -> TopUpCheckoutJourney:
    view = build_settings_top_up_view_model(plan_code)
    quote = quote_top_up(plan_code, requested_units)
    eligibility = evaluate_top_up_checkout_eligibility(
        active_subscription=active_subscription,
        billing_country=billing_country,
        tunisian_address_eligible=tunisian_address_eligible,
    )

    channels: list[str] = []
    if eligibility.local_channel_available:
        channels.append(TopUpCheckoutChannel.LOCAL_TUNISIA.value)
    if eligibility.lemon_squeezy_available:
        channels.append(TopUpCheckoutChannel.LEMON_SQUEEZY.value)

    if selected_channel is not None and selected_channel.value not in channels:
        raise ValueError("selected channel is not available")

    if not active_subscription:
        state = TopUpCheckoutState.ELIGIBILITY_REQUIRED
    elif not channels:
        state = TopUpCheckoutState.DISABLED
    elif selected_channel is None:
        state = TopUpCheckoutState.CHANNEL_SELECTION
    else:
        state = TopUpCheckoutState.REVIEW

    return TopUpCheckoutJourney(
        surface=view.surface.value,
        plan_code=plan_code,
        requested_units=requested_units,
        quote=quote.to_dict(),
        eligibility=eligibility.to_dict(),
        available_channels=tuple(channels),
        selected_channel=(None if selected_channel is None else selected_channel.value),
        state=state,
        explicit_confirmation_required=REQUIRES_EXPLICIT_CONFIRMATION,
        duplicate_submission_protection_required=(DUPLICATE_SUBMISSION_PROTECTION_REQUIRED),
        checkout_enabled=CHECKOUT_SESSION_CREATION_ENABLED,
        payment_enabled=PAYMENT_COLLECTION_ENABLED,
        persistence_enabled=ORDER_PERSISTENCE_ENABLED,
        unit_grant_enabled=UNIT_GRANT_ENABLED,
    )
