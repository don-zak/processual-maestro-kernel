from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs" / "reports" / "API_KEY_PROFILES_ADMIN_PROVISIONING.md"


def _report_text() -> str:
    assert REPORT.exists(), "API_KEY_PROFILES_ADMIN_PROVISIONING.md must exist"
    return REPORT.read_text(encoding="utf-8")


def test_api_key_profiles_report_declares_phase_and_boundaries():
    text = _report_text()

    assert "ADMIN-APIKEYS-02A" in text
    assert "governed scoped access provisioning" in text
    assert "It should not modify backend schemas." in text
    assert "It should not modify JavaScript." in text
    assert "It should not implement Lemon Squeezy API calls." in text
    assert "It should not create the lifecycle UI yet." in text
    assert "It should not create `tests/test_admin_api_key_lifecycle_regression.py` yet." in text


def test_api_key_profiles_report_declares_current_route_baseline():
    text = _report_text()

    required_routes = [
        "GET | `/settings/api-keys`",
        "POST | `/settings/api-keys`",
        "PATCH | `/settings/api-keys/{key_id}/plan`",
        "PATCH | `/settings/api-keys/{key_id}/quota`",
        "DELETE | `/settings/api-keys/{key_id}`",
    ]

    for route in required_routes:
        assert route in text


def test_api_key_profiles_report_declares_security_rules():
    text = _report_text()

    required_rules = [
        "No raw API key is stored.",
        "No raw API key is recoverable after creation.",
        "Raw API key material may only be shown once in the create response.",
        "Revoke must use `key_id`, not a raw key.",
        "UI hiding is not security.",
        "Billing state must be able to restrict, downgrade, or suspend key access.",
    ]

    for rule in required_rules:
        assert rule in text


def test_api_key_profiles_report_declares_all_admin_roles():
    text = _report_text()

    roles = [
        "owner_admin",
        "security_admin",
        "ops_admin",
        "billing_admin",
        "support_admin",
        "viewer_admin",
    ]

    for role in roles:
        assert role in text


def test_api_key_profiles_report_declares_required_admin_scopes():
    text = _report_text()

    scopes = [
        "admin:read",
        "admin:settings",
        "admin:api_keys:read",
        "admin:api_keys:write",
        "admin:api_keys:revoke",
        "admin:adapters:read",
        "admin:adapters:write",
        "admin:usage:read",
        "admin:clients:read",
        "admin:clients:write",
        "admin:billing:read",
        "admin:billing:write",
        "admin:health:read",
        "admin:audit:read",
        "admin:dangerous",
    ]

    for scope in scopes:
        assert scope in text


def test_api_key_profiles_report_declares_all_key_categories():
    text = _report_text()

    categories = [
        "client_api",
        "pilot_client",
        "external_partner",
        "service_integration",
        "billing_service",
        "support_viewer",
        "ops_admin",
        "billing_admin",
        "security_admin",
        "owner_admin",
        "emergency_bootstrap",
    ]

    for category in categories:
        assert category in text


def test_api_key_profiles_report_covers_programmatic_access_policy():
    text = _report_text()

    assert "Programmatic Access Without Browser Login" in text
    assert "This is not an authentication bypass." in text

    allowed_categories = [
        "`client_api` | Yes",
        "`pilot_client` | Yes",
        "`external_partner` | Yes",
        "`service_integration` | Yes",
        "`billing_service` | Yes",
        "`emergency_bootstrap` | Yes",
    ]

    for category in allowed_categories:
        assert category in text


def test_api_key_profiles_report_declares_lemonsqueezy_readiness():
    text = _report_text()

    required_env_vars = [
        "LEMONSQUEEZY_API_KEY",
        "LEMONSQUEEZY_STORE_ID",
        "LEMONSQUEEZY_WEBHOOK_SECRET",
        "LEMONSQUEEZY_STARTER_VARIANT_ID",
        "LEMONSQUEEZY_PRO_VARIANT_ID",
        "LEMONSQUEEZY_BUSINESS_VARIANT_ID",
        "LEMONSQUEEZY_SUCCESS_URL",
        "LEMONSQUEEZY_CANCEL_URL",
    ]

    for env_var in required_env_vars:
        assert env_var in text

    assert "No real Lemon Squeezy secret may be committed to Git." in text


def test_api_key_profiles_report_maps_billing_state_to_key_policy():
    text = _report_text()

    billing_states = [
        "`trialing`",
        "`active`",
        "`past_due`",
        "`cancelled`",
        "`expired`",
        "`refunded`",
        "`disputed`",
    ]

    for billing_state in billing_states:
        assert billing_state in text


def test_api_key_profiles_report_declares_future_schema_direction():
    text = _report_text()

    required_fields = [
        "`category`",
        "`role`",
        "`scopes`",
        "`plan_id`",
        "`quota_limit_override`",
        "`expires_at`",
        "`client_id`",
        "`user_id`",
        "`label`",
        "`purpose`",
        "`issued_to`",
        "`created_by_admin_role`",
    ]

    for field in required_fields:
        assert field in text


def test_api_key_profiles_report_declares_future_ui_direction():
    text = _report_text()

    required_controls = [
        "Category selector.",
        "Role selector.",
        "Scope checklist.",
        "Plan/quota profile selector.",
        "Expiry field.",
        "Purpose field.",
        "Issued-to field.",
        "Generate button.",
        "One-time raw key display box.",
        "Copy button.",
        "Raw key warning.",
        "Metadata table.",
        "Refresh button.",
        "Revoke button.",
        "Permission labels for read-only roles.",
    ]

    for control in required_controls:
        assert control in text


def test_api_key_profiles_report_declares_next_phases():
    text = _report_text()

    next_phases = [
        "ADMIN-APIKEYS-02B",
        "ADMIN-APIKEYS-02C",
        "BILLING-LEMON-01",
        "BILLING-LEMON-02",
        "BILLING-LEMON-03",
        "ADMIN-BILLING-01",
    ]

    for phase in next_phases:
        assert phase in text
