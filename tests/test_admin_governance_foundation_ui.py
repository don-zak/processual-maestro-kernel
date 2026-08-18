"""Static contract tests for the administrator governance workspace foundation."""

from pathlib import Path

NAV_JS = Path("processual_api/static/js/admin_nav.js")
GOVERNANCE_JS = Path("processual_api/static/js/admin_governance.js")
GOVERNANCE_CSS = Path("processual_api/static/css/admin_governance.css")
AUTH_BRIDGE_JS = Path("processual_api/static/js/admin_auth_bridge.js")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_governance_workspace_is_loaded_from_admin_navigation() -> None:
    nav = _read(NAV_JS)

    required = [
        "bootstrapAdminGovernance",
        "/console/css/admin_governance.css?v=governance-foundation-1",
        "/console/js/admin_governance.js?v=governance-foundation-1",
        "data-admin-governance-style",
        "data-admin-governance-script",
    ]

    for marker in required:
        assert marker in nav


def test_governance_workspace_registers_admin_page_and_navigation() -> None:
    js = _read(GOVERNANCE_JS)

    required = [
        "navApi.pageIds.governance = 'page-admin-governance'",
        "navApi.labelToPage.administrators = 'governance'",
        'data-admin-page="governance"',
        "Administrators &amp; Access",
        "Platform governance",
        "Engineering governance",
    ]

    for marker in required:
        assert marker in js


def test_governance_workspace_uses_real_read_api_without_fabricated_records() -> None:
    js = _read(GOVERNANCE_JS)
    auth_bridge = _read(AUTH_BRIDGE_JS)

    required = [
        "fetch('/governance/administrators', { method: 'GET' })",
        "Array.isArray(payload.administrators)",
        "Read-only governance mode",
        "Loading administrator governance data",
        "No administrators match the current filters.",
    ]

    for marker in required:
        assert marker in js

    assert "target.pathname.startsWith('/governance')" in auth_bridge


def test_privileged_controls_remain_inert_until_mutation_authority_exists() -> None:
    js = _read(GOVERNANCE_JS)

    assert 'id="ag-invite-admin" type="button" disabled' in js

    forbidden = [
        "method: 'POST'",
        'method: "POST"',
        "method: 'PATCH'",
        'method: "PATCH"',
        "method: 'DELETE'",
        'method: "DELETE"',
        "administrator.revoke()",
        "administrator.freeze()",
        "/governance/invitations",
        "/governance/freeze",
        "/governance/revoke",
    ]

    for marker in forbidden:
        assert marker not in js


def test_governance_read_controls_support_search_and_state_filters() -> None:
    js = _read(GOVERNANCE_JS)

    required = [
        'id="ag-search"',
        'data-filter="all"',
        'data-filter="active"',
        'data-filter="pending"',
        'data-filter="frozen"',
        "visibleAdministrators",
        "renderSummary",
        "renderTable",
    ]

    for marker in required:
        assert marker in js


def test_governance_permission_domains_cover_operations_and_engineering() -> None:
    js = _read(GOVERNANCE_JS)

    required = [
        "Administration",
        "Marketplace",
        "Billing",
        "Customers",
        "Audit",
        "Engineering",
        "Releases",
        "Infrastructure",
        "Code Reviewer",
        "Developer",
        "Lead Developer",
    ]

    for marker in required:
        assert marker in js


def test_governance_security_invariants_are_visible() -> None:
    js = _read(GOVERNANCE_JS)

    required = [
        "Invitation allow-list",
        "Self-managed credentials",
        "Recent MFA step-up",
        "Session revocation",
        "No self-escalation",
        "Last-super-admin guard",
    ]

    for marker in required:
        assert marker in js


def test_governance_ui_has_responsive_and_accessible_contracts() -> None:
    js = _read(GOVERNANCE_JS)
    css = _read(GOVERNANCE_CSS)

    js_required = [
        'aria-label="Administrator governance summary"',
        'role="tablist"',
        'role="tab"',
        'aria-selected="true"',
        'aria-describedby="ag-foundation-note"',
    ]
    css_required = [
        "@media (max-width: 980px)",
        "@media (max-width: 640px)",
        ".ag-table-wrap",
        "overflow-x: auto",
        ".ag-primary[disabled]",
    ]

    for marker in js_required:
        assert marker in js
    for marker in css_required:
        assert marker in css
