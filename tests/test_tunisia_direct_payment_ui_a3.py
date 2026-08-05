from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_client_payment_choice_is_fail_closed_and_order_backed() -> None:
    html = (ROOT / "processual_api/static/index.html").read_text(encoding="utf-8")
    javascript = (ROOT / "processual_api/static/js/pages/settings.js").read_text(encoding="utf-8")

    assert 'id="set-tunisia-direct-payment-card"' in html
    assert 'style="display:none"' in html
    assert "/billing/subscription-preparation/payment-options" in javascript
    assert "/billing/subscription-preparation/maestro-direct/orders" in javascript
    assert "option.visible !== true" in javascript
    assert "Idempotency-Key" in javascript
    assert "X-Correlation-ID" in javascript
    assert "/contract/complete" in javascript
    assert "accepted: true" in javascript
    assert "contract_version: tunisianPendingOrder.contract_version" in javascript


def test_client_payment_surface_never_requests_or_renders_raw_destination_identifier() -> None:
    javascript = (ROOT / "processual_api/static/js/pages/settings.js").read_text(encoding="utf-8")
    direct_section = javascript[
        javascript.index("function renderTunisiaPaymentInstructions") :
    ]

    assert "masked_identifier" in direct_section
    assert "raw_account_identifier" not in direct_section
    assert "encrypted_identifier" not in direct_section
