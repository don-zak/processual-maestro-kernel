from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_vq1_workflow_runs_button_action_validator_before_summary_and_upload():
    workflow = read(".github/workflows/vq1-browser-qualification.yml")
    validator = "python qualification/vq1_button_action_validator.py"
    assert "Validate all delivered button actions" in workflow
    assert validator in workflow
    assert "artifacts/vq1/button_action_report.json" in workflow
    assert workflow.index(validator) < workflow.index("Show capture summary")
    assert workflow.index(validator) < workflow.index("Upload VQ-1 evidence")


def test_button_action_validator_covers_console_admin_and_openapi_contracts():
    source = read("qualification/vq1_button_action_validator.py")
    assert "discover_console_sections" in source
    assert "discover_admin_sections" in source
    assert "button:visible" in source
    assert "visible button has no accessible label" in source
    assert "click produced no observable execution effect" in source
    assert "is not registered in OpenAPI" in source
    assert "returned HTTP {status}" in source
    assert '"CONDITIONAL"' in source
    assert "mutation requests are observed and neutralized" in source
    assert "button_action_report.json" in source


def test_button_action_gate_neutralizes_mutations_without_bypassing_auth_token():
    source = read("qualification/vq1_button_action_validator.py")
    assert 'MUTATION_METHODS = {"POST", "PUT", "PATCH", "DELETE"}' in source
    assert 'request_path(request.url) == "/auth/token"' in source
    assert "route.continue_()" in source
    assert 'route.fulfill(status=200, content_type="application/json", body="{}")' in source
