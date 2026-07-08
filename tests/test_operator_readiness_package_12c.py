from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient


def _seed_operator_case(path: Path) -> None:
    payload = {
        "cases": [
            {
                "case_id": "operator_client_12c:operator_request_12c:crm:intake:visible",
                "client_id": "operator_client_12c",
                "request_id": "operator_request_12c",
                "adapter_id": "crm",
                "status": "readiness_tracking",
                "input_statuses": [
                    {
                        "item_key": "operator_api_documentation_reference",
                        "label": "Operator API documentation reference",
                        "status": "provided",
                        "safe_reference": "operator-doc-ref-12c",
                    }
                ],
                "security_control_statuses": [
                    {
                        "item_key": "sandbox_only",
                        "label": "Sandbox only",
                        "status": "verified",
                    }
                ],
                "timeline": [
                    {
                        "event": "item_provided",
                        "item_key": "operator_api_documentation_reference",
                        "status": "provided",
                    }
                ],
            }
        ]
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_operator_readiness_package_12c_service_payload_is_safe(
    tmp_path,
    monkeypatch,
):
    store_path = tmp_path / "integration_readiness_cases.json"
    _seed_operator_case(store_path)
    monkeypatch.setenv("PMK_INTEGRATION_READINESS_CASES_PATH", str(store_path))

    from processual_api.services.operator_readiness_package import (
        build_operator_readiness_package_12c,
    )

    payload = build_operator_readiness_package_12c()

    assert payload["package_version"] == "operator-readiness-package-12c"
    assert payload["package_status"] == "draft_review"
    assert payload["handoff_status"] == "pilot_handoff_pending_operator_inputs"
    assert payload["case_count"] == 1
    assert payload["pilot_handoff_ready"] is False
    assert payload["sandbox_ready"] is False
    assert payload["production_ready"] is False
    assert payload["requires_operator_inputs"] is True
    assert payload["requires_supervisor_review"] is True
    assert payload["production_allowed"] is False
    assert payload["runtime_connector_approved"] is False
    assert payload["external_http_enabled"] is False
    assert payload["raw_secret_visible"] is False
    assert payload["external_connector_execution"] is False
    assert payload["customer_credentials_required_in_package"] is False
    assert payload["customer_endpoint_required_in_package"] is False
    assert len(payload["operator_required_inputs"]) >= 8
    assert len(payload["pilot_handoff_steps"]) >= 5
    assert len(payload["production_blockers"]) >= 4


def test_operator_readiness_package_12c_routes_return_json_and_markdown(
    tmp_path,
    monkeypatch,
):
    store_path = tmp_path / "integration_readiness_cases.json"
    _seed_operator_case(store_path)
    monkeypatch.setenv("PMK_INTEGRATION_READINESS_CASES_PATH", str(store_path))

    from processual_api.main import app

    client = TestClient(app)

    json_response = client.get("/settings/admin/integration-readiness-operator-package")
    assert json_response.status_code == 200
    payload = json_response.json()
    assert payload["package_version"] == "operator-readiness-package-12c"
    assert payload["case_count"] == 1
    assert payload["production_allowed"] is False
    assert payload["runtime_connector_approved"] is False
    assert payload["external_http_enabled"] is False
    assert payload["raw_secret_visible"] is False

    export_response = client.get(
        "/settings/admin/integration-readiness-operator-package/export"
    )
    assert export_response.status_code == 200
    text = export_response.text
    assert "Operator Readiness Package" in text
    assert "production_allowed" in text
    assert "runtime_connector_approved" in text
    assert "external_http_enabled" in text
    assert "raw_secret_visible" in text
    assert "http://" not in text
    assert "https://" not in text


def test_operator_readiness_package_12c_doc_is_review_only():
    doc = Path("docs/integrations/OPERATOR_READINESS_PACKAGE_12C.md")
    text = doc.read_text(encoding="utf-8")

    assert "draft_review" in text
    assert "does not enable production connectors" in text
    assert "production_allowed: false" in text
    assert "runtime_connector_approved: false" in text
    assert "external_http_enabled: false" in text
    assert "raw_secret_visible: false" in text
    assert "http://" not in text
    assert "https://" not in text
