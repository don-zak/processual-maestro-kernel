from pathlib import Path


LOGIN_TOKEN_CAPTURE = Path("processual_api/static/js/login_token_capture.js")
REGISTER_HTML = Path("processual_api/static/register.html")
REGISTER_JS = Path("processual_api/static/js/pages/register.js")
CONSOLE_I18N = Path("processual_api/static/js/i18n.js")
TOUR_ENGINE = Path("processual_api/static/js/tour/tour-engine.js")
OFFER_JS = Path("processual_api/static/js/pages/offer.js")


def test_login_password_visibility_is_anchored_inside_input_shell() -> None:
    source = LOGIN_TOKEN_CAPTURE.read_text(encoding="utf-8")

    assert "login-password-shell" in source
    assert "shell.appendChild(password)" in source
    assert "shell.appendChild(button)" in source
    assert "top:50%" in source
    assert "translateY(-50%)" in source
    assert "bottom:7px" not in source
    assert "password.style.paddingInlineEnd = '76px'" in source


def test_mfa_challenge_replaces_primary_login_controls_without_card_pressure() -> None:
    source = LOGIN_TOKEN_CAPTURE.read_text(encoding="utf-8")

    assert "function setMfaLayout(active)" in source
    assert "card.dataset.mfaActive" in source
    assert "commercialActions.hidden = active" in source
    assert "commercialPanel.hidden = true" in source
    assert "lostAccessPanel.hidden = true" in source
    assert "setMfaLayout(true)" in source
    assert "setMfaLayout(false)" in source
    assert "focus({ preventScroll: true })" in source


def test_general_console_and_login_are_english_only_but_tutorial_keeps_arabic() -> None:
    login = LOGIN_TOKEN_CAPTURE.read_text(encoding="utf-8")
    console_i18n = CONSOLE_I18N.read_text(encoding="utf-8")
    tour = TOUR_ENGINE.read_text(encoding="utf-8")

    assert "function lockLoginToEnglish()" in login
    assert "bar.hidden = true" in login
    assert "document.documentElement.dir = 'ltr'" in login

    assert "function lockConsoleToEnglish()" in console_i18n
    assert "I18N.setLang('en')" in console_i18n
    assert "toggle.hidden = true" in console_i18n

    assert 'data-lang="ar"' in tour
    assert "TOUR_STEPS[_lang] || TOUR_STEPS.en" in tour
    assert "localStorage.setItem('tour_lang', _lang)" in tour


def test_offer_selection_is_visible_and_preserved_in_registration_request() -> None:
    html = REGISTER_HTML.read_text(encoding="utf-8")
    source = REGISTER_JS.read_text(encoding="utf-8")
    offer = OFFER_JS.read_text(encoding="utf-8")

    assert 'id="registration-plan-context"' in html
    assert 'id="registration-plan-name"' in html
    assert 'id="registration-plan-billing"' in html
    assert 'id="registration-plan-price"' in html

    assert "async function loadSelectedOfferContext()" in source
    assert 'fetch("/billing/public-plan-journey"' in source
    assert "payload.selected_plan_id = planId" in source
    assert "payload.billing_period = selectedBillingPeriod()" in source
    assert "loadSelectedOfferContext();" in source

    assert "billing_period=monthly" in offer
    assert "billing_period=annual" in offer


def test_registration_password_and_terms_layout_are_stable() -> None:
    html = REGISTER_HTML.read_text(encoding="utf-8")

    assert 'class="password-shell"' in html
    assert 'id="registration-password-visibility"' in html
    assert ".password-shell { position: relative; width: 100%; }" in html
    assert "top: 50%;" in html
    assert "transform: translateY(-50%);" in html
    assert ".terms input" in html
    assert "width: auto;" in html
    assert "justify-content: flex-start;" in html
