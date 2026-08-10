from pathlib import Path

OFFER_JS = Path("processual_api/static/js/pages/offer.js")

def test_offer_does_not_coerce_missing_values_to_zero() -> None:
    source = OFFER_JS.read_text(encoding="utf-8")
    assert "value === null || value === undefined" in source
    assert "Capacity defined during assessment" in source
    assert "Pricing defined during assessment" in source

def test_offer_renders_monthly_and_annual_paths() -> None:
    source = OFFER_JS.read_text(encoding="utf-8")
    assert "billing_period=monthly" in source
    assert "billing_period=annual" in source
    assert "Start monthly subscription" in source
    assert "Start annual subscription" in source

def test_offer_renders_top_up_terms() -> None:
    source = OFFER_JS.read_text(encoding="utf-8")
    assert "plan.quota_add_ons" in source
    assert "No recurring commitment" in source
    assert "Annual subscription discount does not apply" in source


def test_offer_explains_contract_scoped_integration_trial_duration() -> None:
    source = OFFER_JS.read_text(encoding="utf-8")

    assert "30_days_or_agreed_quota_exhausted" in source
    assert "one month or until the agreed quota is exhausted" in source



def test_assessment_only_offer_hides_all_annual_language() -> None:
    source = OFFER_JS.read_text(encoding="utf-8")

    assert "annualPrice.hidden = assessmentOnly" in source
    assert "annualSavings.hidden = assessmentOnly" in source
    assert 'annualPrice.textContent = ""' in source
    assert "Annual terms defined during assessment" not in source


def test_commercial_pages_use_approved_compact_scale() -> None:
    source = Path("processual_api/static/css/public-journey.css").read_text(
        encoding="utf-8"
    )

    assert "A3 APPROVED COMPACT COMMERCIAL SCALE START" in source
    assert "font-size: clamp(2rem, 5.6vw, 4rem)" in source
    assert ".quota-value," in source
    assert ".price-line" in source
