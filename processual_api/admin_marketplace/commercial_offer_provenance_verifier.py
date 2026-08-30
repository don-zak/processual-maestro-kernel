from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Final

from processual_api.admin_marketplace.commercial_offer_provenance import (
    CommercialOfferProvenance,
)
from processual_api.billing.commercial_currency_settlement_contracts import (
    calculate_tnd_settlement,
)
from processual_api.billing.maestro_group1_selected_pricing import (
    SELECTED_PROPOSAL_VERSION,
)
from processual_api.billing.offer_pricebook import (
    OFFER_PRICEBOOK_VERSION,
    get_offer_price,
)

VERIFIED_REASON: Final = "canonical_offer_provenance_verified"


@dataclass(frozen=True, slots=True)
class OfferProvenanceVerification:
    verified: bool
    reason_code: str


def _decimal(value: object) -> Decimal | None:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if not parsed.is_finite() or parsed <= 0:
        return None
    return parsed


def _digest(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def verify_commercial_offer_provenance(
    *,
    offer: object,
    plan: object,
    persisted: object,
) -> OfferProvenanceVerification:
    evidence = getattr(persisted, "evidence_json", None)
    stored_digest = str(getattr(persisted, "evidence_sha256", ""))
    if not isinstance(evidence, dict) or len(stored_digest) != 64:
        return OfferProvenanceVerification(False, "offer_provenance_missing")
    if _digest(evidence) != stored_digest:
        return OfferProvenanceVerification(False, "offer_provenance_digest_mismatch")

    try:
        provenance = CommercialOfferProvenance(**evidence)
    except (TypeError, ValueError, InvalidOperation):
        return OfferProvenanceVerification(False, "offer_provenance_invalid")

    offer_code = str(getattr(offer, "offer_code", "")).strip().lower()
    plan_code = str(getattr(plan, "plan_code", "")).strip().lower()
    if offer_code != provenance.offer_code.strip().lower():
        return OfferProvenanceVerification(False, "offer_provenance_offer_mismatch")
    if plan_code != provenance.plan_code.strip().lower():
        return OfferProvenanceVerification(False, "offer_provenance_plan_mismatch")
    if getattr(offer, "plan_id", None) != getattr(plan, "id", None):
        return OfferProvenanceVerification(False, "offer_plan_binding_mismatch")
    if str(getattr(offer, "sales_channel", "")) != provenance.sales_channel:
        return OfferProvenanceVerification(False, "offer_provenance_channel_mismatch")
    if str(getattr(offer, "billing_period", "")) != provenance.billing_period:
        return OfferProvenanceVerification(False, "offer_provenance_period_mismatch")
    if str(getattr(offer, "currency", "")) != provenance.settlement_currency:
        return OfferProvenanceVerification(False, "offer_provenance_currency_mismatch")

    persisted_amount = _decimal(getattr(offer, "amount", None))
    settlement_amount = _decimal(provenance.settlement_amount)
    authoritative_amount = _decimal(provenance.authoritative_price_amount)
    if persisted_amount is None or settlement_amount is None or authoritative_amount is None:
        return OfferProvenanceVerification(False, "offer_provenance_amount_invalid")
    if persisted_amount != settlement_amount:
        return OfferProvenanceVerification(False, "offer_provenance_amount_mismatch")

    if provenance.source_pricing_version != SELECTED_PROPOSAL_VERSION:
        return OfferProvenanceVerification(False, "offer_pricing_version_not_canonical")
    if provenance.source_pricebook_version != OFFER_PRICEBOOK_VERSION:
        return OfferProvenanceVerification(False, "offer_pricebook_version_not_canonical")

    source = get_offer_price(provenance.source_offer_id)
    if source is None:
        return OfferProvenanceVerification(False, "source_offer_not_found")
    if str(source["plan_id"]) != provenance.plan_code:
        return OfferProvenanceVerification(False, "source_offer_plan_mismatch")
    if str(source["pricebook_version"]) != provenance.source_pricebook_version:
        return OfferProvenanceVerification(False, "source_offer_pricebook_mismatch")
    if str(source["pricing_source_version"]) != provenance.source_pricing_version:
        return OfferProvenanceVerification(False, "source_offer_pricing_mismatch")

    price_key = (
        "monthly_amount_cents"
        if provenance.billing_period == "monthly"
        else "annual_amount_cents"
    )
    source_cents = source.get(price_key)
    if not isinstance(source_cents, int) or source_cents <= 0:
        return OfferProvenanceVerification(False, "source_offer_price_missing")
    expected_usd = (Decimal(source_cents) / Decimal("100")).quantize(Decimal("0.01"))
    if authoritative_amount != expected_usd:
        return OfferProvenanceVerification(False, "authoritative_price_mismatch")

    if provenance.sales_channel == "lemon_squeezy":
        if provenance.settlement_currency != "USD" or settlement_amount != expected_usd:
            return OfferProvenanceVerification(False, "lemon_settlement_mismatch")
        return OfferProvenanceVerification(True, VERIFIED_REASON)

    rate = _decimal(provenance.exchange_rate_value)
    if rate is None:
        return OfferProvenanceVerification(False, "direct_fx_rate_invalid")
    expected_tnd = calculate_tnd_settlement(
        amount_usd=expected_usd,
        usd_tnd_rate=rate,
    )
    if provenance.settlement_currency != "TND" or settlement_amount != expected_tnd:
        return OfferProvenanceVerification(False, "direct_settlement_mismatch")

    try:
        generated_at = datetime.fromisoformat(provenance.generated_at)
        observed_at = datetime.fromisoformat(str(provenance.exchange_rate_observed_at))
        expires_at = datetime.fromisoformat(str(provenance.exchange_rate_expires_at))
    except ValueError:
        return OfferProvenanceVerification(False, "direct_fx_window_invalid")
    if any(value.tzinfo is None for value in (generated_at, observed_at, expires_at)):
        return OfferProvenanceVerification(False, "direct_fx_window_invalid")
    if generated_at < observed_at or generated_at >= expires_at:
        return OfferProvenanceVerification(False, "direct_fx_quote_not_valid_at_projection")

    return OfferProvenanceVerification(True, VERIFIED_REASON)


__all__ = [
    "OfferProvenanceVerification",
    "VERIFIED_REASON",
    "verify_commercial_offer_provenance",
]
