from pathlib import Path

ADMIN_HTML = Path("processual_api/static/admin.html")
ADMIN_CLIENT_REQUESTS_JS = Path("processual_api/static/js/admin_client_requests.js")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _phase_block() -> str:
    js = _read(ADMIN_CLIENT_REQUESTS_JS)
    marker = "ADMIN_CLIENT_REQUEST_INTEGRATION_READINESS_WORKFLOW_11M_MARKER"
    assert marker in js
    return js[js.index(marker) :]


def test_supervisor_readiness_workflow_loads_from_existing_admin_script():
    html = _read(ADMIN_HTML)
    js = _read(ADMIN_CLIENT_REQUESTS_JS)

    assert "admin_client_requests.js" in html
    assert "adminreadinessworkflow11m" in html
    assert "ADMIN_CLIENT_REQUEST_INTEGRATION_READINESS_WORKFLOW_11M_MARKER" in js
    assert "PMK_ADMIN_CLIENT_REQUEST_INTEGRATION_READINESS_WORKFLOW" in js


def test_supervisor_readiness_workflow_renders_required_dom_markers():
    block = _phase_block()

    required_markers = [
        "admin-client-request-integration-readiness-workflow-card",
        "admin-client-request-integration-readiness-status",
        "admin-client-request-integration-readiness-profile",
        "admin-client-request-integration-readiness-sandbox",
        "admin-client-request-integration-readiness-production",
        "admin-client-request-integration-readiness-runtime",
        "admin-client-request-integration-readiness-blockers",
        "admin-client-request-integration-readiness-actions",
        "admin-client-request-integration-readiness-safety",
        "admin-client-request-integration-readiness-draft-button",
        "admin-client-request-integration-readiness-draft",
    ]

    for marker in required_markers:
        assert marker in block


def test_supervisor_readiness_workflow_listens_to_integration_key_bridge():
    block = _phase_block()

    assert "pmk-admin-integration-key-bridge" in block
    assert "renderSupervisorIntegrationReadinessWorkflow" in block
    assert "generateSafeSupervisorDraft" in block
    assert "lastBridgeDetail" in block


def test_supervisor_readiness_workflow_keeps_guardrails_false():
    block = _phase_block()

    assert "productionConnectorApproved = false" in block
    assert "runtimeConnectorApproved = false" in block
    assert "externalHttpEnabled = false" in block
    assert "rawSecretVisible = false" in block
    assert "Production connector approval remains separate." in block
    assert "Runtime connectors are not approved from this request." in block
    assert "No raw integration secret should be sent in this request." in block


def test_supervisor_readiness_workflow_does_not_enable_runtime_or_http():
    block = _phase_block()

    forbidden_markers = [
        "fetch(",
        "XMLHttpRequest",
        "requests.get",
        "requests.post",
        "httpx",
        "urllib",
        "productionConnectorApproved = true",
        "runtimeConnectorApproved = true",
        "externalHttpEnabled = true",
        "rawSecretVisible = true",
        "connectorRuntimeExecute",
        "runtimeConnectorExecute",
        "productionApprovalGranted",
    ]

    for marker in forbidden_markers:
        assert marker not in block
