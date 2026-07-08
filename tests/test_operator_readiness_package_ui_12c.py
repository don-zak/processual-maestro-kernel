from __future__ import annotations

import re
from pathlib import Path


def _block(text: str, start: str, end: str) -> str:
    pattern = re.compile(re.escape(start) + r"(.*?)" + re.escape(end), re.S)
    match = pattern.search(text)
    assert match is not None
    return match.group(1)


def test_operator_readiness_package_12c_admin_html_markers():
    html = Path("processual_api/static/admin.html").read_text(encoding="utf-8")

    assert "admin-integration-readiness-operator-package-host" in html
    assert 'data-admin-integration-readiness-operator-package-host="12c"' in html
    assert "admin-integration-readiness-operator-package-body" in html
    assert 'data-admin-integration-readiness-operator-package-body="12c"' in html
    assert "Operator Readiness Package" in html
    assert "external HTTP execution is enabled" in html


def test_operator_readiness_package_12c_admin_js_markers_and_guardrails():
    js = Path("processual_api/static/js/admin_client_requests.js").read_text(
        encoding="utf-8"
    )
    package_block = _block(
        js,
        "// BEGIN INTEGRATION_READINESS_12C_OPERATOR_PACKAGE_UI",
        "// END INTEGRATION_READINESS_12C_OPERATOR_PACKAGE_UI",
    )

    assert "PMK_OPERATOR_READINESS_PACKAGE_12C" in package_block
    assert 'marker: "adminpackage12c"' in package_block
    assert "/settings/admin/integration-readiness-operator-package" in package_block
    assert "/settings/admin/integration-readiness-operator-package/export" in package_block
    assert "data-admin-operator-package-case-count" in package_block
    assert "data-admin-operator-package-pilot-ready" in package_block
    assert "data-admin-operator-package-production-allowed" in package_block
    assert "data-admin-operator-package-runtime-approved" in package_block
    assert "data-admin-operator-package-external-http" in package_block
    assert "data-admin-operator-package-raw-secret" in package_block
    assert "http://" not in package_block
    assert "https://" not in package_block
    assert "XMLHttpRequest" not in package_block
    assert "requests.get" not in package_block
    assert "requests.post" not in package_block
