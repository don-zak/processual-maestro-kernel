from pathlib import Path

STATIC = Path("processual_api/static")
ADMIN_HTML = STATIC / "admin.html"
ADMIN_MARKETPLACE_JS = STATIC / "js" / "admin_marketplace.js"
ADMIN_MARKETPLACE_CSS = STATIC / "css" / "admin_marketplace.css"
ADMIN_NAV_JS = STATIC / "js" / "admin_nav.js"
ADMIN_AUTH_BRIDGE_JS = STATIC / "js" / "admin_auth_bridge.js"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_admin_marketplace_is_registered_inside_existing_admin_shell() -> None:
    html = _read(ADMIN_HTML)
    nav = _read(ADMIN_NAV_JS)

    assert 'id="admin-marketplace-nav"' in html
    assert 'data-admin-page="admin-marketplace"' in html
    assert 'id="page-admin-marketplace"' in html
    assert "'admin-marketplace': 'page-admin-marketplace'" in nav
    assert "/console/css/admin_marketplace.css?v=a3-phase7b-1" in html
    assert "/console/js/admin_marketplace.js?v=a3-phase7b-1" in html


def test_admin_marketplace_shell_contains_every_approved_section() -> None:
    html = _read(ADMIN_HTML)

    for section in (
        "overview",
        "catalog",
        "payment-destinations",
        "orders",
        "contracts",
        "payments",
        "reconciliation",
        "subscriptions",
        "audit",
    ):
        assert f'data-am-panel="{section}"' in html

    assert "No synthetic records are shown" in html
    assert "Payment audit API pending" in html


def test_payment_destination_form_uses_atomic_create_validate_contract() -> None:
    html = _read(ADMIN_HTML)
    script = _read(ADMIN_MARKETPLACE_JS)

    for field in (
        "destination_ref",
        "display_name",
        "destination_type",
        "institution_name",
        "account_holder_name",
        "raw_account_identifier",
        "instructions",
    ):
        assert f'name="{field}"' in html

    assert "Create &amp; Validate" in html
    assert "TN" in html
    assert "TND" in html
    assert "maestro_direct" in html
    assert "API_ROOT + '/create-and-validate'" in script
    assert "'Idempotency-Key': pendingCreateKey" in script
    assert "'X-Correlation-ID': uniqueKey('admin-market-ui')" in script


def test_payment_destination_ui_handles_recent_mfa_and_safe_retry() -> None:
    html = _read(ADMIN_HTML)
    script = _read(ADMIN_MARKETPLACE_JS)

    assert 'id="am-mfa-dialog"' in html
    assert "error.status === 428" in script
    assert "await request('/auth/mfa/verify'" in script
    assert "pendingMfaOperation = operation" in script
    assert "codeInput.value = ''" in script


def test_destination_renderer_only_uses_safe_response_fields() -> None:
    script = _read(ADMIN_MARKETPLACE_JS)
    renderer = script.split("function renderDestinations()", 1)[1].split(
        "async function loadDestinations", 1
    )[0]

    assert "masked_identifier" in renderer
    assert "raw_account_identifier" not in renderer
    assert "identifier_ciphertext" not in renderer
    assert "identifier_key_version" not in renderer
    assert "innerHTML" in renderer
    assert "escapeHtml" in renderer


def test_identifier_is_cleared_on_success_navigation_and_page_exit() -> None:
    script = _read(ADMIN_MARKETPLACE_JS)

    assert "function clearIdentifier()" in script
    assert "if (name !== 'payment-destinations') clearIdentifier()" in script
    assert "window.addEventListener('pagehide', clearIdentifier)" in script
    assert "form.reset()" in script


def test_admin_auth_bridge_covers_admin_marketplace_requests() -> None:
    bridge = _read(ADMIN_AUTH_BRIDGE_JS)

    assert "target.pathname.startsWith('/admin-marketplace')" in bridge
    assert "X-Supervisor-Session-Key" in bridge


def test_admin_marketplace_layout_has_responsive_rules() -> None:
    css = _read(ADMIN_MARKETPLACE_CSS)

    assert ".am-payment-layout" in css
    assert "@media (max-width: 1000px)" in css
    assert "@media (max-width: 700px)" in css
    assert ".am-dialog::backdrop" in css
