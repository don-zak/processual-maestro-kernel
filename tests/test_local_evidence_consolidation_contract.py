from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_local_evidence_consolidation.ps1"
LINEAGE = ROOT / "scripts" / "analyze_review_decision_lineage.ps1"


def _script_text() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_evidence_consolidation_script_exists_and_is_read_only_by_contract():
    text = _script_text()

    assert "READ_ONLY_EVIDENCE_CONSOLIDATION" in text
    assert "deletion_authorized = $false" in text
    assert "repository_reconciliation_complete = $false" in text
    assert "version_number_is_not_supersession_authority = $true" in text
    assert "old_tracked_version_requires_historical_proof = $true" in text

    for destructive_token in ("Remove-Item", "Move-Item", "git clean", "git rm"):
        assert destructive_token not in text


def test_evidence_consolidation_covers_required_local_evidence_families():
    text = _script_text()
    for required_path_or_pattern in (
        "pmk-review-decisions-v*.json",
        "cgt17_branch_retirement_audit_*.json",
        ".coverage",
        "coverage.xml",
        ".pmk-validation",
        ".pmk-local-review",
        "local-qualification-results",
        "PMK_Transition_Handoff_Report_20260811_v2.docx",
        "maestro-update-backup",
    ):
        assert required_path_or_pattern in text

    for required_output in (
        "evidence-consolidation-{0}.json",
        "evidence-consolidation-{0}.csv",
        "evidence-consolidation-{0}.md",
    ):
        assert required_output in text


def test_unknown_provenance_and_dependencies_remain_unasserted():
    text = _script_text()
    assert "source_head = $null" in text
    assert "observed_at_head = $head" in text
    assert "runtime_dependency = $null" in text
    assert "unknown_provenance_is_null = $true" in text
    assert "unknown_dependency_is_null = $true" in text


def test_backup_classification_does_not_claim_historical_version_without_proof():
    text = _script_text()
    assert "EXACT_CURRENT_COPY" in text
    assert "DIVERGENT_UNTRACKED" in text
    assert "DATABASE_BACKUP" in text
    assert "UNIQUE_UNTRACKED" in text
    assert "OLD_TRACKED_VERSION" not in text or "return 'OLD_TRACKED_VERSION'" not in text


def test_windows_powershell_uses_relative_path_compatibility_fallback():
    text = _script_text()
    assert "function Get-CompatibleRelativePath" in text
    assert "[System.IO.Path].GetMethod(" in text
    assert "New-Object System.Uri" in text
    assert ".MakeRelativeUri(" in text


def test_json_metadata_supports_python_fallback_and_empty_files():
    text = _script_text()
    assert "schema_version = 4" in text
    assert "function Test-JsonWithPython" in text
    assert "json_validator = $null" in text
    assert "$metadata.json_parse_status = 'EMPTY'" in text
    assert "$metadata.json_parse_status = 'VALID_PYTHON_FALLBACK'" in text
    assert "$metadata.json_parse_status = 'INVALID'" in text
    assert "$metadata.json_validator = 'PYTHON'" in text
    assert "python_fallback_json_count" in text


def test_review_decision_lineage_is_read_only_and_enumerates_root_array():
    text = LINEAGE.read_text(encoding="utf-8")
    assert "READ_ONLY_REVIEW_DECISION_LINEAGE" in text
    assert "schema_version = 2" in text
    assert "foreach ($item in $parsed)" in text
    assert "$itemCount += 1" in text
    assert "previous_is_identity_subset" in text
    assert "previous_is_exact_subset" in text
    assert "identities_missing_from_latest" in text
    for destructive_token in ("Remove-Item", "Move-Item", "git clean", "git rm"):
        assert destructive_token not in text


def test_every_artifact_starts_non_retirable_and_non_deletable():
    text = _script_text()
    assert "retirement_candidate = $false" in text
    assert "deletion_authorized = $false" in text
    assert "deletion_authorized_count" in text
