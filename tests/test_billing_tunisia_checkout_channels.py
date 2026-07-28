from __future__ import annotations

import pytest

from processual_api.billing.checkout_channels import (
    LEMON_SQUEEZY_CHANNEL,
    MAESTRO_DIRECT_CHANNEL,
    authoritative_billing_country,
    require_tunisia_payment_eligibility,
    resolve_checkout_channel_options,
)


def test_tunisian_billing_address_receives_both_checkout_channels() -> None:
    options = resolve_checkout_channel_options(
        current_user={
            "sub": "customer-tn",
            "billing_address": {"country_code": "tn"},
        },
        maestro_direct_enabled=True,
    )

    assert options.address_country_code == "TN"
    assert options.eligible_channels == (
        MAESTRO_DIRECT_CHANNEL,
        LEMON_SQUEEZY_CHANNEL,
    )
    assert options.show_tunisia_payment_option is True
    assert options.customer_choice_allowed is True
    assert options.address_required is False


@pytest.mark.parametrize("country_code", ["FR", "DE", "US", "DZ", "LY"])
def test_non_tunisian_addresses_receive_lemon_squeezy_only(
    country_code: str,
) -> None:
    options = resolve_checkout_channel_options(
        current_user={
            "sub": "customer-global",
            "billing_address": {"country_code": country_code},
        },
        maestro_direct_enabled=True,
    )

    assert options.address_country_code == country_code
    assert options.eligible_channels == (LEMON_SQUEEZY_CHANNEL,)
    assert options.show_tunisia_payment_option is False
    assert options.customer_choice_allowed is False


def test_missing_address_never_exposes_tunisia_payment() -> None:
    options = resolve_checkout_channel_options(
        current_user={"sub": "customer-without-address"},
        maestro_direct_enabled=True,
    )

    assert options.address_country_code is None
    assert options.eligible_channels == (LEMON_SQUEEZY_CHANNEL,)
    assert options.show_tunisia_payment_option is False
    assert options.address_required is True


def test_invalid_country_code_never_exposes_tunisia_payment() -> None:
    options = resolve_checkout_channel_options(
        current_user={
            "sub": "customer-invalid-address",
            "billing_address": {"country_code": "Tunisia"},
        },
        maestro_direct_enabled=True,
    )

    assert options.show_tunisia_payment_option is False
    assert options.eligible_channels == (LEMON_SQUEEZY_CHANNEL,)


def test_disabled_local_channel_never_appears_for_tunisian_address() -> None:
    options = resolve_checkout_channel_options(
        current_user={
            "sub": "customer-tn",
            "billing_address": {"country_code": "TN"},
        },
        maestro_direct_enabled=False,
    )

    assert options.show_tunisia_payment_option is False
    assert options.eligible_channels == (LEMON_SQUEEZY_CHANNEL,)


def test_admin_review_blocks_local_channel() -> None:
    options = resolve_checkout_channel_options(
        current_user={
            "sub": "customer-tn",
            "billing_address": {"country_code": "TN"},
        },
        maestro_direct_enabled=True,
        admin_review_required=True,
    )

    assert options.show_tunisia_payment_option is False
    assert options.eligible_channels == (LEMON_SQUEEZY_CHANNEL,)


def test_request_supplied_country_is_not_part_of_the_policy() -> None:
    current_user = {
        "sub": "customer-fr",
        "billing_address": {"country_code": "FR"},
    }

    assert authoritative_billing_country(current_user) == "FR"

    options = resolve_checkout_channel_options(
        current_user=current_user,
        maestro_direct_enabled=True,
    )
    assert options.show_tunisia_payment_option is False


def test_direct_tunisia_flow_rejects_non_tunisian_address() -> None:
    with pytest.raises(
        PermissionError,
        match="tunisia_payment_not_eligible",
    ):
        require_tunisia_payment_eligibility(
            current_user={
                "sub": "customer-fr",
                "billing_address": {"country_code": "FR"},
            },
            maestro_direct_enabled=True,
        )


def test_direct_tunisia_flow_accepts_tunisian_address() -> None:
    options = require_tunisia_payment_eligibility(
        current_user={
            "sub": "customer-tn",
            "billing_address": {"country_code": "TN"},
        },
        maestro_direct_enabled=True,
    )

    assert options.show_tunisia_payment_option is True


def test_authoritative_country_resolver_supports_database_country() -> None:
    from processual_api.billing.checkout_channels import (
        resolve_checkout_channel_options_for_country,
    )

    options = resolve_checkout_channel_options_for_country(
        billing_country_code="tn",
        maestro_direct_enabled=True,
    )

    assert options.address_country_code == "TN"
    assert options.eligible_channels == (
        MAESTRO_DIRECT_CHANNEL,
        LEMON_SQUEEZY_CHANNEL,
    )
    assert options.show_tunisia_payment_option is True


def test_authoritative_country_resolver_hides_tunisia_for_other_country() -> None:
    from processual_api.billing.checkout_channels import (
        resolve_checkout_channel_options_for_country,
    )

    options = resolve_checkout_channel_options_for_country(
        billing_country_code="FR",
        maestro_direct_enabled=True,
    )

    assert options.address_country_code == "FR"
    assert options.eligible_channels == (LEMON_SQUEEZY_CHANNEL,)
    assert options.show_tunisia_payment_option is False
