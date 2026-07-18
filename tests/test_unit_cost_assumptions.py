from processual_api.billing.unit_cost_assumptions import get_unit_cost_assumptions


def test_unit_cost_assumptions_are_not_approved_for_pricing_or_checkout():
    payload = get_unit_cost_assumptions()

    assert payload["review_status"] == "pending_review"
    assert payload["approved_for_pricing"] is False
    assert payload["approved_for_checkout"] is False
    assert payload["currency"] is None
    assert payload["provider_cost_included"] is False
    assert payload["billing_policy"] == "byok"


def test_unit_cost_assumptions_include_infra_lemon_and_tunisia_tax_review():
    payload = get_unit_cost_assumptions()
    components = payload["cost_components"]

    assert "infrastructure" in components
    assert components["payment_processing"]["processor"] == "lemon_squeezy"
    assert components["payment_processing"]["merchant_of_record"] is True
    assert components["external_taxes"]["sales_tax_or_vat_handled_by_merchant_of_record"] is True
    assert components["tunisia_local_taxes"]["accountant_review_required"] is True


def test_unit_cost_assumptions_returns_deep_copy():
    first = get_unit_cost_assumptions()
    first["cost_components"]["payment_processing"]["processor"] = "changed"

    second = get_unit_cost_assumptions()

    assert second["cost_components"]["payment_processing"]["processor"] == "lemon_squeezy"
