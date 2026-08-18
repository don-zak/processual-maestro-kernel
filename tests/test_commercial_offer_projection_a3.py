from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from processual_api.admin_marketplace.commercial_offer_projection import (
    build_lemon_squeezy_draft_offer_projections,
    build_maestro_direct_draft_offer_projection,
)
from processual_api.billing.commercial_currency_settlement_contracts import (
    ExchangeRateQuote,
    calculate_tnd_settlement,
)


def quote(rate: str = "3.100000") -> ExchangeRateQuote:
    observed = datetime(2026, 8, 17, 10, 0, tzinfo=UTC)
    return ExchangeRateQuote(
        base_currency="USD",
        settlement_currency="TND",
        rate=Decimal(rate),
        source="test_fx_authority",
        reference="fx-20260817-001",
        observed_at=observed,
        expires_at=observed + timedelta(hours=1),
    )


def test_lemon_projections_are_usd_drafts_from_canonical_offers() -> None:
    offers = build_lemon_squeezy_draft_offer_projections()

    assert offers
    assert {offer.plan_code for offer in offers} == {"academic", "starter", "business"}
    for offer in offers:
        assert offer.sales_channel == "lemon_squeezy"
        assert offer.currency == "USD"
        assert offer.status == "draft"
        assert offer.billing_period in {"monthly", "annual"}
        assert offer.amount > 0
        assert offer.source_offer_id.startswith(f"{offer.plan_code}_")
        assert offer.exchange_rate_source is None


def test_tunisia_projection_requires_auditable_fx_and_remains_draft() -> None:
    fx = quote()
    offer = build_maestro_direct_draft_offer_projection(
        plan_code="starter",
        billing_period="monthly",
        exchange_rate_quote=fx,
    )

    assert offer.sales_channel == "maestro_direct"
    assert offer.currency == "TND"
    assert offer.status == "draft"
    assert offer.amount == calculate_tnd_settlement(
        amount_usd=Decimal("49.00"),
        usd_tnd_rate=fx.rate,
    )
    assert offer.exchange_rate_source == fx.source
    assert offer.exchange_rate_reference == fx.reference
    assert offer.exchange_rate_observed_at == fx.observed_at
    assert offer.exchange_rate_expires_at == fx.expires_at


@pytest.mark.parametrize("legacy_plan", ("enterprise", "enterprise_integration", "pilot_starter"))
def test_legacy_plan_aliases_cannot_create_channel_offer_projections(legacy_plan: str) -> None:
    with pytest.raises(ValueError, match="not eligible"):
        build_maestro_direct_draft_offer_projection(
            plan_code=legacy_plan,
            billing_period="monthly",
            exchange_rate_quote=quote(),
        )


def test_enterprise_review_plans_cannot_bypass_assessment_into_checkout_projection() -> None:
    with pytest.raises(ValueError, match="not eligible"):
        build_maestro_direct_draft_offer_projection(
            plan_code="enterprise_core",
            billing_period="monthly",
            exchange_rate_quote=quote(),
        )
