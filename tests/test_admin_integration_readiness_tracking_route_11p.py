from pathlib import Path

from fastapi.testclient import TestClient

from processual_api.main import app
from processual_api.services.integration_readiness_tracking_store import (
    admin_tracking_summary_payload,
    create_tracking_case_from_payload,
    update_tracking_case_item_from_payload,
)

MAIN_MODULE = Path("processual_api/main.py")
ADMIN_JS = Path("processual_api/static/js/admin_client_requests.js")
STORE_MODULE = Path("processual_api/services/integration_readiness_tracking_store.py")


def _sample_payload() -> dict[str, object]:
    return {
        "client_id": "client_route_11p",
        "request_id": "request_route_11p",
        "adapter_contract_id": "crm",
        "credential_profile_id": "enterprise_core_api_reference",
        "readiness_check_id": "crm:enterprise_core_api_reference:readiness",
        "operational_profile_id": "service_integration_read_only",
        "missing_inputs": ["api_documentation", "sandbox_access"],
        "missing_security_controls": ["enterprise_review"],
        "assigned_supervisor": "review_supervisor",
    }


def test_admin_tracking_store_creates_and_summarizes_cases(tmp_path):
    store_path = tmp_path / "integration_readiness_cases.json"

    created = create_tracking_case_from_payload(_sample_payload(), store_path)
    summary = admin_tracking_summary_payload(store_path)

    assert created["client_id"] == "client_route_11p"
    assert summary["tracking_foundation"] == "available"
    assert summary["persisted_cases"] == 1
    assert summary["provided_inputs"] == 0
    assert summary["verified_items"] == 0
    assert summary["production_allowed"] is False
    assert summary["runtime_connector_approved"] is False
    assert summary["external_http_enabled"] is False
    assert summary["raw_secret_visible"] is False


def test_admin_tracking_store_updates_items_without_approving_runtime(tmp_path):
    store_path = tmp_path / "integration_readiness_cases.json"
    created = create_tracking_case_from_payload(_sample_payload(), store_path)

    update_tracking_case_item_from_payload(
        str(created["case_id"]),
        {
            "item_kind": "input",
            "item_key": "api_documentation",
            "status": "provided",
            "actor": "review_supervisor",
            "safe_reference": {
                "reference_type": "document_ref",
                "reference_label": "Customer portal document reference DOC-11P",
            },
            "note": "Reference received through approved customer portal.",
        },
        store_path,
    )

    summary = admin_tracking_summary_payload(store_path)

    assert summary["persisted_cases"] == 1
    assert summary["provided_inputs"] == 1
    assert summary["verified_items"] == 0
    assert summary["timeline_events"] == 2
    assert summary["production_allowed"] is False
    assert summary["runtime_connector_approved"] is False


def test_admin_tracking_routes_are_registered_in_openapi():
    client = TestClient(app)
    openapi = client.get("/openapi.json").json()
    paths = openapi["paths"]

    assert "/settings/admin/integration-readiness-tracking" in paths
    assert "/settings/admin/integration-readiness-tracking/cases" in paths
    assert (
        "/settings/admin/integration-readiness-tracking/cases/{case_id}/items"
        in paths
    )


def test_admin_tracking_route_payload_is_safe():
    client = TestClient(app)
    response = client.get("/settings/admin/integration-readiness-tracking")

    assert response.status_code == 200
    payload = response.json()
    assert payload["tracking_foundation"] == "available"
    assert payload["production_allowed"] is False
    assert payload["runtime_connector_approved"] is False
    assert payload["external_http_enabled"] is False
    assert payload["raw_secret_visible"] is False


def test_admin_tracking_summary_js_loads_same_origin_route():
    js = ADMIN_JS.read_text(encoding="utf-8")

    assert "ADMIN_INTEGRATION_READINESS_TRACKING_ROUTE_11P_MARKER" in js
    assert "loadIntegrationReadinessTrackingSummary" in js
    assert "/settings/admin/integration-readiness-tracking" in js
    assert 'credentials: "same-origin"' in js
    assert "admintracking11o-admintrackingroute11p" in js


def test_admin_tracking_route_does_not_add_external_http_or_runtime():
    main_text = MAIN_MODULE.read_text(encoding="utf-8")
    admin_js_text = ADMIN_JS.read_text(encoding="utf-8")
    store_text = STORE_MODULE.read_text(encoding="utf-8")

    route_marker = "INTEGRATION_READINESS_TRACKING_11P_MAIN_ROUTE_MARKER"
    js_marker = "ADMIN_INTEGRATION_READINESS_TRACKING_ROUTE_11P_MARKER"

    assert route_marker in main_text
    assert js_marker in admin_js_text

    route_block = main_text[main_text.index(route_marker) :]
    js_block = admin_js_text[admin_js_text.index(js_marker) :]
    combined = "\n".join([route_block, js_block, store_text])

    forbidden = [
        "requests.get",
        "requests.post",
        "fetch(\"http",
        "fetch('http",
        "XMLHttpRequest",
        "http://",
        "https://",
        "production_allowed=True",
        "runtime_connector_approved=True",
        "external_http_enabled=True",
        "raw_secret_visible=True",
        "productionConnectorApproved: true",
        "runtimeConnectorApproved: true",
        "externalHttpEnabled: true",
        "rawSecretVisible: true",
    ]

    for marker in forbidden:
        assert marker not in combined

def test_admin_tracking_routes_are_present_in_app_routes():
    registered = {
        getattr(route, "path", "")
        for route in app.routes
        if "integration-readiness-tracking" in getattr(route, "path", "")
    }

    assert "/settings/admin/integration-readiness-tracking" in registered
    assert "/settings/admin/integration-readiness-tracking/cases" in registered
    assert (
        "/settings/admin/integration-readiness-tracking/cases/{case_id:path}/items"
        in registered
    )

def test_admin_tracking_route_marker_uses_visible_host_cache():
    js = ADMIN_JS.read_text(encoding="utf-8")

    assert "admintracking11o-admintrackingroute11p-visiblehost" in js
    assert "admin-integration-readiness-tracking-summary-host" in js
    assert "ADMIN_INTEGRATION_READINESS_TRACKING_VISIBLE_HOST_11P_MARKER" in js
