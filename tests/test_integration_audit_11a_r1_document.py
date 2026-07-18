from pathlib import Path

DOC = Path("docs/integrations/INTEGRATION_AUDIT_11A_R1.md")
ADMIN_API_KEYS_JS = Path("processual_api/static/js/admin_api_keys.js")
SETTINGS_JS = Path("processual_api/static/js/pages/settings.js")
CLIENT_HTML = Path("processual_api/static/index.html")
SUBSCRIPTION_CATALOG = Path("processual_api/billing/subscription_catalog.py")
USAGE_PRICING = Path("processual_api/billing/usage_pricing.py")


def _text(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").lower().split())


def test_integration_audit_11a_r1_document_exists():
    assert DOC.exists()


def test_integration_audit_11a_r1_records_existing_primitives():
    text = _text(DOC)

    expected_markers = [
        "integration-audit-11a-r1",
        "status: `draft_audit`",
        "maestro is not empty in the integration area",
        "existing api key access primitives",
        "existing client integration readiness ui",
        "existing integration request workflow",
        "existing enterprise integration plan layer",
        "existing usage logging and quota primitives",
        "existing platform-specific integrations",
    ]

    for marker in expected_markers:
        assert marker in text


def test_integration_audit_11a_r1_distinguishes_access_from_adapters():
    text = _text(DOC)

    expected_markers = [
        "these primitives are not the same as customer-sector production adapters",
        "platform integrations",
        "not customer-sector adapters",
        "telecom crm adapter",
        "banking kyc adapter",
        "government case adapter",
        "university student adapter",
        "research dataset adapter",
        "generic enterprise helpdesk adapter",
    ]

    for marker in expected_markers:
        assert marker in text


def test_integration_audit_11a_r1_aligns_11b_with_existing_workflows():
    text = _text(DOC)

    expected_markers = [
        "guardrails for 11b",
        "reuse `external_partner` and `service_integration` concepts",
        "preserve `/settings/api-key-integration`",
        "preserve existing integration key request types",
        "preserve safe support-message behavior",
        "preserve enterprise plan gating",
        "preserve service integration usage logging",
        "avoid writing a second incompatible key lifecycle",
    ]

    for marker in expected_markers:
        assert marker in text


def test_existing_admin_api_key_integration_primitives_are_present():
    text = ADMIN_API_KEYS_JS.read_text(encoding="utf-8")

    expected_markers = [
        "service_integration",
        "Service Integration - server-to-server access",
        "Integration API key",
        "integration-client",
        "integration-user",
        "API Key for integration",
    ]

    for marker in expected_markers:
        assert marker in text


def test_existing_client_integration_readiness_primitives_are_present():
    settings_text = SETTINGS_JS.read_text(encoding="utf-8")
    html_text = CLIENT_HTML.read_text(encoding="utf-8")

    settings_markers = [
        "/settings/api-key-integration",
        "loadApiKeyIntegration",
        "applyApiKeyIntegration",
        "renderIntegrationKeys",
        "prepareIntegrationKeyRequest",
        "integration_key_provisioning",
        "integration_key_rotation",
        "integration_key_deactivation",
        "clientIntegrationGuideText",
    ]

    html_markers = [
        "Client Integration Guide",
        "&lt;client-integration-key&gt;",
        "Prepare integration support request",
    ]

    for marker in settings_markers:
        assert marker in settings_text

    for marker in html_markers:
        assert marker in html_text


def test_existing_client_request_options_include_integration_workflow():
    text = CLIENT_HTML.read_text(encoding="utf-8")

    expected_markers = [
        "enterprise_integration_upgrade",
        "integration_key_provisioning",
        "integration_key_rotation",
        "integration_key_deactivation",
        "enterprise_integration",
        "enterprise_integration_starter",
        "do not paste raw provider secrets or raw integration keys",
    ]

    for marker in expected_markers:
        assert marker in text


def test_existing_subscription_catalog_contains_enterprise_integration_plans():
    catalog_text = SUBSCRIPTION_CATALOG.read_text(encoding="utf-8")
    usage_pricing_text = USAGE_PRICING.read_text(encoding="utf-8")

    catalog_markers = [
        "enterprise_integration_starter",
        "enterprise_integration",
    ]

    for marker in catalog_markers:
        assert marker in catalog_text

    assert "allows_enterprise_integration" in usage_pricing_text


def test_integration_audit_11a_r1_publication_restrictions_are_present():
    text = _text(DOC)

    restricted_markers = [
        "publication restrictions",
        "production adapter approval",
        "proof that customer-sector connectors exist",
        "customer api compatibility guarantee",
        "credential approval",
        "write-action approval",
        "security approval",
        "acceptance-test approval",
    ]

    for marker in restricted_markers:
        assert marker in text
