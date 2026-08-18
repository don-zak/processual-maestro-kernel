from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_customer_billing_comprehensive.ps1"


def test_comprehensive_billing_verification_script_exists_and_chains_full_program() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    required_markers = (
        "Customer billing contract and gateways",
        "Maestro Units, quota, plan, and usage regressions",
        "Top-up purchase, grant, and reversal lifecycle",
        "API readiness, Settings, admin UI, and canonical billing boundaries",
        "verify_full_program_local.ps1",
        "customer-billing-comprehensive-verification.json",
        "customer-billing-comprehensive-verification.md",
        "CUSTOMER BILLING COMPREHENSIVE VERIFICATION PASSED",
        "2026-08-customer-billing-comprehensive-powershell-v1",
    )
    for marker in required_markers:
        assert marker in source


def test_all_pytest_files_referenced_by_verification_bundle_exist() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    referenced = sorted(set(re.findall(r'"(tests/test_[^"]+\.py)"', source)))

    assert referenced
    assert len(referenced) >= 20
    missing = [path for path in referenced if not (ROOT / path).is_file()]
    assert missing == []


def test_verification_bundle_is_fail_closed_and_emits_phase_evidence() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert '$ErrorActionPreference = "Stop"' in source
    assert "--junitxml=$junitPath" in source
    assert "Tee-Object -FilePath $logPath" in source
    assert 'if ($status -ne "passed")' in source
    assert 'if (-not $overallPassed)' in source
    assert "Per-phase JUnit XML and logs" in source
    assert "full-program-verification.json" in source
