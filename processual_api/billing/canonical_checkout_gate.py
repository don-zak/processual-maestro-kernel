from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Mapping

LEGACY_CHECKOUT_FIELDS: Final = frozenset({"variant_id", "plan", "billing"})


class CanonicalCheckoutGateError(ValueError):
    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__("Checkout request is not eligible for canonical checkout.")


@dataclass(frozen=True, slots=True)
class CanonicalCheckoutRequest:
    offer_ref: str
    email: str | None


def require_canonical_checkout_request(
    body: Mapping[str, object],
) -> CanonicalCheckoutRequest:
    supplied_legacy = sorted(
        field
        for field in LEGACY_CHECKOUT_FIELDS
        if str(body.get(field) or "").strip()
    )
    if supplied_legacy:
        raise CanonicalCheckoutGateError("legacy_checkout_input_blocked")

    offer_ref = str(body.get("offer_ref") or "").strip().lower()
    if not offer_ref:
        raise CanonicalCheckoutGateError("canonical_offer_ref_required")

    email_value = str(body.get("email") or "").strip()
    return CanonicalCheckoutRequest(
        offer_ref=offer_ref,
        email=email_value or None,
    )


def require_checkout_publication_ready(
    *,
    offer_status: str,
    sales_channel: str,
    provider_binding_verified: bool,
) -> None:
    if offer_status.strip().lower() != "published":
        raise CanonicalCheckoutGateError("published_offer_required")
    if sales_channel.strip().lower() != "lemon_squeezy":
        raise CanonicalCheckoutGateError("lemon_squeezy_offer_required")
    if not provider_binding_verified:
        raise CanonicalCheckoutGateError("verified_provider_binding_required")


__all__ = [
    "CanonicalCheckoutGateError",
    "CanonicalCheckoutRequest",
    "LEGACY_CHECKOUT_FIELDS",
    "require_canonical_checkout_request",
    "require_checkout_publication_ready",
]
