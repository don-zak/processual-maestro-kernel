from pathlib import Path

CHECKOUT_DISABLED_CONTRACT_DOC = Path(
    "docs/pricing/CHECKOUT_DISABLED_CONTRACT_09D.md"
)


def _checkout_contract_text():
    return " ".join(
        CHECKOUT_DISABLED_CONTRACT_DOC.read_text(
            encoding="utf-8"
        ).lower().split()
    )


def test_checkout_disabled_contract_09d_document_exists():
    assert CHECKOUT_DISABLED_CONTRACT_DOC.exists()


def test_checkout_disabled_contract_09d_guardrails_are_present():
    text = _checkout_contract_text()

    expected_markers = [
        "pricing-checkout-09d",
        "status: `draft_review`",
        "checkout approved: `false`",
        "public pricing approved: `false`",
        "currency approved: `false`",
        "tax treatment approved: `false`",
        "merchant of record approved: `false`",
        "lemon squeezy wiring approved: `false`",
        "checkout remains disabled",
        "real payment sessions remain forbidden",
        "public self-service payment remains forbidden",
        "production payment webhook handling remains forbidden",
    ]

    for marker in expected_markers:
        assert marker in text


def test_checkout_disabled_contract_09d_forbidden_work_is_explicit():
    text = _checkout_contract_text()

    forbidden_work_markers = [
        "forbidden implementation work in 09d",
        "payment provider identifiers",
        "provider-specific product identifiers",
        "provider-specific price identifiers",
        "provider-specific checkout links",
        "provider-specific webhook secrets",
        "real checkout routes",
        "real subscription activation from payment",
        "public self-service purchase buttons",
    ]

    for marker in forbidden_work_markers:
        assert marker in text


def test_checkout_disabled_contract_09d_future_inputs_are_required():
    text = _checkout_contract_text()

    expected_markers = [
        "required future approval inputs",
        "approved public price book",
        "approved price for each public offer",
        "approved currency",
        "approved tax-inclusive or tax-exclusive wording",
        "approved merchant of record model",
        "approved refund policy",
        "approved paid trial policy",
        "approved subscription renewal behavior",
        "approved enterprise review boundary",
        "approved telecom-grade integration exclusion",
    ]

    for marker in expected_markers:
        assert marker in text


def test_checkout_disabled_contract_09d_future_fields_are_neutral():
    text = _checkout_contract_text()

    expected_markers = [
        "future checkout contract fields",
        "offer_code",
        "billing_period",
        "approved_price",
        "approved_currency",
        "tax_mode",
        "refund_policy_code",
        "trial_policy_code",
        "renewal_behavior",
        "cancellation_behavior",
        "enterprise_review_required",
        "integration_scope_required",
        "checkout_enabled",
        "intentionally neutral",
        "do not bind the project to a payment provider",
    ]

    for marker in expected_markers:
        assert marker in text


def test_checkout_disabled_contract_09d_safe_disabled_behavior_is_defined():
    text = _checkout_contract_text()

    expected_markers = [
        "checkout-disabled behavior expectations",
        "offers may be marked as pending review",
        "checkout calls must not be available",
        "purchase buttons must not create payment sessions",
        "paid trial wording must not imply automatic activation",
        "enterprise must remain contact, review, and scoping based",
        "telecom-grade integration must remain separately scoped",
        "safe future route expectations",
        "the disabled route should not create payment sessions or activate subscriptions",
    ]

    for marker in expected_markers:
        assert marker in text


def test_checkout_disabled_contract_09d_approval_gate_is_present():
    text = _checkout_contract_text()

    expected_markers = [
        "approval gate for pricing-approval-10a",
        "final public offers",
        "final prices",
        "final currency",
        "final tax treatment",
        "final merchant of record model",
        "final refund policy",
        "final paid trial behavior",
        "final payment provider decision",
        "without these decisions, checkout must remain disabled",
    ]

    for marker in expected_markers:
        assert marker in text


def test_checkout_disabled_contract_09d_publication_restrictions_are_present():
    text = _checkout_contract_text()

    restricted_markers = [
        "publication restrictions",
        "this document must not be used as",
        "public pricing approval",
        "checkout approval",
        "payment provider approval",
        "lemon squeezy configuration",
        "tax approval",
        "merchant of record approval",
        "public refund approval",
        "public terms approval",
        "subscription activation approval",
        "paid trial conversion approval",
    ]

    for marker in restricted_markers:
        assert marker in text


def test_checkout_disabled_contract_09d_has_no_provider_specific_identifiers():
    raw_text = CHECKOUT_DISABLED_CONTRACT_DOC.read_text(encoding="utf-8").lower()

    forbidden_tokens = [
        "amount_cents",
        "variant_id",
        "lemon_variant",
        "checkout_session_id",
        "payment_intent",
        "live_mode",
        "webhook_secret",
    ]

    for token in forbidden_tokens:
        assert token not in raw_text
