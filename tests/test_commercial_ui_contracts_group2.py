from processual_api.billing.commercial_ui_contracts import (
    CHECKOUT_ENABLED,
    INVOICING_ENABLED,
    PRICING_APPROVED,
    QUOTA_ENFORCEMENT_ENABLED,
    SETTLEMENT_ENABLED,
    STANDALONE_UI_ALLOWED,
    STATE_MESSAGES,
    CommercialSurface,
    CommercialUiState,
    build_commercial_ui_foundation,
)


def test_commercial_ui_foundation_remains_non_activating() -> None:
    assert PRICING_APPROVED is False
    assert CHECKOUT_ENABLED is False
    assert INVOICING_ENABLED is False
    assert SETTLEMENT_ENABLED is False
    assert QUOTA_ENFORCEMENT_ENABLED is False
    assert STANDALONE_UI_ALLOWED is False


def test_required_ui_states_are_explicit() -> None:
    assert {
        CommercialUiState.LOADING,
        CommercialUiState.EMPTY,
        CommercialUiState.ERROR,
        CommercialUiState.DISABLED,
    }.issubset(STATE_MESSAGES[CommercialSurface.PUBLIC_PRICING])

    assert {
        CommercialUiState.LOADING,
        CommercialUiState.ERROR,
        CommercialUiState.DISABLED,
    }.issubset(STATE_MESSAGES[CommercialSurface.SUBSCRIPTION_CHECKOUT])

    assert {
        CommercialUiState.LOADING,
        CommercialUiState.EMPTY,
        CommercialUiState.ERROR,
        CommercialUiState.DISABLED,
        CommercialUiState.PERMISSION_DENIED,
    }.issubset(STATE_MESSAGES[CommercialSurface.ADMIN_MARKETPLACE])


def test_admin_marketplace_denial_is_explicit() -> None:
    message = STATE_MESSAGES[CommercialSurface.ADMIN_MARKETPLACE][CommercialUiState.PERMISSION_DENIED]
    assert "platform administrator" in message.description
    assert message.retry_allowed is False


def test_foundation_references_selected_pricing_review() -> None:
    payload = build_commercial_ui_foundation()
    assert payload["pricing_proposal_status"] == "draft_review"
    assert payload["requires_existing_frontend_design_system"] is True
    assert payload["standalone_ui_allowed"] is False
    assert payload["pricing_approved"] is False
    assert payload["checkout_enabled"] is False
