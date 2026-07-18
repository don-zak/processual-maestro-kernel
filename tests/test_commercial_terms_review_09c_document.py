from pathlib import Path

COMMERCIAL_TERMS_DOC = Path("docs/pricing/COMMERCIAL_TERMS_REVIEW_09C.md")


def _commercial_terms_text():
    return " ".join(
        COMMERCIAL_TERMS_DOC.read_text(encoding="utf-8").lower().split()
    )


def test_commercial_terms_review_09c_document_exists():
    assert COMMERCIAL_TERMS_DOC.exists()


def test_commercial_terms_review_09c_guardrails_are_present():
    text = _commercial_terms_text()

    expected_markers = [
        "pricing-terms-09c",
        "status: `draft_review`",
        "public terms approved: `false`",
        "public pricing approved: `false`",
        "checkout approved: `false`",
        "lemon squeezy wiring approved: `false`",
        "currency approved: `false`",
        "pricing remains unapproved",
        "currency remains unapproved",
        "checkout remains disabled",
        "lemon squeezy variant ids remain forbidden",
        "byok remains required",
        "ai provider costs remain excluded",
    ]

    for marker in expected_markers:
        assert marker in text


def test_commercial_terms_review_09c_subscription_scope_is_bounded():
    text = _commercial_terms_text()

    expected_markers = [
        "what the subscription may include",
        "monthly usage allowance",
        "limited product support according to plan level",
        "client-side byok provider configuration support",
        "do not automatically include custom implementation",
        "production api integration",
        "telecom-grade connectors",
        "custom sla",
        "dedicated operational supervision",
    ]

    for marker in expected_markers:
        assert marker in text


def test_commercial_terms_review_09c_byok_and_provider_costs_are_explicit():
    text = _commercial_terms_text()

    expected_markers = [
        "byok and provider-cost wording",
        "ai provider costs are external to maestro pricing",
        "customer is responsible for provider accounts",
        "usage charges",
        "rate limits",
        "provider availability",
        "provider policy compliance",
        "does not mean maestro absorbs ai provider costs",
    ]

    for marker in expected_markers:
        assert marker in text


def test_commercial_terms_review_09c_paid_trial_refund_tax_checklists():
    text = _commercial_terms_text()

    expected_markers = [
        "paid trial review checklist",
        "whether the trial renews automatically",
        "whether conversion to subscription is manual or automatic",
        "paid trial must not be treated as enterprise approval",
        "refund terms review checklist",
        "provider-cost exclusion",
        "tax and payment processor limitations",
        "tax and merchant of record checklist",
        "tax-inclusive or tax-exclusive",
        "merchant of record model",
    ]

    for marker in expected_markers:
        assert marker in text


def test_commercial_terms_review_09c_enterprise_and_telecom_are_separate():
    text = _commercial_terms_text()

    expected_markers = [
        "enterprise review policy",
        "production api access",
        "commercial review",
        "technical review",
        "supervisor or operations involvement",
        "telecom-grade integration policy",
        "oss/bss",
        "api gateway integration",
        "production cutover",
        "acceptance testing",
        "not included in standard subscription pricing",
        "sandbox access",
        "credentials policy",
        "acceptance criteria",
    ]

    for marker in expected_markers:
        assert marker in text


def test_commercial_terms_review_09c_publication_restrictions_are_present():
    text = _commercial_terms_text()

    restricted_markers = [
        "this document must not be used as",
        "public legal terms",
        "public pricing approval",
        "checkout approval",
        "lemon squeezy configuration",
        "tax approval",
        "merchant of record approval",
        "refund policy approval",
        "enterprise sla approval",
        "telecom integration approval",
    ]

    for marker in restricted_markers:
        assert marker in text
