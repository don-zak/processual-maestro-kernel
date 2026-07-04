from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "processual_api" / "static" / "index.html"
SETTINGS_JS = ROOT / "processual_api" / "static" / "js" / "pages" / "settings.js"


def read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_enterprise_integration_eligibility_card_is_hidden_by_default() -> None:
    html = read_file(INDEX_HTML)

    assert 'id="set-enterprise-integration-eligibility-card"' in html
    assert 'style="display:none' in html
    assert "Enterprise Integration Eligibility" in html
    assert "shown only for enterprise plans" in html
    assert "Starter and Business clients should request an upgrade first" in html


def test_enterprise_integration_eligibility_runtime_gates_by_plan() -> None:
    js = read_file(SETTINGS_JS)

    assert "function normalizeClientPlanId(plan)" in js
    assert "function clientSubscriptionPlanId(sub)" in js
    assert "function isEnterpriseClientPlan(sub)" in js
    assert "function updateEnterpriseIntegrationEligibility(sub)" in js
    assert 'planId === "enterprise"' in js
    assert 'planId.indexOf("enterprise_") === 0' in js
    assert 'card.style.display = eligible ? "" : "none"' in js
    assert "updateEnterpriseIntegrationEligibility(sub);" in js


def test_enterprise_integration_eligibility_does_not_enable_admin_or_secret_routes() -> None:
    js = read_file(SETTINGS_JS)

    forbidden = (
        "/admin",
        "admin_",
        "/settings/api-keys",
        "/settings/llm-provider",
        "encrypted_key",
        "api_key",
    )

    for marker in forbidden:
        assert marker not in js

    assert "/settings/subscription" in js
    assert "/settings/api-key-integration" in js
