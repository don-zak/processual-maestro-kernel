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

    for destructive_token in (
        "Remove-Item",
        "Move-Item",
        "git clean",
        "git rm",
    ):
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
    assert "OLD_TRACKED_VERSION" in text
    assert "Historical blob proof is required" in text

    # The current first-pass analyzer may name OLD_TRACKED_VERSION as a policy
    # concept, but it must not return that classification without historical
    # blob proof.
    assert "return 'OLD_TRACKED_VERSION'" not in text


def test_windows_powershell_uses_relative_path_compatibility_fallback():
    text = _script_text()

    assert "function Get-CompatibleRelativePath" in text
    assert "[System.IO.Path].GetMethod(" in text
    assert "New-Object System.Uri" in text
    assert ".MakeRelativeUri(" in text
    assert "Get-CompatibleRelativePath -BasePath $rootPath -TargetPath $Path" in text
    assert "Get-CompatibleRelativePath -BasePath $backupRoot -TargetPath $File.FullName" in text


def test_json_metadata_distinguishes_arrays_objects_empty_and_invalid_json():
    text = _script_text()

    assert "schema_version = 3" in text
    assert "json_parse_error = $null" in text
    assert "json_root_type = $null" in text
    assert "json_item_count = $null" in text
    assert "json_item_keys = @()" in text
    assert "$metadata.json_parse_status = 'EMPTY'" in text
    assert "$metadata.json_parse_status = 'INVALID'" in text
    assert "$metadata.json_root_type = 'ARRAY'" in text
    assert "$metadata.json_root_type = 'OBJECT'" in text
    assert "$metadata.json_root_type = 'SCALAR'" in text
    assert "$metadata.json_item_count = $items.Count" in text
    assert "$metadata.json_item_keys = @($itemKeys | Sort-Object -Unique)" in text
    assert "$metadata.json_parse_error = $_.Exception.Message" in text
    assert "empty_json_count" in text


def test_review_decision_lineage_is_read_only_and_requires_exact_subset_proof():
    text = LINEAGE.read_text(encoding="utf-8")

    assert "READ_ONLY_REVIEW_DECISION_LINEAGE" in text
    assert "deletion_authorized = $false" in text
    assert "version_number_is_not_supersession_authority = $true" in text
    assert "exact_subset_proof_required = $true" in text
    assert "previous_is_identity_subset" in text
    assert "previous_is_exact_subset" in text
    assert "identities_missing_from_latest" in text

    for destructive_token in (
        "Remove-Item",
        "Move-Item",
        "git clean",
        "git rm",
    ):
        assert destructive_token not in text


def test_every_artifact_starts_non_retirable_and_non_deletable():
    text = _script_text()

    assert "retirement_candidate = $false" in text
    assert "deletion_authorized = $false" in text
    assert "deletion_authorized_count" in text
