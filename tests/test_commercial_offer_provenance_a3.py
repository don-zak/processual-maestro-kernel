from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from processual_api.admin_marketplace.commercial_offer_projection import (
    build_lemon_squeezy_draft_offer_projections,
    build_maestro_direct_draft_offer_projection,
)
from processual_api.admin_marketplace.commercial_offer_provenance import (
    COMMERCIAL_OFFER_PROVENANCE_VERSION,
    build_offer_provenance,
)
from processual_api.admin_marketplace.commercial_offer_provenance_persistence import (
    AdminMarketOfferProvenance,
)
from processual_api.billing.commercial_currency_settlement_contracts import (
    ExchangeRateQuote,
)

NOW = datetime(2026, 8, 17, 13, 45, tzinfo=UTC)


def _quote(*, reference: str = "fx-001") -> ExchangeRateQuote:
    return ExchangeRateQuote(
        base_currency="USD",
        settlement_currency="TND",
        rate=Decimal("3.100000"),
        source="qualified-fx-provider",
        reference=reference,
        observed_at=NOW,
        expires_at=NOW + timedelta(minutes=15),
    )


def test_lemon_provenance_keeps_authoritative_usd_identity() -> None:
    projection = build_lemon_squeezy_draft_offer_projections()[0]
    provenance = build_offer_provenance(projection=projection, generated_at=NOW)

    assert provenance.provenance_version == COMMERCIAL_OFFER_PROVENANCE_VERSION
    assert provenance.authoritative_price_currency == "USD"
    assert provenance.authoritative_price_amount == str(
        projection.authoritative_price_usd
    )
    assert provenance.settlement_currency == "USD"
    assert provenance.settlement_amount == str(projection.amount)
    assert provenance.exchange_rate_reference is None
    assert len(provenance.digest_sha256()) == 64


def test_tnd_provenance_captures_fixed_fx_evidence() -> None:
    projection = build_maestro_direct_draft_offer_projection(
        plan_code="starter",
        billing_period="monthly",
        exchange_rate_quote=_quote(),
    )
    provenance = build_offer_provenance(projection=projection, generated_at=NOW)

    assert provenance.authoritative_price_currency == "USD"
    assert provenance.settlement_currency == "TND"
    assert provenance.exchange_rate_source == "qualified-fx-provider"
    assert provenance.exchange_rate_reference == "fx-001"
    assert provenance.exchange_rate_observed_at == NOW.isoformat()


def test_provenance_digest_changes_when_fx_evidence_changes() -> None:
    first = build_offer_provenance(
        projection=build_maestro_direct_draft_offer_projection(
            plan_code="starter",
            billing_period="monthly",
            exchange_rate_quote=_quote(reference="fx-001"),
        ),
        generated_at=NOW,
    )
    second = build_offer_provenance(
        projection=build_maestro_direct_draft_offer_projection(
            plan_code="starter",
            billing_period="monthly",
            exchange_rate_quote=_quote(reference="fx-002"),
        ),
        generated_at=NOW,
    )

    assert first.digest_sha256() != second.digest_sha256()


def test_persisted_provenance_is_append_only_by_shape() -> None:
    columns = {column.name for column in AdminMarketOfferProvenance.__table__.columns}

    assert "created_at" in columns
    assert "updated_at" not in columns
    assert "offer_id" in columns
    assert "evidence_sha256" in columns
