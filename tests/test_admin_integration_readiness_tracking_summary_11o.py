from pathlib import Path

ADMIN_HTML = Path("processual_api/static/admin.html")
ADMIN_CLIENT_REQUESTS_JS = Path("processual_api/static/js/admin_client_requests.js")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _phase_block() -> str:
    js = _read(ADMIN_CLIENT_REQUESTS_JS)
    marker = "ADMIN_INTEGRATION_READINESS_TRACKING_SUMMARY_11O_MARKER"
    assert marker in js
    return js[js.index(marker) :]


def test_admin_tracking_summary_loads_from_existing_admin_script():
    html = _read(ADMIN_HTML)
    js = _read(ADMIN_CLIENT_REQUESTS_JS)

    assert "admin_client_requests.js" in html
    assert "admintracking11o" in html
    assert "ADMIN_INTEGRATION_READINESS_TRACKING_SUMMARY_11O_MARKER" in js
    assert "PMK_ADMIN_INTEGRATION_READINESS_TRACKING_SUMMARY" in js


def test_admin_tracking_summary_renders_case_table_and_empty_state():
    block = _phase_block()

    required = [
        "admin-integration-readiness-tracking-summary-card",
        "admin-integration-readiness-tracking-state",
        "admin-integration-readiness-tracking-foundation",
        "admin-integration-readiness-tracking-cases",
        "admin-integration-readiness-tracking-provided",
        "admin-integration-readiness-tracking-verified",
        "admin-integration-readiness-tracking-rejected",
        "admin-integration-readiness-tracking-events",
        "admin-integration-readiness-tracking-cases-table",
        "admin-integration-readiness-tracking-cases-body",
        "No persisted readiness tracking cases yet.",
        "current readiness checks are declarative",
    ]

    for marker in required:
        assert marker in block


def test_admin_tracking_summary_keeps_zero_persisted_cases_without_fake_data():
    block = _phase_block()

    assert "persistedCases: 0" in block
    assert "providedInputs: 0" in block
    assert "verifiedItems: 0" in block
    assert "rejectedItems: 0" in block
    assert "timelineEvents: 0" in block
    assert "does not invent customer submissions" in block


def test_admin_tracking_summary_guardrails_remain_false():
    block = _phase_block()

    assert "productionConnectorApproved: false" in block
    assert "runtimeConnectorApproved: false" in block
    assert "externalHttpEnabled: false" in block
    assert "rawSecretVisible: false" in block
    assert "no raw secrets" in block
    assert "no customer credentials" in block
    assert "no external HTTP calls" in block
    assert "no runtime connector" in block
    assert "no production connector approval" in block


def test_admin_tracking_summary_does_not_add_runtime_or_external_http():
    block = _phase_block()

    forbidden = [
        "fetch(\"http",
        "fetch('http",
        "XMLHttpRequest",
        "requests.get",
        "requests.post",
        "httpx",
        "urllib",
        "productionConnectorApproved: true",
        "runtimeConnectorApproved: true",
        "externalHttpEnabled: true",
        "rawSecretVisible: true",
        "connectorRuntimeExecute",
        "runtimeConnectorExecute",
        "productionApprovalGranted",
    ]

    for marker in forbidden:
        assert marker not in block

def test_admin_tracking_summary_has_visible_admin_host():
    html = _read(ADMIN_HTML)
    js = _read(ADMIN_CLIENT_REQUESTS_JS)

    assert "admin-integration-readiness-tracking-summary-host" in html
    assert "Visible admin integration readiness tracking host" in html
    assert "admintrackingroute11p-visiblehost" in html
    assert "ADMIN_INTEGRATION_READINESS_TRACKING_VISIBLE_HOST_11P_MARKER" in js
    assert "trackingHost()" in js
    assert "host.appendChild(card)" in js
