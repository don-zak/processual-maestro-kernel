from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_enterprise_endpoint_task_bindings.ps1"


def test_comprehensive_verification_bundle_exists_and_is_fail_closed() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "Set-StrictMode -Version Latest" in text
    assert '$ErrorActionPreference = "Stop"' in text
    assert "--junitxml=" in text
    assert "Tee-Object -FilePath" in text
    assert "verify_full_program_local.ps1" in text
    assert "overall_status" in text
    assert "ENTERPRISE ENDPOINT TASK BINDINGS VERIFICATION PASSED" in text


def test_verification_bundle_references_all_required_contract_layers() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    required = {
        "test_integration_task_catalog_contracts.py",
        "test_integration_task_injection.py",
        "test_enterprise_endpoint_bindings.py",
        "test_enterprise_endpoint_request_mapping.py",
        "test_settings_enterprise_request_mapping_runtime.py",
        "test_settings_enterprise_endpoint_bindings_runtime.py",
        "test_enterprise_endpoint_sandbox_grants.py",
        "test_enterprise_sandbox_execution.py",
        "test_enterprise_sandbox_task_injection_proof.py",
        "test_settings_enterprise_sandbox_execution_runtime.py",
        "test_enterprise_endpoint_failure_review.py",
        "test_settings_enterprise_endpoint_failure_review_runtime.py",
        "test_settings_enterprise_failure_review_ui.py",
        "test_admin_enterprise_failure_review_ui.py",
        "test_settings_enterprise_endpoints_ui.py",
        "test_settings_enterprise_sandbox_proof_ui.py",
        "test_settings_enterprise_integration_runtime.py",
        "test_enterprise_endpoint_sandbox_readiness.py",
        "test_api_readiness_automatic_gate_b1.py",
        "test_api_readiness_app_coverage_b1.py",
    }
    assert all(name in text for name in required)
    assert len(required) >= 20
    for name in required:
        assert (ROOT / "tests" / name).is_file(), name


def test_skip_full_program_is_diagnostic_only() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "[switch]$SkipFullProgram" in text
    assert "if (-not $SkipFullProgram)" in text
    assert '($SkipFullProgram -or $fullProgram.overall_status -eq "passed")' in text
