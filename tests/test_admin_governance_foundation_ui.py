"""Static contract tests for the administrator governance workspace foundation."""

from pathlib import Path

NAV_JS = Path("processual_api/static/js/admin_nav.js")
GOVERNANCE_JS = Path("processual_api/static/js/admin_governance.js")
GOVERNANCE_CSS = Path("processual_api/static/css/admin_governance.css")


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


def test_governance_foundation_does_not_fabricate_runtime_data() -> None:
    js = _read(GOVERNANCE_JS)

    required = [
        "Governance read API is not connected yet.",
        "No administrator data is fabricated",
        "Foundation mode",
    ]

    for marker in required:
        assert marker in js


def test_privileged_controls_are_inert_until_backend_authority_exists() -> None:
    js = _read(GOVERNANCE_JS)

    assert 'id="ag-invite-admin" type="button" disabled' in js
    assert 'aria-label="Search administrators" disabled' in js

    forbidden = [
        "fetch('/admin/governance",
        'fetch("/admin/governance',
        "XMLHttpRequest",
        "administrator.revoke()",
        "administrator.freeze()",
    ]

    for marker in forbidden:
        assert marker not in js


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
