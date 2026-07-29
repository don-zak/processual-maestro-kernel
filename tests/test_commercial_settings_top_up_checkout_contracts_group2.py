import pytest

from processual_api.billing.commercial_settings_top_up_checkout_contracts import (
    CHECKOUT_SESSION_CREATION_ENABLED,
    GENERAL_LEMON_SQUEEZY_CHANNEL_ENABLED,
    LOCAL_TUNISIA_CHANNEL_ENABLED,
    ORDER_PERSISTENCE_ENABLED,
    PAYMENT_COLLECTION_ENABLED,
    UNIT_GRANT_ENABLED,
    TopUpCheckoutChannel,
    TopUpCheckoutState,
    build_top_up_checkout_journey,
    evaluate_top_up_checkout_eligibility,
)


def test_inactive_subscription_requires_eligibility() -> None:
    journey = build_top_up_checkout_journey(
        plan_code="starter",
        requested_units=10_000,
        active_subscription=False,
        billing_country="TN",
        tunisian_address_eligible=True,
    )
    assert journey.state is TopUpCheckoutState.ELIGIBILITY_REQUIRED
    assert journey.available_channels == ()


def test_local_channel_requires_eligible_tunisian_address() -> None:
    eligibility = evaluate_top_up_checkout_eligibility(
        active_subscription=True,
        billing_country="TN",
        tunisian_address_eligible=False,
    )
    assert eligibility.local_channel_available is False


def test_non_tunisian_profile_never_receives_local_channel() -> None:
    eligibility = evaluate_top_up_checkout_eligibility(
        active_subscription=True,
        billing_country="FR",
        tunisian_address_eligible=True,
    )
    assert eligibility.local_channel_available is False


def test_channels_remain_disabled_during_review() -> None:
    assert LOCAL_TUNISIA_CHANNEL_ENABLED is False
    assert GENERAL_LEMON_SQUEEZY_CHANNEL_ENABLED is False

    journey = build_top_up_checkout_journey(
        plan_code="starter",
        requested_units=20_000,
        active_subscription=True,
        billing_country="TN",
        tunisian_address_eligible=True,
    )
    assert journey.state is TopUpCheckoutState.DISABLED
    assert journey.available_channels == ()


def test_unavailable_selected_channel_is_rejected() -> None:
    with pytest.raises(ValueError):
        build_top_up_checkout_journey(
            plan_code="starter",
            requested_units=20_000,
            active_subscription=True,
            billing_country="TN",
            tunisian_address_eligible=True,
            selected_channel=TopUpCheckoutChannel.LOCAL_TUNISIA,
        )


def test_commercial_side_effect_flags_remain_false() -> None:
    assert CHECKOUT_SESSION_CREATION_ENABLED is False
    assert PAYMENT_COLLECTION_ENABLED is False
    assert ORDER_PERSISTENCE_ENABLED is False
    assert UNIT_GRANT_ENABLED is False


def test_settings_surface_and_confirmation_requirements() -> None:
    journey = build_top_up_checkout_journey(
        plan_code="business",
        requested_units=25_000,
        active_subscription=True,
        billing_country="TN",
        tunisian_address_eligible=True,
    )
    assert journey.surface == "settings_billing_usage"
    assert journey.explicit_confirmation_required is True
    assert journey.duplicate_submission_protection_required is True
    assert journey.checkout_enabled is False
    assert journey.payment_enabled is False
    assert journey.persistence_enabled is False
    assert journey.unit_grant_enabled is False
