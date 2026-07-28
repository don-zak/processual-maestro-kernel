"""Public-checkout channel eligibility derived from authoritative customer addresses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Mapping

TUNISIA_COUNTRY_CODE: Final = "TN"
MAESTRO_DIRECT_CHANNEL: Final = "maestro_direct"
LEMON_SQUEEZY_CHANNEL: Final = "lemon_squeezy"


@dataclass(frozen=True, slots=True)
class CheckoutChannelOptions:
    """Safe public representation of the checkout channels available to a customer."""

    address_country_code: str | None
    eligible_channels: tuple[str, ...]
    show_tunisia_payment_option: bool
    customer_choice_allowed: bool
    address_required: bool

    def as_public_dict(self) -> dict[str, object]:
        return {
            "address_country_code": self.address_country_code,
            "eligible_channels": list(self.eligible_channels),
            "show_tunisia_payment_option": self.show_tunisia_payment_option,
            "customer_choice_allowed": self.customer_choice_allowed,
            "address_required": self.address_required,
        }


def normalize_country_code(value: object) -> str | None:
    """Normalize a two-letter country code without inferring it from IP or locale."""

    if not isinstance(value, str):
        return None

    normalized = value.strip().upper()
    if len(normalized) != 2 or not normalized.isalpha():
        return None

    return normalized


def authoritative_billing_country(current_user: Mapping[str, object]) -> str | None:
    """Read the billing country only from server-issued authenticated user claims.

    This deliberately ignores request-body, query-string, browser-locale, timezone,
    phone number, and IP-geolocation values.
    """

    billing_address = current_user.get("billing_address")
    if isinstance(billing_address, Mapping):
        country_code = normalize_country_code(billing_address.get("country_code") or billing_address.get("country"))
        if country_code is not None:
            return country_code

    return normalize_country_code(current_user.get("billing_country_code") or current_user.get("address_country_code"))


def resolve_checkout_channel_options(
    *,
    current_user: Mapping[str, object],
    maestro_direct_enabled: bool,
    admin_review_required: bool = False,
) -> CheckoutChannelOptions:
    """Resolve public checkout channels using the authoritative billing address."""

    country_code = authoritative_billing_country(current_user)

    tunisian_local_payment_allowed = (
        country_code == TUNISIA_COUNTRY_CODE and maestro_direct_enabled and not admin_review_required
    )

    if tunisian_local_payment_allowed:
        channels = (MAESTRO_DIRECT_CHANNEL, LEMON_SQUEEZY_CHANNEL)
    else:
        channels = (LEMON_SQUEEZY_CHANNEL,)

    return CheckoutChannelOptions(
        address_country_code=country_code,
        eligible_channels=channels,
        show_tunisia_payment_option=tunisian_local_payment_allowed,
        customer_choice_allowed=tunisian_local_payment_allowed,
        address_required=country_code is None,
    )


def require_tunisia_payment_eligibility(
    *,
    current_user: Mapping[str, object],
    maestro_direct_enabled: bool,
    admin_review_required: bool = False,
) -> CheckoutChannelOptions:
    """Reject direct access to the Tunisia-payment flow when it is not eligible."""

    options = resolve_checkout_channel_options(
        current_user=current_user,
        maestro_direct_enabled=maestro_direct_enabled,
        admin_review_required=admin_review_required,
    )
    if not options.show_tunisia_payment_option:
        raise PermissionError("tunisia_payment_not_eligible")

    return options
