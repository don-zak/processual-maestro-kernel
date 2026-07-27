import processual_api.admin_marketplace as marketplace


def test_public_exports_include_r1_contracts() -> None:
    required = {
        "CommercialOfferContract",
        "CommercialPlanContract",
        "CommercialSubscriptionContract",
        "SalesChannelEligibilityContract",
        "CustomerChannelSelectionContract",
        "CommercialAuditRecord",
        "AdminMarketplaceAction",
        "require_admin_marketplace_authority",
    }
    assert required.issubset(set(marketplace.__all__))
