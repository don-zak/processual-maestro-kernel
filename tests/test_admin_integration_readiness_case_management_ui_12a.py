
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADMIN_HTML = ROOT / "processual_api" / "static" / "admin.html"
ADMIN_JS = ROOT / "processual_api" / "static" / "js" / "admin_client_requests.js"


def _between(text: str, start: str, end: str) -> str:
    assert start in text
    assert end in text
    return text.split(start, 1)[1].split(end, 1)[0]


def test_admin_integration_readiness_case_management_12a_html_host_exists():
    html = ADMIN_HTML.read_text(encoding="utf-8")

    assert "admin-integration-readiness-case-management-host" in html
    assert 'data-admin-integration-readiness-case-management="12a"' in html
    assert "Integration readiness case management" in html
    assert "data-admin-integration-readiness-case-table" in html
    assert "data-admin-integration-readiness-case-detail" in html


def test_admin_integration_readiness_case_management_12a_js_markers_and_actions():
    js = ADMIN_JS.read_text(encoding="utf-8")
    block = _between(
        js,
        "// BEGIN INTEGRATION_READINESS_12A_CASE_MANAGEMENT_UI",
        "// END INTEGRATION_READINESS_12A_CASE_MANAGEMENT_UI",
    )

    assert "admincase12a" in block
    assert "PMK_INTEGRATION_READINESS_CASE_MANAGEMENT_12A" in block
    assert "data-admin-integration-readiness-case-table" in block
    assert "data-admin-integration-readiness-case-detail" in block
    assert "data-admin-integration-readiness-item-action-provided" in block
    assert "data-admin-integration-readiness-item-action-verified" in block
    assert "data-admin-integration-readiness-item-action-rejected" in block
    assert "data-admin-integration-readiness-case-timeline" in block
    assert "data-admin-integration-readiness-safe-reference-input" in block


def test_admin_integration_readiness_case_management_12a_js_has_no_external_http():
    js = ADMIN_JS.read_text(encoding="utf-8")
    block = _between(
        js,
        "// BEGIN INTEGRATION_READINESS_12A_CASE_MANAGEMENT_UI",
        "// END INTEGRATION_READINESS_12A_CASE_MANAGEMENT_UI",
    )

    forbidden = [
        'fetch("http',
        "fetch('http",
        "XMLHttpRequest",
        "http://",
        "https://",
        "requests.get",
        "requests.post",
    ]
    for marker in forbidden:
        assert marker not in block
