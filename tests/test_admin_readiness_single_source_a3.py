from pathlib import Path

HOME_LAYOUT = Path("processual_api/static/js/admin_home_layout.js")
INTEGRATION_CENTER = Path("processual_api/static/js/admin_integration_center_18.js")
LEGACY_READINESS = Path("processual_api/static/js/admin_integration_readiness.js")
ADMIN_HTML = Path("processual_api/static/admin.html")


def test_integration_center_is_the_owner_of_readiness_workspace() -> None:
    source = INTEGRATION_CENTER.read_text(encoding="utf-8")

    assert 'page-admin-integration-center' not in source
    assert 'tracking: "/settings/admin/integration-readiness-tracking"' in source
    assert 'cases: "/settings/admin/integration-readiness-tracking/cases"' in source
    assert 'handoff: "/settings/admin/operator-pilot-handoff"' in source
    assert 'progress: "/settings/admin/operator-pilot-handoff/progress"' in source
    assert "External Integration Center" in source
    assert "Review cases" in source


def test_home_layout_removes_legacy_readiness_surfaces() -> None:
    source = HOME_LAYOUT.read_text(encoding="utf-8")

    assert "removeLegacyReadinessSurfaces" in source
    assert "admin-integration-readiness-card" in source
    assert "admin-integration-readiness-case-management-host" in source
    assert "page-admin-integration-center" in source
    assert "MutationObserver" in source
    assert "PMK_ADMIN_SURFACE_OWNERSHIP_OBSERVER" in source
    assert "removeLegacyUsagePlaceholder" in source


def test_legacy_readiness_script_is_not_loaded_directly() -> None:
    html = ADMIN_HTML.read_text(encoding="utf-8")
    legacy_source = LEGACY_READINESS.read_text(encoding="utf-8")

    assert "admin_integration_readiness.js" not in html
    assert 'const ENDPOINT = "/settings/admin/integration-readiness"' in legacy_source


def test_readiness_mutations_are_not_owned_by_home_layout() -> None:
    source = HOME_LAYOUT.read_text(encoding="utf-8")

    forbidden = (
        "case-item-action",
        "method: 'POST'",
        'method: "POST"',
        "method: 'PUT'",
        'method: "PUT"',
        "method: 'PATCH'",
        'method: "PATCH"',
        "method: 'DELETE'",
        'method: "DELETE"',
    )
    for marker in forbidden:
        assert marker not in source
