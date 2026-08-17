from __future__ import annotations

import pytest

from processual_api.billing.canonical_checkout_gate import (
    CanonicalCheckoutGateError,
    require_canonical_checkout_request,
    require_checkout_publication_ready,
)


@pytest.mark.parametrize(
    "body",
    (
        {"variant_id": "123", "offer_ref": "starter-monthly"},
        {"plan": "professional", "offer_ref": "starter-monthly"},
        {"plan": "enterprise", "billing": "yearly", "offer_ref": "starter-monthly"},
    ),
)
def test_legacy_checkout_inputs_are_blocked(body: dict[str, object]) -> None:
    with pytest.raises(CanonicalCheckoutGateError) as captured:
        require_canonical_checkout_request(body)

    assert captured.value.reason_code == "legacy_checkout_input_blocked"


def test_checkout_requires_canonical_offer_identity() -> None:
    with pytest.raises(CanonicalCheckoutGateError) as captured:
        require_canonical_checkout_request({"email": "buyer@example.com"})

    assert captured.value.reason_code == "canonical_offer_ref_required"


def test_checkout_accepts_only_offer_ref_as_commercial_identity() -> None:
    request = require_canonical_checkout_request(
        {"offer_ref": "Starter-Monthly", "email": " buyer@example.com "}
    )

    assert request.offer_ref == "starter-monthly"
    assert request.email == "buyer@example.com"


def test_checkout_requires_published_lemon_offer_and_verified_binding() -> None:
    with pytest.raises(CanonicalCheckoutGateError) as captured:
        require_checkout_publication_ready(
            offer_status="approved",
            sales_channel="lemon_squeezy",
            provider_binding_verified=True,
        )
    assert captured.value.reason_code == "published_offer_required"

    with pytest.raises(CanonicalCheckoutGateError) as captured:
        require_checkout_publication_ready(
            offer_status="published",
            sales_channel="maestro_direct",
            provider_binding_verified=True,
        )
    assert captured.value.reason_code == "lemon_squeezy_offer_required"

    with pytest.raises(CanonicalCheckoutGateError) as captured:
        require_checkout_publication_ready(
            offer_status="published",
            sales_channel="lemon_squeezy",
            provider_binding_verified=False,
        )
    assert captured.value.reason_code == "verified_provider_binding_required"


def test_checkout_gate_allows_verified_published_lemon_offer() -> None:
    require_checkout_publication_ready(
        offer_status="published",
        sales_channel="lemon_squeezy",
        provider_binding_verified=True,
    )
