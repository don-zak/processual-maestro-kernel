from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "processual_api" / "static" / "js" / "settings_enterprise_endpoints.js"


def test_settings_exposes_request_mapping_and_live_sandbox_proof() -> None:
    js = JS.read_text(encoding="utf-8")
    assert "request-mapping" in js
    assert "Run live sandbox proof" in js
    assert "sandbox-execute" in js
    assert "/settings/enterprise-integration/sandbox-evidence" in js
    assert "Live sandbox proof evidence" in js
    assert "evidence_sha256" in js
    assert "canonical_input_sha256" in js


def test_settings_maps_canonical_fields_to_external_request_body_paths() -> None:
    js = JS.read_text(encoding="utf-8")
    assert "body_mapping" in js
    assert "data-body-field" in js.lower() or "dataset.bodyField" in js
    assert "requestMappingPayload" in js
    assert "pathParameterMapping" in js
    assert "`$task.${name}`" in js


def test_live_sandbox_ui_keeps_production_and_credentials_out_of_form() -> None:
    js = JS.read_text(encoding="utf-8")
    lowered = js.lower()
    assert "Production blocked" in js
    assert "credential reference profile" in lowered
    assert 'name="authorization"' not in lowered
    assert 'name="x-api-key"' not in lowered
    assert "raw_secret" not in lowered
    assert "password" not in lowered
