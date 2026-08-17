from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

from processual_api.admin_marketplace.commercial_offer_projection import (
    build_lemon_squeezy_draft_offer_projections,
    build_maestro_direct_draft_offer_projection,
)
from processual_api.admin_marketplace.commercial_offer_provenance import (
    build_offer_provenance,
)
from processual_api.admin_marketplace.commercial_offer_provenance_verifier import (
    VERIFIED_REASON,
    verify_commercial_offer_provenance,
)
from processual_api.billing.commercial_currency_settlement_contracts import (
    ExchangeRateQuote,
)

NOW = datetime(2026, 8, 17, 13, 45, tzinfo=UTC)


def _persisted_projection(projection):
    plan_id = uuid.uuid4()
    offer = SimpleNamespace(
        offer_code=projection.offer_code,
        plan_id=plan_id,
        sales_channel=projection.sales_channel,
        billing_period=projection.billing_period,
        currency=projection.currency,
        amount=projection.amount,
    )
    plan = SimpleNamespace(id=plan_id, plan_code=projection.plan_code)
    provenance = build_offer_provenance(projection=projection, generated_at=NOW)
    persisted = SimpleNamespace(
        evidence_json=provenance.payload(),
        evidence_sha256=provenance.digest_sha256(),
    )
    return offer, plan, persisted


def test_lemon_offer_verifies_against_canonical_source() -> None:
    projection = build_lemon_squeezy_draft_offer_projections()[0]
    offer, plan, persisted = _persisted_projection(projection)

    result = verify_commercial_offer_provenance(
        offer=offer,
        plan=plan,
        persisted=persisted,
    )

    assert result.verified is True
    assert result.reason_code == VERIFIED_REASON


def test_direct_tnd_offer_verifies_fx_math_and_window() -> None:
    quote = ExchangeRateQuote(
        base_currency="USD",
        settlement_currency="TND",
        rate=Decimal("3.100000"),
        source="qualified-fx-provider",
        reference="fx-001",
        observed_at=NOW - timedelta(minutes=1),
        expires_at=NOW + timedelta(minutes=14),
    )
    projection = build_maestro_direct_draft_offer_projection(
        plan_code="starter",
        billing_period="monthly",
        exchange_rate_quote=quote,
    )
    offer, plan, persisted = _persisted_projection(projection)

    result = verify_commercial_offer_provenance(
        offer=offer,
        plan=plan,
        persisted=persisted,
    )

    assert result.verified is True
    assert result.reason_code == VERIFIED_REASON


def test_tampered_provenance_digest_fails_closed() -> None:
    projection = build_lemon_squeezy_draft_offer_projections()[0]
    offer, plan, persisted = _persisted_projection(projection)
    persisted.evidence_json["settlement_amount"] = "999999.00"

    result = verify_commercial_offer_provenance(
        offer=offer,
        plan=plan,
        persisted=persisted,
    )

    assert result.verified is False
    assert result.reason_code == "offer_provenance_digest_mismatch"


def test_persisted_offer_amount_must_equal_provenance() -> None:
    projection = build_lemon_squeezy_draft_offer_projections()[0]
    offer, plan, persisted = _persisted_projection(projection)
    offer.amount = Decimal("1.00")

    result = verify_commercial_offer_provenance(
        offer=offer,
        plan=plan,
        persisted=persisted,
    )

    assert result.verified is False
    assert result.reason_code == "offer_provenance_amount_mismatch"
