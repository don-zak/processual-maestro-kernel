from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_admin_api_keys_loads_external_evaluation_runtime_in_dependency_order():
    source = read("processual_api/static/js/admin_actions.js")

    assert "function loadExternalEvaluationAccess()" in source
    assert "loadExternalEvaluationAccess();" in source
    assert "adminExternalEvaluationAssets = 'loaded'" in source

    assets = (
        "/console/js/admin_api_key_provisioning_workspace.js",
        "/console/js/admin_external_evaluation_dom_contract.js",
        "/console/js/admin_evaluation_grants.js",
        "/console/js/admin_api_key_evaluation_lifecycle.js",
    )
    positions = [source.index(asset) for asset in assets]
    assert positions == sorted(positions)

    assert "PMK_ADMIN_EXTERNAL_EVALUATION_DOM_CONTRACT?.reconcile?.()" in source
    assert "PMK_ADMIN_API_KEY_EVALUATION_LIFECYCLE?.initialize?.()" in source
    assert "ProductionAuthorityGranted=true" not in source
    assert "RealStagingQualified=true" not in source


def test_external_evaluation_contract_still_exposes_governed_category_and_card():
    source = read("processual_api/static/js/admin_external_evaluation_dom_contract.js")

    assert "const EXTERNAL_CATEGORY = 'external_evaluation'" in source
    assert "External Evaluation Access - governed sandbox evaluation" in source
    assert "admin-api-key-external-evaluation-card" in source
    assert "Administrator Verification" in source
    assert "Production access remains disabled" in source
    assert "setStandardVisible(!external)" in source


def test_registration_mfa_review_is_layout_only_and_requires_explicit_review_query():
    source = read("processual_api/static/js/pages/register.js")

    assert 'queryValue("review_mfa") !== "1"' in source
    assert 'review.id = "registration-mfa-review"' in source
    assert 'review.dataset.reviewOnly = "true"' in source
    assert "MFA enrollment preview" in source
    assert "Real TOTP enrollment becomes available only after email verification" in source
    assert "register → verify email → sign in → enroll TOTP → confirm TOTP" in source

    # The visual review state must never become an enrollment shortcut.
    assert "/auth/mfa/totp/enroll" not in source
    assert "/auth/mfa/totp/confirm" not in source
    assert "provisioning_uri" not in source
    assert "qr" not in source.lower()
    assert "secret=" not in source.lower()


def test_registration_mfa_review_layout_does_not_overlay_or_fix_card_height():
    source = read("processual_api/static/js/pages/register.js")
    review_start = source.index('style.id = "registration-mfa-review-style"')
    review_end = source.index("document.head.appendChild(style);", review_start)
    css = source[review_start:review_end]

    assert "min-width: 0" in css
    assert "width: 100%" in css
    assert "grid-template-columns: minmax(0, 1fr)" in css
    assert "@media (max-width: 520px)" in css
    assert "position: absolute" not in css
    assert "position: fixed" not in css
    assert "height:" not in css
    assert "max-height:" not in css


def test_full_web_review_opens_registration_mfa_review_and_preserves_real_mfa_boundary():
    source = read("scripts/run_full_web_review.ps1")

    assert 'Name = "Registration MFA layout review"' in source
    assert 'Path = "/register?review_mfa=1"' in source
    assert "Registration MFA review is layout-only" in source
    assert "real MFA enrollment remains after verified sign-in" in source
    assert "sessionStorage" not in source
    assert "maestro_token" not in source
    assert "RealStagingQualified=true" not in source
    assert "ProductionAuthorityGranted=true" not in source
