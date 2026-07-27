import pytest

from processual_api.admin_marketplace.contracts import (
    ChannelEligibilityStatus,
    CustomerChannelSelectionContract,
    SalesChannel,
    SalesChannelEligibilityContract,
)
from processual_api.admin_marketplace.errors import AdminMarketplaceError


def test_tunisian_customer_may_choose_direct_or_lemon_squeezy() -> None:
    eligibility = SalesChannelEligibilityContract(
        country_code="TN",
        maestro_direct_status=ChannelEligibilityStatus.ELIGIBLE,
        lemon_squeezy_status=ChannelEligibilityStatus.ELIGIBLE,
        customer_choice_allowed=True,
        admin_review_required=False,
    )
    assert eligibility.country_code == "TN"
    assert eligibility.customer_choice_allowed is True

    selection = CustomerChannelSelectionContract(
        customer_id="institution_001",
        selected_channel=SalesChannel.LEMON_SQUEEZY,
        eligible_channels=frozenset({SalesChannel.MAESTRO_DIRECT, SalesChannel.LEMON_SQUEEZY}),
    )
    assert selection.selected_channel is SalesChannel.LEMON_SQUEEZY


def test_ineligible_channel_requires_documented_reason() -> None:
    with pytest.raises(AdminMarketplaceError, match="restriction_reason"):
        SalesChannelEligibilityContract(
            country_code="TN",
            maestro_direct_status=ChannelEligibilityStatus.ELIGIBLE,
            lemon_squeezy_status=ChannelEligibilityStatus.INELIGIBLE,
            customer_choice_allowed=False,
            admin_review_required=True,
        )


def test_review_state_forbids_automatic_activation() -> None:
    with pytest.raises(AdminMarketplaceError, match="automatic activation"):
        SalesChannelEligibilityContract(
            country_code="TN",
            maestro_direct_status=ChannelEligibilityStatus.ELIGIBLE,
            lemon_squeezy_status=ChannelEligibilityStatus.REQUIRES_REVIEW,
            customer_choice_allowed=False,
            admin_review_required=True,
            automatic_activation_allowed=True,
        )


def test_selection_must_be_eligible_and_customer_choice_needs_two_channels() -> None:
    with pytest.raises(AdminMarketplaceError, match="selected_channel"):
        CustomerChannelSelectionContract(
            customer_id="customer_001",
            selected_channel=SalesChannel.LEMON_SQUEEZY,
            eligible_channels=frozenset({SalesChannel.MAESTRO_DIRECT}),
        )

    with pytest.raises(AdminMarketplaceError, match="at least two"):
        SalesChannelEligibilityContract(
            country_code="TN",
            maestro_direct_status=ChannelEligibilityStatus.ELIGIBLE,
            lemon_squeezy_status=ChannelEligibilityStatus.REQUIRES_REVIEW,
            customer_choice_allowed=True,
            admin_review_required=True,
        )
