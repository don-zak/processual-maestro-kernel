import pytest

from processual_api.billing.commercial_settings_top_up_ui_contracts import (
    REQUIRES_EXISTING_SETTINGS_DESIGN_SYSTEM,
    SETTINGS_TOP_UP_CHECKOUT_ENABLED,
    SETTINGS_TOP_UP_PURCHASE_ENABLED,
    SETTINGS_TOP_UP_VISIBLE,
    STANDALONE_TOP_UP_PAGE_ALLOWED,
    SettingsTopUpState,
    SettingsTopUpSurface,
    build_settings_top_up_preview,
    build_settings_top_up_view_model,
)


def test_top_up_is_bound_to_settings_billing_usage() -> None:
    view = build_settings_top_up_view_model("starter")
    assert view.surface is SettingsTopUpSurface.SETTINGS_BILLING_USAGE
    assert view.controlled_stepper_required is True
    assert view.free_form_quantity_allowed is False
    assert view.active_subscription_required is True


def test_required_interface_content_is_present() -> None:
    content = build_settings_top_up_view_model("business").content
    assert content["heading"] == "Additional Maestro units"
    assert content["bundle_label"]
    assert content["quantity_label"]
    assert content["total_units_label"]
    assert content["bundle_price_label"]
    assert content["total_price_label"]
    assert content["rollover_label"]
    assert content["upgrade_comparison_label"]
    assert content["confirmation_label"]


def test_required_ui_states_are_explicit() -> None:
    states = set(build_settings_top_up_view_model("starter").states)
    assert {state.value for state in SettingsTopUpState}.issubset(states)


def test_preview_combines_settings_view_and_quote() -> None:
    preview = build_settings_top_up_preview("starter", 20_000)
    assert preview["surface"] == "settings_billing_usage"
    assert preview["view"]["plan_code"] == "starter"
    assert preview["quote"]["requested_units"] == 20_000
    assert preview["quote"]["total_units"] == 20_000


def test_unknown_plan_is_rejected() -> None:
    with pytest.raises(ValueError):
        build_settings_top_up_view_model("unknown")


def test_settings_top_up_remains_non_activating() -> None:
    assert SETTINGS_TOP_UP_VISIBLE is False
    assert SETTINGS_TOP_UP_PURCHASE_ENABLED is False
    assert SETTINGS_TOP_UP_CHECKOUT_ENABLED is False
    assert STANDALONE_TOP_UP_PAGE_ALLOWED is False
    assert REQUIRES_EXISTING_SETTINGS_DESIGN_SYSTEM is True
