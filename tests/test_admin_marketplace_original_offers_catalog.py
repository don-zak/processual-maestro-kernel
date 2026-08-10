from __future__ import annotations

from processual_api.admin_marketplace.catalog_router import (
    _admin_offer_payload,
    _local_payment_gate_reasons,
)
from processual_api.admin_marketplace.router import router
from processual_api.billing.offer_pricebook import list_offer_prices


def test_original_offer_catalog_route_is_registered() -> None:
    paths = {route.path for route in router.routes}
    assert "/admin-marketplace/catalog/offers" in paths


def test_draft_original_offers_are_not_local_payment_ready() -> None:
    offers = list_offer_prices(include_unlisted=True)
    assert offers

    for offer in offers:
        payload = _admin_offer_payload(offer)
        assert payload.local_payment_ready is False
        assert payload.local_payment_channel is None
        assert payload.local_payment_currency is None
        assert "offer_not_published" in payload.local_payment_gate_reasons
        assert "price_not_approved" in payload.local_payment_gate_reasons
        assert "currency_not_tnd" in payload.local_payment_gate_reasons
        assert "checkout_disabled" in payload.local_payment_gate_reasons


def test_local_payment_requires_published_tnd_checkout_offer() -> None:
    offer = {
        "pricebook_status": "published",
        "price_status": "approved",
        "currency": "TND",
        "checkout_enabled": True,
        "commercially_listed": True,
    }
    assert _local_payment_gate_reasons(offer) == ()


def test_unlisted_offer_stays_blocked_even_when_other_gates_pass() -> None:
    offer = {
        "pricebook_status": "published",
        "price_status": "approved",
        "currency": "TND",
        "checkout_enabled": True,
        "commercially_listed": False,
    }
    assert _local_payment_gate_reasons(offer) == (
        "offer_not_commercially_listed",
    )
